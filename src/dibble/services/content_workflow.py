from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentWarmRequest,
    ContentWarmResult,
    GeneratedContent,
    GenerationRequest,
    RemedialTriggerRequest,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import RouterPlugin
from dibble.services.content_warmer import ContentWarmer
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generation_modes import build_generation_mode_plan
from dibble.services.protocols import AuditStore, ProfileStore
from dibble.services.remediation_planner import RemediationPlanner


class LearnerProfileNotFoundError(LookupError):
    def __init__(self, student_id: UUID) -> None:
        super().__init__(f"Learner profile not found for student_id {student_id}.")
        self.student_id = student_id


@dataclass(slots=True)
class ContentWorkflowService:
    profile_store: ProfileStore
    router: RouterPlugin
    generation_engine: GenerationEngine
    content_warmer: ContentWarmer
    remediation_planner: RemediationPlanner
    audit_store: AuditStore

    def decide_route(self, request: GenerationRequest) -> AdaptiveRouteDecision:
        profile = self._load_profile(request.student_id)
        decision = self.router.route(profile, request)
        self.audit_store.append(
            event_type="adaptive.decide",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "intervention_type": decision.intervention_type.value,
                "delivery_mode": decision.delivery_mode.value,
                "scaffolding_level": decision.scaffolding_level,
                "reason_count": len(decision.reasons),
                "calibration_signal": decision.calibration.signal if decision.calibration is not None else None,
                "calibration_source": decision.calibration.source if decision.calibration is not None else None,
                "calibration_confidence": decision.calibration.confidence if decision.calibration is not None else 0.0,
                "calibration_run_count": (
                    decision.calibration.matched_run_count if decision.calibration is not None else 0
                ),
                "calibration_outcome_score": (
                    decision.calibration.average_run_outcome_score if decision.calibration is not None else None
                ),
            },
        )
        return decision

    def generate_content(self, request: GenerationRequest) -> GeneratedContent:
        profile = self._load_profile(request.student_id)
        response = self.generation_engine.generate(profile, request)
        plan = build_generation_mode_plan(profile, request, response.route)
        metadata = response.generation_metadata
        if metadata is None or response.generation_id is None:
            raise RuntimeError("Generated content metadata was not available.")

        generated_content = GeneratedContent(
            generation_id=response.generation_id,
            student_id=response.student_id,
            content_type=plan.content_type.value,
            request_context=plan.request_context,
            response=response,
            quality=metadata,
            created_at=response.generated_at,
        )
        self.audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "learning_session_id": request.learning_session_id,
                "content_type": generated_content.content_type,
                "generation_id": generated_content.generation_id,
                "intervention_type": response.route.intervention_type.value,
                "delivery_mode": response.route.delivery_mode.value,
                "grounding_count": len(response.grounding),
                "generated_block_count": len(response.blocks),
                "validation_issue_count": len(response.validation_issues),
                "validation_passed": metadata.validation_passed,
                "cache_hit": metadata.cache_hit,
                "quality_score": metadata.quality_score,
                "target_kc_ids": request.target_kc_ids,
                "target_lo_ids": request.target_lo_ids,
                "scaffolding_level": response.route.scaffolding_level,
                "route_calibration_signal": (
                    response.route.calibration.signal if response.route.calibration is not None else None
                ),
                "route_calibration_source": (
                    response.route.calibration.source if response.route.calibration is not None else None
                ),
                "route_calibration_confidence": (
                    response.route.calibration.confidence if response.route.calibration is not None else 0.0
                ),
                "prompt_template_name": metadata.prompt_template_name,
                "prompt_template_version": metadata.prompt_template_version,
                "prompt_template_variant": metadata.prompt_template_variant,
            },
        )
        return generated_content

    def warm_content(self, request: ContentWarmRequest) -> ContentWarmResult:
        warmed = self.content_warmer.warm(request.requests)
        self.audit_store.append(
            event_type="content.warm",
            status="success",
            payload={
                "total_requests": warmed.total_requests,
                "cache_hits": warmed.cache_hits,
                "cache_misses": warmed.cache_misses,
            },
        )
        return warmed

    def trigger_remedial_content(self, request: RemedialTriggerRequest) -> GeneratedContent:
        profile = self._load_profile(request.student_id)
        plan = self.remediation_planner.plan(
            profile,
            request.target_kc_id,
            misconception_description=request.misconception_description,
            curriculum_context=request.curriculum_context,
        )
        generation_request = GenerationRequest(
            student_id=request.student_id,
            target_kc_ids=plan.focus_kc_ids,
            intent="remediation",
            requested_content_type="remedial_micro_module",
            learner_prompt=(
                f"{request.learner_prompt} Step back through prerequisite components before returning to the target."
                if request.learner_prompt
                else "Step back through prerequisite components before returning to the target."
            ),
            curriculum_context=[request.misconception_description, *request.curriculum_context],
        )
        generated_content = self.generate_content(generation_request)
        enriched_request_context = {
            **generated_content.request_context,
            "target_kc_id": request.target_kc_id,
            "focus_kc_ids": plan.focus_kc_ids,
            "prerequisite_kc_ids": plan.prerequisite_kc_ids,
            "misconception_description": request.misconception_description,
            "misconception_signals": [signal.model_dump(mode="json") for signal in plan.misconception_signals],
            "remediation_rationale": plan.rationale,
        }
        enriched_content = generated_content.model_copy(update={"request_context": enriched_request_context})
        self.audit_store.append(
            event_type="remediation.trigger",
            status="success",
            student_id=str(request.student_id),
            payload={
                "target_kc_id": request.target_kc_id,
                "focus_kc_ids": plan.focus_kc_ids,
                "prerequisite_kc_ids": plan.prerequisite_kc_ids,
                "misconception_signal_count": len(plan.misconception_signals),
                "misconception_signals": [signal.model_dump(mode="json") for signal in plan.misconception_signals],
                "generation_id": enriched_content.generation_id,
                "rationale": plan.rationale,
            },
        )
        return enriched_content

    def load_profile(self, student_id: UUID) -> LearnerProfile:
        return self._load_profile(student_id)

    def _load_profile(self, student_id: UUID) -> LearnerProfile:
        profile = self.profile_store.get(student_id)
        if profile is None:
            raise LearnerProfileNotFoundError(student_id)
        return profile
