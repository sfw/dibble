from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from time import monotonic
from uuid import uuid4

from dibble.models.generation import (
    DeliveryMode,
    GeneratedContent,
    GeneratedBlock,
    GenerationMetadata,
    GenerationRequest,
    GenerationResponse,
    GenerationStreamEvent,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import ProviderPlugin, RetrieverPlugin, RouterPlugin, ValidatorPlugin
from dibble.services.generation_modes import build_generation_mode_plan
from dibble.services.generated_content_store import SQLiteGeneratedContentStore


class GenerationEngine:
    def __init__(
        self,
        retriever: RetrieverPlugin,
        router: RouterPlugin,
        provider: ProviderPlugin,
        validator: ValidatorPlugin,
        generated_content_store: SQLiteGeneratedContentStore | None = None,
        cache_ttl_seconds: int = 3600,
        time_provider=monotonic,
    ) -> None:
        self.retriever = retriever
        self.router = router
        self.provider = provider
        self.validator = validator
        self.generated_content_store = generated_content_store
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self.time_provider = time_provider

    def generate(self, profile: LearnerProfile, request: GenerationRequest) -> GenerationResponse:
        grounding = self.retriever.retrieve(profile, request)
        route = self.router.route(profile, request)
        cache_key = self._cache_key(profile, request, route, grounding)
        cached = self._get_cached_content(cache_key=cache_key)
        if cached is not None:
            return cached.response

        started_at = self.time_provider()
        blocks = self.provider.generate(profile, request, route, [item.title for item in grounding])
        response = self._build_response(profile, request, route, grounding, blocks)
        content = self._build_generated_content(
            profile=profile,
            request=request,
            response=response,
            cache_hit=False,
            generation_latency_ms=int(round((self.time_provider() - started_at) * 1000)),
        )
        self._store_generated_content(cache_key=cache_key, content=content)
        return content.response

    def stream_generate(self, profile: LearnerProfile, request: GenerationRequest) -> Iterator[GenerationStreamEvent]:
        grounding = self.retriever.retrieve(profile, request)
        route = self.router.route(profile, request)
        cache_key = self._cache_key(profile, request, route, grounding)
        cached = self._get_cached_content(cache_key=cache_key)
        if cached is not None:
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

        yield GenerationStreamEvent(
            event="start",
            student_id=profile.student_id,
            route=route,
            grounding=grounding,
        )

        started_at = self.time_provider()
        block_buffers: dict[int, GeneratedBlock] = {}
        for chunk in self.provider.stream_generate(profile, request, route, [item.title for item in grounding]):
            current = block_buffers.get(chunk.block_index)
            if current is None:
                current = GeneratedBlock(kind=chunk.kind, title=chunk.title, body="")
                block_buffers[chunk.block_index] = current

            current.body += chunk.body_delta
            yield GenerationStreamEvent(
                event="delta",
                student_id=profile.student_id,
                chunk=chunk,
            )

        blocks = [block_buffers[index] for index in sorted(block_buffers)]
        response = self._build_response(profile, request, route, grounding, blocks)
        content = self._build_generated_content(
            profile=profile,
            request=request,
            response=response,
            cache_hit=False,
            generation_latency_ms=int(round((self.time_provider() - started_at) * 1000)),
        )
        self._store_generated_content(cache_key=cache_key, content=content)
        yield GenerationStreamEvent(
            event="complete",
            student_id=profile.student_id,
            route=content.response.route,
            grounding=content.response.grounding,
            validation_issues=content.response.validation_issues,
            response=content.response,
        )

    def _build_response(self, profile: LearnerProfile, request: GenerationRequest, route, grounding, blocks: list[GeneratedBlock]) -> GenerationResponse:
        validation_issues = self.validator.validate(blocks, grounding)

        if validation_issues and not grounding:
            route.delivery_mode = DeliveryMode.static_fallback

        return GenerationResponse(
            student_id=profile.student_id,
            route=route,
            blocks=blocks,
            curriculum_context=request.curriculum_context,
            grounding=grounding,
            safety_notes=[
                "Generation is a scaffolded draft and should be validated against curriculum standards before student delivery.",
                "Profiles should avoid sensitive inference beyond declared accommodations and observable learning signals.",
            ],
            validation_issues=validation_issues,
        )

    def _build_generated_content(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        response: GenerationResponse,
        cache_hit: bool,
        generation_latency_ms: int,
    ) -> GeneratedContent:
        plan = build_generation_mode_plan(profile, request, response.route)
        provider_descriptor = self._provider_descriptor()
        metadata = GenerationMetadata(
            quality_score=self._quality_score(response),
            validation_passed=not response.validation_issues,
            validation_issue_count=len(response.validation_issues),
            grounding_count=len(response.grounding),
            provider_name=provider_descriptor.get("provider_name"),
            model_used=provider_descriptor.get("model_used"),
            prompt_template_name=provider_descriptor.get("prompt_template_name"),
            prompt_template_version=provider_descriptor.get("prompt_template_version"),
            prompt_template_variant=provider_descriptor.get("prompt_template_variant"),
            generation_latency_ms=max(0, generation_latency_ms),
            cache_hit=cache_hit,
        )
        generation_id = response.generation_id or str(uuid4())
        updated_response = response.model_copy(
            update={
                "generation_id": generation_id,
                "generation_metadata": metadata,
            }
        )
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(seconds=self.cache_ttl_seconds) if self.cache_ttl_seconds > 0 else None
        return GeneratedContent(
            generation_id=generation_id,
            student_id=profile.student_id,
            content_type=plan.content_type.value,
            request_context=plan.request_context,
            response=updated_response,
            quality=metadata,
            created_at=created_at,
            expires_at=expires_at,
        )

    def _get_cached_content(self, *, cache_key: str) -> GeneratedContent | None:
        if self.generated_content_store is None or self.cache_ttl_seconds <= 0:
            return None
        cached = self.generated_content_store.get_fresh(cache_key=cache_key)
        if cached is None:
            return None
        cached_quality = cached.quality.model_copy(update={"cache_hit": True})
        cached_response = cached.response.model_copy(update={"generation_metadata": cached_quality})
        return cached.model_copy(update={"quality": cached_quality, "response": cached_response})

    def _store_generated_content(self, *, cache_key: str, content: GeneratedContent) -> None:
        if self.generated_content_store is None or self.cache_ttl_seconds <= 0:
            return
        self.generated_content_store.upsert(cache_key=cache_key, content=content)

    def _cache_key(self, profile: LearnerProfile, request: GenerationRequest, route, grounding) -> str:
        payload = {
            "profile": profile.model_dump(mode="json"),
            "request": {
                key: value
                for key, value in request.model_dump(mode="json").items()
                if key != "learning_session_id"
            },
            "route": route.model_dump(mode="json"),
            "grounding": [item.model_dump(mode="json") for item in grounding],
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _quality_score(self, response: GenerationResponse) -> float:
        base_score = 1.0
        base_score -= min(len(response.validation_issues) * 0.15, 0.6)
        if not response.grounding:
            base_score -= 0.2
        if response.route.delivery_mode == DeliveryMode.static_fallback:
            base_score -= 0.1
        return round(max(0.0, min(base_score, 1.0)), 2)

    def _provider_descriptor(self) -> dict[str, str | None]:
        descriptor = getattr(self.provider, "last_used_descriptor", None)
        if isinstance(descriptor, dict):
            return {
                "provider_name": descriptor.get("provider_name"),
                "model_used": descriptor.get("model_used"),
                "prompt_template_name": descriptor.get("prompt_template_name"),
                "prompt_template_version": descriptor.get("prompt_template_version"),
                "prompt_template_variant": descriptor.get("prompt_template_variant"),
            }
        return {
            "provider_name": self.provider.__class__.__name__,
            "model_used": None,
            "prompt_template_name": None,
            "prompt_template_version": None,
            "prompt_template_variant": None,
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
