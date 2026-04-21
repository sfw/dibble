from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from dibble.models.generation import (
    GenerationRequest,
    GenerationResponse,
    GenerationStreamEvent,
)
from dibble.models.observability import HarnessBoundary, OperationalTraceStatus
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import ModalityPlugins
from dibble.services.generation_engine import GenerationEngine
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.harness.facades import PreparedAuthoringRequest
from dibble.services.harness.modality_routing import (
    ModalityRoutingHarness,
    ModalityRoutingPlan,
    TextModalityDirective,
)
from dibble.services.harness.policy import HarnessAuthoringPolicy


@dataclass(frozen=True, slots=True)
class PreparedContentGeneration:
    profile: LearnerProfile
    request: GenerationRequest
    routing_plan: ModalityRoutingPlan
    authoring: PreparedAuthoringRequest


@dataclass(slots=True)
class ContentGenerationHarness:
    generation_engine: GenerationEngine
    modality_routing_harness: ModalityRoutingHarness
    modality_plugins: ModalityPlugins
    operational_observability_service: OperationalObservabilityService | None = None

    def prepare_generation(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        routing_plan: ModalityRoutingPlan | None = None,
    ) -> PreparedContentGeneration:
        resolved_plan = routing_plan or self.modality_routing_harness.plan(
            profile=profile,
            request=request,
        )
        authoring = self.generation_engine.harness.authoring.prepare_request_for(
            profile=profile,
            request=request,
            route=resolved_plan.route,
        )
        effective_plan = resolved_plan
        degraded_reason: str | None = None
        fallback_kind: str | None = None
        try:
            modality_chain = self.modality_plugins.chain_for(
                resolved_plan.directive.plugin_id
            )
        except Exception as exc:
            degraded_reason = str(exc)
            fallback_kind = "text_modality_fallback"
            modality_chain = self._safe_text_chain()
            effective_plan = self._fallback_plan(
                resolved_plan=resolved_plan,
                reason=str(exc),
            )
        request_context = dict(authoring.policy.request_context)
        request_context["selected_modality"] = effective_plan.directive.modality
        request_context["modality_plugin_id"] = effective_plan.directive.plugin_id
        request_context["modality_composition_mode"] = (
            effective_plan.directive.composition_mode
        )
        request_context["selected_modalities"] = list(effective_plan.directive.plugin_ids)
        generation_constraints = dict(authoring.policy.generation_constraints)
        if effective_plan.directive.plugin_id != "text":
            generation_constraints["modality_plugin_id"] = (
                effective_plan.directive.plugin_id
            )
            generation_constraints["selected_modality"] = (
                effective_plan.directive.modality
            )
            generation_constraints["selected_modalities"] = list(
                effective_plan.directive.plugin_ids
            )
        curriculum_request = authoring.curriculum_request
        try:
            for modality_plugin in modality_chain:
                curriculum_request = modality_plugin.apply(
                    request=curriculum_request,
                    accessibility_requirements=effective_plan.accessibility_requirements,
                )
        except Exception as exc:
            degraded_reason = str(exc)
            fallback_kind = "text_modality_fallback"
            effective_plan = self._fallback_plan(
                resolved_plan=resolved_plan,
                reason=str(exc),
            )
            request_context["selected_modality"] = effective_plan.directive.modality
            request_context["modality_plugin_id"] = effective_plan.directive.plugin_id
            request_context["modality_composition_mode"] = (
                effective_plan.directive.composition_mode
            )
            request_context["selected_modalities"] = list(
                effective_plan.directive.plugin_ids
            )
            generation_constraints.pop("modality_plugin_id", None)
            generation_constraints.pop("selected_modality", None)
            generation_constraints["selected_modalities"] = list(
                effective_plan.directive.plugin_ids
            )
            curriculum_request = authoring.curriculum_request
        authoring = PreparedAuthoringRequest(
            policy=HarnessAuthoringPolicy(
                content_type=authoring.policy.content_type,
                prompt_guidance=authoring.policy.prompt_guidance,
                request_context=request_context,
                generation_constraints=generation_constraints,
            ),
            curriculum_request=curriculum_request,
        )
        self._record_trace(
            profile=profile,
            request=request,
            plan=effective_plan,
            degraded_reason=degraded_reason,
            fallback_kind=fallback_kind,
        )
        return PreparedContentGeneration(
            profile=profile,
            request=request,
            routing_plan=effective_plan,
            authoring=authoring,
        )

    def generate(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        routing_plan: ModalityRoutingPlan | None = None,
    ) -> GenerationResponse:
        prepared = self.prepare_generation(
            profile=profile,
            request=request,
            routing_plan=routing_plan,
        )
        return self.generate_prepared(prepared)

    def generate_prepared(
        self, prepared: PreparedContentGeneration
    ) -> GenerationResponse:
        return self.generation_engine.generate_prepared(
            profile=prepared.profile,
            request=prepared.request,
            route=prepared.routing_plan.route,
            prepared_authoring=prepared.authoring,
        )

    def stream_generate_prepared(
        self, prepared: PreparedContentGeneration
    ) -> Iterator[GenerationStreamEvent]:
        return self.generation_engine.stream_generate_prepared(
            profile=prepared.profile,
            request=prepared.request,
            route=prepared.routing_plan.route,
            prepared_authoring=prepared.authoring,
        )

    def _safe_text_chain(self):
        try:
            return self.modality_plugins.chain_for("text")
        except Exception:
            return ()

    def _fallback_plan(
        self, *, resolved_plan: ModalityRoutingPlan, reason: str
    ) -> ModalityRoutingPlan:
        return ModalityRoutingPlan(
            route=resolved_plan.route,
            pedagogical_move=resolved_plan.pedagogical_move,
            context_key=resolved_plan.context_key,
            directive=TextModalityDirective(),
            theme_family=resolved_plan.theme_family,
            locale=resolved_plan.locale,
            accessibility_requirements=list(resolved_plan.accessibility_requirements),
            rationale=[*resolved_plan.rationale, f"modality_fallback:{reason}"],
            inspection=resolved_plan.inspection,
        )

    def _record_trace(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        plan: ModalityRoutingPlan,
        degraded_reason: str | None,
        fallback_kind: str | None,
    ) -> None:
        if self.operational_observability_service is None:
            return
        degraded_mode = degraded_reason is not None
        self.operational_observability_service.record_trace(
            harness=HarnessBoundary.content_generation,
            operation="prepare_generation",
            status=(
                OperationalTraceStatus.degraded
                if degraded_mode
                else OperationalTraceStatus.success
            ),
            summary=(
                "Prepared content generation request with a text fallback after a modality plugin failure."
                if degraded_mode
                else "Prepared content generation request."
            ),
            student_id=str(profile.student_id),
            degraded_mode=degraded_mode,
            degraded_reason=degraded_reason,
            fallback_kind=fallback_kind,
            fallback_provenance=plan.directive.plugin_id if degraded_mode else None,
            reason_code="modality_plugin_failed" if degraded_mode else None,
            payload={
                "learning_session_id": request.learning_session_id,
                "selected_plugin_id": plan.directive.plugin_id,
                "selected_modality": plan.directive.modality,
                "requested_content_type": (
                    request.requested_content_type.value
                    if request.requested_content_type is not None
                    else None
                ),
                "target_kc_ids": list(request.target_kc_ids),
            },
        )
