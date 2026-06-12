from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import UUID, uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    CurriculumContentKey,
    CurriculumLibraryEntry,
    CurriculumLibraryStorageScope,
    CurriculumContentRequest,
    DeliveryMode,
    GeneratedContent,
    GeneratedBlock,
    GenerationMetadata,
    ModerationResult,
    GenerationRequest,
    GenerationResponse,
    GenerationStreamEvent,
    GroundingReference,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import (
    ProviderPlugin,
    RetrieverPlugin,
    RouterPlugin,
    ValidatorPlugin,
)
from dibble.services.content_moderation import ContentModerationService
from dibble.services.generated_block_normalizer import normalize_generated_blocks
from dibble.services.harness.content_library import (
    GeneratedContentBackedCurriculumLibraryStore,
    LocalCurriculumContentLibrary,
)
from dibble.services.harness.facades import (
    AuthoringHarnessFacade,
    ContentLibraryHarnessFacade,
    GenerationHarnessFacades,
    PreparedAuthoringRequest,
    RoutingHarnessFacade,
)
from dibble.services.harness.policy import (
    HarnessAuthoringPolicy,
    HarnessAuthoringPolicyBuilder,
)
from dibble.services.harness.request_adapter import CurriculumContentRequestAdapter
from dibble.services.harness.content_library import CurriculumContentLibrary
from dibble.services.math_verification import (
    VERIFICATION_FAILED_EVENT_TYPE,
    MathVerificationOutcome,
    MathVerificationService,
)
from dibble.services.protocols import AuditStore, GeneratedContentStore
from dibble.services.runtime_telemetry import log_runtime_event
from dibble.services.surplus_practice_cache import SurplusPracticeCache

logger = logging.getLogger(__name__)
_CURRICULUM_LIBRARY_STUDENT_ID = UUID("00000000-0000-0000-0000-000000000000")


class GenerationEngine:
    def __init__(
        self,
        retriever: RetrieverPlugin,
        router: RouterPlugin,
        provider: ProviderPlugin,
        validator: ValidatorPlugin,
        moderation_service: ContentModerationService | None = None,
        generated_content_store: GeneratedContentStore | None = None,
        content_library: CurriculumContentLibrary | None = None,
        harness: GenerationHarnessFacades | None = None,
        surplus_practice_cache: SurplusPracticeCache | None = None,
        cache_ttl_seconds: int = 3600,
        time_provider=monotonic,
        math_verification_service: MathVerificationService | None = None,
        audit_store: AuditStore | None = None,
        verification_retry_attempts: int = 2,
    ) -> None:
        self.retriever = retriever
        self.router = router
        self.provider = provider
        self.validator = validator
        self.moderation_service = moderation_service or ContentModerationService()
        self.generated_content_store = generated_content_store
        resolved_library = content_library
        if resolved_library is None and generated_content_store is not None:
            resolved_library = LocalCurriculumContentLibrary(
                GeneratedContentBackedCurriculumLibraryStore(generated_content_store)
            )
        self.harness = harness or GenerationHarnessFacades(
            routing=RoutingHarnessFacade(router=router),
            authoring=AuthoringHarnessFacade(
                policy_builder=HarnessAuthoringPolicyBuilder(),
                request_adapter=CurriculumContentRequestAdapter()
            ),
            content_library=ContentLibraryHarnessFacade(library=resolved_library),
        )
        self.surplus_practice_cache = surplus_practice_cache
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self.time_provider = time_provider
        self.math_verification_service = math_verification_service
        self.audit_store = audit_store
        self.verification_retry_attempts = max(0, verification_retry_attempts)

    def _safe_retrieve(
        self, request: CurriculumContentRequest
    ) -> list[GroundingReference]:
        """Retrieve grounding references, falling back to empty on error."""
        try:
            return self.retriever.retrieve(request)
        except Exception:
            logger.warning(
                "Retriever failed for curriculum request; proceeding without grounding",
                exc_info=True,
            )
            return []

    def generate(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> GenerationResponse:
        route = self.harness.routing.decide_route(profile=profile, request=request)
        prepared_authoring = self.harness.authoring.prepare_request_for(
            profile=profile,
            request=request,
            route=route,
        )
        return self.generate_prepared(
            profile=profile,
            request=request,
            route=route,
            prepared_authoring=prepared_authoring,
        )

    def generate_prepared(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        prepared_authoring: PreparedAuthoringRequest,
    ) -> GenerationResponse:
        route = route.model_copy(deep=True)
        authoring_policy = prepared_authoring.policy
        curriculum_request = prepared_authoring.curriculum_request
        grounding = self._safe_retrieve(curriculum_request)
        log_runtime_event(
            logger,
            logging.DEBUG,
            "generation.engine.route",
            student_id=str(profile.student_id),
            learning_session_id=request.learning_session_id,
            intervention_type=route.intervention_type.value,
            delivery_mode=route.delivery_mode.value,
            scaffolding_level=route.scaffolding_level,
            grounding_count=len(grounding),
            request=request.model_dump(mode="json"),
            curriculum_request=curriculum_request.model_dump(mode="json"),
            route=route.model_dump(mode="json"),
            grounding=[item.model_dump(mode="json") for item in grounding],
        )
        surplus = self._pop_surplus(profile, request)
        if surplus is not None:
            return surplus.response

        content_key = self._content_library_key(
            request=curriculum_request,
            route=route,
            grounding=grounding,
        )
        cached, cached_history_needs_store = self._get_cached_content(
            profile=profile,
            authoring_policy=authoring_policy,
            content_key=content_key,
        )
        if cached is not None:
            if cached_history_needs_store:
                self._store_generated_history(content=cached)
            log_runtime_event(
                logger,
                logging.DEBUG,
                "generation.engine.cache_hit",
                generation_id=cached.response.generation_id,
                student_id=str(profile.student_id),
                learning_session_id=request.learning_session_id,
                cached_content=cached.model_dump(mode="json"),
            )
            return cached.response

        started_at = self.time_provider()
        surplus_blocks: list[GeneratedBlock] = []
        request_moderation = self.moderation_service.moderate_request(request)
        if request_moderation.status == "flagged":
            blocks = self._moderation_fallback_blocks(
                request=request,
                grounding=grounding,
                moderation=request_moderation,
            )
            moderation = self._apply_moderation_fallback(
                moderation=request_moderation,
                decision="block_request",
                fallback_kind="request_safe_reset",
                stream_action="emit_fallback_only",
                provider_invoked=False,
                stream_buffered=False,
                original_block_count=0,
                replacement_block_count=len(blocks),
            )
            route.delivery_mode = DeliveryMode.static_fallback
            verification = MathVerificationOutcome()
            verification_attempts = 0
        else:
            blocks = self.provider.generate(curriculum_request, route, grounding)
            blocks = normalize_generated_blocks(blocks)
            blocks, surplus_blocks = self._split_surplus(blocks)
            blocks, verification, verification_attempts = (
                self._apply_math_verification(
                    profile=profile,
                    request=request,
                    curriculum_request=curriculum_request,
                    route=route,
                    grounding=grounding,
                    blocks=blocks,
                )
            )
            moderation = self.moderation_service.moderate_blocks(blocks)
            if moderation.status == "flagged":
                original_blocks = len(blocks)
                blocks = self._moderation_fallback_blocks(
                    request=request,
                    grounding=grounding,
                    moderation=moderation,
                )
                moderation = self._apply_moderation_fallback(
                    moderation=moderation,
                    decision="rewrite_response",
                    fallback_kind="response_teacher_safe_rewrite",
                    stream_action="replace_before_delivery",
                    provider_invoked=True,
                    stream_buffered=False,
                    original_block_count=original_blocks,
                    replacement_block_count=len(blocks),
                )
                route.delivery_mode = DeliveryMode.static_fallback
        response = self._build_response(
            profile, request, route, grounding, blocks, moderation=moderation
        )
        content = self._build_generated_content(
            profile=profile,
            response=response,
            authoring_policy=authoring_policy,
            moderation=moderation,
            cache_hit=False,
            generation_latency_ms=int(
                round((self.time_provider() - started_at) * 1000)
            ),
            verification=verification,
            verification_attempts=verification_attempts,
        )
        self._store_generated_content(content_key=content_key, content=content)
        self._cache_surplus(surplus_blocks, blocks, content, profile, request)
        log_runtime_event(
            logger,
            logging.DEBUG,
            "generation.engine.complete",
            generation_id=content.generation_id,
            student_id=str(profile.student_id),
            learning_session_id=request.learning_session_id,
            moderation_status=moderation.status,
            validation_issue_count=len(response.validation_issues),
            generation_latency_ms=content.quality.generation_latency_ms,
            response=response.model_dump(mode="json"),
            generated_content=content.model_dump(mode="json"),
        )
        return content.response

    def stream_generate(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> Iterator[GenerationStreamEvent]:
        route = self.harness.routing.decide_route(profile=profile, request=request)
        prepared_authoring = self.harness.authoring.prepare_request_for(
            profile=profile,
            request=request,
            route=route,
        )
        return self.stream_generate_prepared(
            profile=profile,
            request=request,
            route=route,
            prepared_authoring=prepared_authoring,
        )

    def stream_generate_prepared(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        prepared_authoring: PreparedAuthoringRequest,
    ) -> Iterator[GenerationStreamEvent]:
        route = route.model_copy(deep=True)
        authoring_policy = prepared_authoring.policy
        curriculum_request = prepared_authoring.curriculum_request
        grounding = self._safe_retrieve(curriculum_request)

        surplus = self._pop_surplus(profile, request)
        if surplus is not None:
            yield GenerationStreamEvent(
                event="start",
                student_id=profile.student_id,
                route=surplus.response.route,
                grounding=surplus.response.grounding,
            )
            for chunk in self._stream_cached_blocks(surplus.response.blocks):
                yield GenerationStreamEvent(
                    event="delta",
                    student_id=profile.student_id,
                    chunk=chunk,
                )
            yield GenerationStreamEvent(
                event="complete",
                student_id=profile.student_id,
                route=surplus.response.route,
                grounding=surplus.response.grounding,
                validation_issues=surplus.response.validation_issues,
                response=surplus.response,
            )
            return

        content_key = self._content_library_key(
            request=curriculum_request,
            route=route,
            grounding=grounding,
        )
        cached, cached_history_needs_store = self._get_cached_content(
            profile=profile,
            authoring_policy=authoring_policy,
            content_key=content_key,
        )
        if cached is not None:
            if cached_history_needs_store:
                self._store_generated_history(content=cached)
            log_runtime_event(
                logger,
                logging.DEBUG,
                "generation.engine.stream.cache_hit",
                generation_id=cached.response.generation_id,
                student_id=str(profile.student_id),
                learning_session_id=request.learning_session_id,
                cached_content=cached.model_dump(mode="json"),
            )
            yield GenerationStreamEvent(
                event="start",
                student_id=profile.student_id,
                route=cached.response.route,
                grounding=cached.response.grounding,
            )
            for chunk in self._stream_cached_blocks(cached.response.blocks):
                yield GenerationStreamEvent(
                    event="delta",
                    student_id=profile.student_id,
                    chunk=chunk,
                )
            yield GenerationStreamEvent(
                event="complete",
                student_id=profile.student_id,
                route=cached.response.route,
                grounding=cached.response.grounding,
                validation_issues=cached.response.validation_issues,
                response=cached.response,
            )
            return

        started_at = self.time_provider()
        surplus_blocks: list[GeneratedBlock] = []
        request_moderation = self.moderation_service.moderate_request(request)
        if request_moderation.status == "flagged":
            blocks = self._moderation_fallback_blocks(
                request=request,
                grounding=grounding,
                moderation=request_moderation,
            )
            moderation = self._apply_moderation_fallback(
                moderation=request_moderation,
                decision="block_request",
                fallback_kind="request_safe_reset",
                stream_action="emit_fallback_only",
                provider_invoked=False,
                stream_buffered=False,
                original_block_count=0,
                replacement_block_count=len(blocks),
            )
            route.delivery_mode = DeliveryMode.static_fallback
            verification = MathVerificationOutcome()
            verification_attempts = 0
            yield GenerationStreamEvent(
                event="start",
                student_id=profile.student_id,
                route=route,
                grounding=grounding,
            )
            yield self._moderation_event(
                profile=profile, route=route, moderation=moderation
            )
        else:
            yield GenerationStreamEvent(
                event="start",
                student_id=profile.student_id,
                route=route,
                grounding=grounding,
            )
            block_buffers: dict[int, GeneratedBlock] = {}
            for chunk in self.provider.stream_generate(
                curriculum_request, route, grounding
            ):
                if chunk.block is not None:
                    block_buffers[chunk.block_index] = chunk.block
                    continue
                current = block_buffers.get(chunk.block_index)
                if current is None:
                    current = GeneratedBlock(
                        kind=chunk.kind, title=chunk.title, body=""
                    )
                    block_buffers[chunk.block_index] = current
                current.body += chunk.body_delta
            blocks = normalize_generated_blocks(
                [block_buffers[index] for index in sorted(block_buffers)]
            )
            blocks, surplus_blocks = self._split_surplus(blocks)
            blocks, verification, verification_attempts = (
                self._apply_math_verification(
                    profile=profile,
                    request=request,
                    curriculum_request=curriculum_request,
                    route=route,
                    grounding=grounding,
                    blocks=blocks,
                )
            )
            moderation = self.moderation_service.moderate_blocks(blocks)
            if moderation.status == "flagged":
                original_blocks = len(blocks)
                blocks = self._moderation_fallback_blocks(
                    request=request,
                    grounding=grounding,
                    moderation=moderation,
                )
                moderation = self._apply_moderation_fallback(
                    moderation=moderation,
                    decision="rewrite_response",
                    fallback_kind="response_teacher_safe_rewrite",
                    stream_action="replace_before_stream",
                    provider_invoked=True,
                    stream_buffered=True,
                    original_block_count=original_blocks,
                    replacement_block_count=len(blocks),
                )
                route.delivery_mode = DeliveryMode.static_fallback
                yield self._moderation_event(
                    profile=profile, route=route, moderation=moderation
                )

        for chunk in self._stream_cached_blocks(blocks):
            yield GenerationStreamEvent(
                event="delta",
                student_id=profile.student_id,
                chunk=chunk,
            )

        response = self._build_response(
            profile, request, route, grounding, blocks, moderation=moderation
        )
        content = self._build_generated_content(
            profile=profile,
            response=response,
            authoring_policy=authoring_policy,
            moderation=moderation,
            cache_hit=False,
            generation_latency_ms=int(
                round((self.time_provider() - started_at) * 1000)
            ),
            verification=verification,
            verification_attempts=verification_attempts,
        )
        self._store_generated_content(content_key=content_key, content=content)
        self._cache_surplus(surplus_blocks, blocks, content, profile, request)
        log_runtime_event(
            logger,
            logging.DEBUG,
            "generation.engine.stream.complete",
            generation_id=content.generation_id,
            student_id=str(profile.student_id),
            learning_session_id=request.learning_session_id,
            moderation_status=moderation.status,
            validation_issue_count=len(response.validation_issues),
            generation_latency_ms=content.quality.generation_latency_ms,
            response=response.model_dump(mode="json"),
            generated_content=content.model_dump(mode="json"),
        )
        yield GenerationStreamEvent(
            event="complete",
            student_id=profile.student_id,
            route=content.response.route,
            grounding=content.response.grounding,
            validation_issues=content.response.validation_issues,
            response=content.response,
        )

    def _pop_surplus(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> GeneratedContent | None:
        if self.surplus_practice_cache is None:
            return None
        return self.surplus_practice_cache.pop_surplus(
            student_id=profile.student_id,
            learning_session_id=request.learning_session_id,
        )

    def _split_surplus(
        self, blocks: list[GeneratedBlock]
    ) -> tuple[list[GeneratedBlock], list[GeneratedBlock]]:
        if self.surplus_practice_cache is None:
            return blocks, []
        return SurplusPracticeCache.split_practice_blocks(blocks)

    def _cache_surplus(
        self,
        surplus_blocks: list[GeneratedBlock],
        delivery_blocks: list[GeneratedBlock],
        content: GeneratedContent,
        profile: LearnerProfile,
        request: GenerationRequest,
    ) -> None:
        if not surplus_blocks or self.surplus_practice_cache is None:
            return
        non_practice = [b for b in delivery_blocks if b.kind != "practice_problem"]
        self.surplus_practice_cache.cache_surplus(
            surplus_blocks=surplus_blocks,
            non_practice_blocks=non_practice,
            parent_content=content,
            profile=profile,
            request=request,
        )

    def _build_response(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route,
        grounding,
        blocks: list[GeneratedBlock],
        *,
        moderation: ModerationResult,
    ) -> GenerationResponse:
        validation_issues = self.validator.validate(blocks, grounding)

        if validation_issues and not grounding:
            route.delivery_mode = DeliveryMode.static_fallback

        return GenerationResponse(
            student_id=profile.student_id,
            route=route,
            blocks=blocks,
            curriculum_context=request.curriculum_context,
            grounding=grounding,
            safety_notes=self._safety_notes(moderation=moderation),
            validation_issues=validation_issues,
        )

    def _build_generated_content(
        self,
        *,
        profile: LearnerProfile,
        response: GenerationResponse,
        authoring_policy: HarnessAuthoringPolicy,
        moderation: ModerationResult,
        cache_hit: bool,
        generation_latency_ms: int,
        verification: MathVerificationOutcome | None = None,
        verification_attempts: int = 0,
    ) -> GeneratedContent:
        provider_descriptor = self._provider_descriptor()
        resolved_verification = verification or MathVerificationOutcome()
        metadata = GenerationMetadata(
            quality_score=self._quality_score(response, moderation=moderation),
            validation_passed=not response.validation_issues,
            validation_issue_count=len(response.validation_issues),
            grounding_count=len(response.grounding),
            provider_name=provider_descriptor.get("provider_name"),
            model_used=provider_descriptor.get("model_used"),
            prompt_template_name=provider_descriptor.get("prompt_template_name"),
            prompt_template_version=provider_descriptor.get("prompt_template_version"),
            prompt_template_variant=provider_descriptor.get("prompt_template_variant"),
            generation_latency_ms=max(0, generation_latency_ms),
            prompt_tokens=int(provider_descriptor.get("prompt_tokens") or 0),
            completion_tokens=int(provider_descriptor.get("completion_tokens") or 0),
            cache_hit=cache_hit,
            verification_status=resolved_verification.status,
            verification_issue_count=len(resolved_verification.issues),
            verification_attempts=max(0, verification_attempts),
            moderation=moderation,
        )
        generation_id = response.generation_id or str(uuid4())
        updated_response = response.model_copy(
            update={
                "generation_id": generation_id,
                "generation_metadata": metadata,
            }
        )
        created_at = datetime.now(timezone.utc)
        expires_at = (
            created_at + timedelta(seconds=self.cache_ttl_seconds)
            if self.cache_ttl_seconds > 0
            else None
        )
        return GeneratedContent(
            generation_id=generation_id,
            student_id=profile.student_id,
            content_type=authoring_policy.content_type.value,
            request_context=authoring_policy.request_context,
            response=updated_response,
            quality=metadata,
            created_at=created_at,
            expires_at=expires_at,
        )

    def _get_cached_content(
        self,
        *,
        profile: LearnerProfile,
        authoring_policy: HarnessAuthoringPolicy,
        content_key: CurriculumContentKey,
    ) -> tuple[GeneratedContent | None, bool]:
        if self.cache_ttl_seconds <= 0:
            return None, False
        cached_entry = self.harness.content_library.get_fresh_entry(
            key=content_key,
            learner_id=str(profile.student_id),
        )
        if cached_entry is None:
            return None, False
        if (
            self.generated_content_store is not None
            and cached_entry.source_generation_id is not None
        ):
            source_content = self.generated_content_store.get(
                generation_id=cached_entry.source_generation_id
            )
            if (
                source_content is not None
                and source_content.student_id == profile.student_id
            ):
                cached_quality = source_content.quality.model_copy(
                    update={"cache_hit": True, "generation_latency_ms": 0}
                )
                cached_response = source_content.response.model_copy(
                    update={"generation_metadata": cached_quality}
                )
                return (
                    source_content.model_copy(
                        update={
                            "quality": cached_quality,
                            "response": cached_response,
                        }
                    ),
                    False,
                )
        cached = self._materialize_cached_content(
            profile=profile,
            authoring_policy=authoring_policy,
            template=cached_entry.content,
        )
        return cached, True

    def _materialize_cached_content(
        self,
        *,
        profile: LearnerProfile,
        authoring_policy: HarnessAuthoringPolicy,
        template: GeneratedContent,
    ) -> GeneratedContent:
        generation_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        expires_at = (
            created_at + timedelta(seconds=self.cache_ttl_seconds)
            if self.cache_ttl_seconds > 0
            else None
        )
        cached_quality = template.quality.model_copy(
            update={"cache_hit": True, "generation_latency_ms": 0}
        )
        cached_response = template.response.model_copy(
            update={
                "student_id": profile.student_id,
                "generation_id": generation_id,
                "generation_metadata": cached_quality,
            }
        )
        return GeneratedContent(
            generation_id=generation_id,
            student_id=profile.student_id,
            content_type=authoring_policy.content_type.value,
            request_context=authoring_policy.request_context,
            response=cached_response,
            quality=cached_quality,
            created_at=created_at,
            expires_at=expires_at,
        )

    def _store_generated_history(self, *, content: GeneratedContent) -> None:
        if self.generated_content_store is None:
            return
        self.generated_content_store.upsert(
            cache_key=self._history_cache_key(content=content),
            content=content,
        )

    def _library_template_content(
        self,
        *,
        content: GeneratedContent,
        content_key: CurriculumContentKey,
    ) -> GeneratedContent:
        sanitized_quality = content.quality.model_copy(update={"cache_hit": False})
        sanitized_response = content.response.model_copy(
            update={
                "student_id": _CURRICULUM_LIBRARY_STUDENT_ID,
                "generation_metadata": sanitized_quality,
            }
        )
        return GeneratedContent(
            generation_id=content.generation_id,
            student_id=_CURRICULUM_LIBRARY_STUDENT_ID,
            content_type=content.content_type,
            request_context={
                "selected_content_type": content.content_type,
                "curriculum_cache_key": content_key.cache_key(),
                "library_storage_scope": CurriculumLibraryStorageScope.local_only.value,
            },
            response=sanitized_response,
            quality=sanitized_quality,
            created_at=content.created_at,
            expires_at=content.expires_at,
        )

    def _store_generated_content(
        self,
        *,
        content_key: CurriculumContentKey,
        content: GeneratedContent,
    ) -> None:
        self._store_generated_history(content=content)
        if self.cache_ttl_seconds <= 0:
            return
        self.harness.content_library.upsert_entry(
            entry=CurriculumLibraryEntry(
                content_key=content_key,
                content=self._library_template_content(
                    content=content,
                    content_key=content_key,
                ),
                storage_scope=CurriculumLibraryStorageScope.local_only,
            ),
            learner_id=str(content.student_id),
        )

    @staticmethod
    def _history_cache_key(*, content: GeneratedContent) -> str:
        return f"generated:{content.generation_id}"

    def _content_library_key(
        self,
        *,
        request: CurriculumContentRequest,
        route,
        grounding,
    ) -> CurriculumContentKey:
        return CurriculumContentKey(request=request, route=route, grounding=grounding)

    def _quality_score(
        self, response: GenerationResponse, *, moderation: ModerationResult
    ) -> float:
        base_score = 1.0
        base_score -= min(len(response.validation_issues) * 0.15, 0.6)
        if not response.grounding:
            base_score -= 0.2
        if response.route.delivery_mode == DeliveryMode.static_fallback:
            base_score -= 0.1
        if moderation.status == "flagged":
            base_score -= 0.1
        return round(max(0.0, min(base_score, 1.0)), 2)

    def _apply_moderation_fallback(
        self,
        *,
        moderation: ModerationResult,
        decision: str,
        fallback_kind: str,
        stream_action: str,
        provider_invoked: bool,
        stream_buffered: bool,
        original_block_count: int,
        replacement_block_count: int,
    ) -> ModerationResult:
        return moderation.model_copy(
            update={
                "blocked": True,
                "decision": decision,
                "request_blocked": decision == "block_request",
                "response_rewritten": decision == "rewrite_response",
                "fallback_applied": True,
                "fallback_kind": fallback_kind,
                "stream_action": stream_action,
                "provider_invoked": provider_invoked,
                "stream_buffered": stream_buffered,
                "original_block_count": max(0, original_block_count),
                "replacement_block_count": max(0, replacement_block_count),
            }
        )

    def _provider_descriptor(self) -> dict[str, object]:
        descriptor = getattr(self.provider, "last_used_descriptor", None)
        if isinstance(descriptor, dict):
            return {
                "provider_name": descriptor.get("provider_name"),
                "model_used": descriptor.get("model_used"),
                "prompt_template_name": descriptor.get("prompt_template_name"),
                "prompt_template_version": descriptor.get("prompt_template_version"),
                "prompt_template_variant": descriptor.get("prompt_template_variant"),
                "prompt_tokens": descriptor.get("prompt_tokens"),
                "completion_tokens": descriptor.get("completion_tokens"),
            }
        return {
            "provider_name": self.provider.__class__.__name__,
            "model_used": None,
            "prompt_template_name": None,
            "prompt_template_version": None,
            "prompt_template_variant": None,
            "prompt_tokens": None,
            "completion_tokens": None,
        }

    def _stream_cached_blocks(self, blocks: list[GeneratedBlock]):
        from dibble.models.generation import GeneratedBlockChunk

        for index, block in enumerate(blocks):
            yield GeneratedBlockChunk(
                block_index=index,
                kind=block.kind,
                title=block.title,
                body_delta=block.body,
                done=True,
            )

    def _moderation_event(
        self,
        *,
        profile: LearnerProfile,
        route,
        moderation: ModerationResult,
    ) -> GenerationStreamEvent:
        return GenerationStreamEvent(
            event="moderation",
            student_id=profile.student_id,
            route=route,
            moderation=moderation,
        )

    def _apply_math_verification(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        curriculum_request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
        blocks: list[GeneratedBlock],
    ) -> tuple[list[GeneratedBlock], MathVerificationOutcome, int]:
        """Verify practice items; on failure regenerate (never repair) up to
        the retry budget, then replace with deterministic fallback content.
        Mutates ``route.delivery_mode`` when the fallback is applied."""
        if self.math_verification_service is None:
            return blocks, MathVerificationOutcome(), 0
        outcome = self.math_verification_service.verify_blocks(blocks)
        attempts = 1
        while outcome.status == "failed" and attempts <= self.verification_retry_attempts:
            self._emit_verification_failed(
                profile=profile,
                request=request,
                outcome=outcome,
                attempt=attempts,
                resolution="regenerated",
            )
            regenerated = normalize_generated_blocks(
                self.provider.generate(curriculum_request, route, grounding)
            )
            regenerated, _ = self._split_surplus(regenerated)
            blocks = regenerated
            outcome = self.math_verification_service.verify_blocks(blocks)
            attempts += 1
        if outcome.status == "failed":
            self._emit_verification_failed(
                profile=profile,
                request=request,
                outcome=outcome,
                attempt=attempts,
                resolution="fallback",
            )
            blocks = self._verification_fallback_blocks(grounding=grounding)
            route.delivery_mode = DeliveryMode.static_fallback
            outcome = MathVerificationOutcome(
                status="fallback",
                issues=outcome.issues,
                checked_block_count=outcome.checked_block_count,
            )
        return blocks, outcome, attempts

    def _emit_verification_failed(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        outcome: MathVerificationOutcome,
        attempt: int,
        resolution: str,
    ) -> None:
        if self.audit_store is None:
            return
        try:
            self.audit_store.append(
                event_type=VERIFICATION_FAILED_EVENT_TYPE,
                status=resolution,
                student_id=str(profile.student_id),
                payload={
                    "attempt": attempt,
                    "resolution": resolution,
                    "issues": list(outcome.issues),
                    "checked_block_count": outcome.checked_block_count,
                    "intent": request.intent.value,
                    "target_kc_ids": list(request.target_kc_ids),
                    "learning_session_id": request.learning_session_id,
                },
            )
        except Exception:  # noqa: BLE001 - telemetry must not break generation
            logger.warning("Failed to record verification audit event", exc_info=True)

    def _verification_fallback_blocks(
        self, *, grounding: list[GroundingReference]
    ) -> list[GeneratedBlock]:
        """Deterministic, answer-key-free review content. Never invents an
        answer that could be wrong in front of a learner."""
        excerpt = next(
            (item.excerpt for item in grounding if item.excerpt),
            None,
        )
        topic = next((item.title for item in grounding), "this concept")
        body_parts = [
            f"Let's take a careful look at {topic} together before trying more practice.",
        ]
        if excerpt:
            body_parts.append(excerpt)
        body_parts.append(
            "Re-read the idea above, then explain it in your own words. "
            "Your next practice question is being prepared."
        )
        return [
            GeneratedBlock(
                kind="exposition",
                title=f"Reviewing {topic}",
                body="\n\n".join(body_parts),
            )
        ]

    def _moderation_fallback_blocks(
        self,
        *,
        request: GenerationRequest,
        grounding: list[GroundingReference],
        moderation: ModerationResult,
    ) -> list[GeneratedBlock]:
        return self.moderation_service.build_fallback_blocks(
            request=request,
            grounding=grounding,
            moderation=moderation,
        )

    def _safety_notes(self, *, moderation: ModerationResult) -> list[str]:
        notes = [
            "Generation is a scaffolded draft and should be validated against curriculum standards before student delivery.",
            "Profiles should avoid sensitive inference beyond declared accommodations and observable learning signals.",
        ]
        if moderation.request_blocked:
            notes.append(
                "Moderation blocked the unsafe request before provider generation and returned a teacher-safe reset."
            )
        elif moderation.response_rewritten:
            notes.append(
                "Moderation withheld an unsafe generated draft and rewrote it as a teacher-safe fallback before delivery."
            )
        return notes
