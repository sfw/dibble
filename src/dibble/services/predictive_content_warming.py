from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.generation import (
    ContentIntent,
    ContentWarmResult,
    GeneratedContent,
    GenerationRequest,
    RequestedContentType,
)
from dibble.services.content_warmer import ContentWarmer
from dibble.services.predictive_next_step_planner import PredictiveNextStepPlanner


@dataclass(frozen=True, slots=True)
class PredictiveWarmPlan:
    requests: list[GenerationRequest]
    content_types: list[str]
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class PredictiveWarmOutcome:
    plan: PredictiveWarmPlan
    result: ContentWarmResult


@dataclass(slots=True)
class PredictiveContentWarmer:
    content_warmer: ContentWarmer
    next_step_planner: PredictiveNextStepPlanner = field(
        default_factory=PredictiveNextStepPlanner
    )

    def warm_follow_ups(
        self, generated_content: GeneratedContent
    ) -> PredictiveWarmOutcome | None:
        plan = self.plan_follow_ups(generated_content)
        if not plan.requests:
            return None
        result = self.content_warmer.warm(plan.requests)
        return PredictiveWarmOutcome(plan=plan, result=result)

    def plan_follow_ups(
        self, generated_content: GeneratedContent
    ) -> PredictiveWarmPlan:
        request_context = generated_content.request_context
        if bool(request_context.get("is_predictive_warm")):
            return PredictiveWarmPlan(requests=[], content_types=[], reasons=[])

        target_kc_ids = _string_list(request_context.get("target_kc_ids"))
        target_lo_ids = _string_list(request_context.get("target_lo_ids"))
        curriculum_context = _string_list(request_context.get("curriculum_context"))
        learning_session_id = _string_or_none(
            request_context.get("learning_session_id")
        )
        requested_types = self.next_step_planner.plan(generated_content)
        requests = [
            GenerationRequest(
                student_id=generated_content.student_id,
                learning_session_id=learning_session_id,
                target_kc_ids=self._target_kc_ids_for_follow_up(
                    predicted_type=predicted_type,
                    default_target_kc_ids=target_kc_ids,
                    request_context=request_context,
                ),
                target_lo_ids=target_lo_ids,
                intent=_intent_for_content_type(predicted_type),
                requested_content_type=predicted_type,
                curriculum_context=curriculum_context,
                predictive_warm=True,
                warm_reason=reason,
                source_generation_id=generated_content.generation_id,
            )
            for predicted_type, reason in requested_types
        ]
        return PredictiveWarmPlan(
            requests=requests,
            content_types=[
                item.requested_content_type.value
                for item in requests
                if item.requested_content_type is not None
            ],
            reasons=[
                item.warm_reason for item in requests if item.warm_reason is not None
            ],
        )

    def _target_kc_ids_for_follow_up(
        self,
        *,
        predicted_type: RequestedContentType,
        default_target_kc_ids: list[str],
        request_context: dict[str, object],
    ) -> list[str]:
        progression = request_context.get("progression")
        if isinstance(progression, dict):
            progression_action = str(
                progression.get("action", "stay_on_requested_target")
            )
            target_stage = str(progression.get("target_stage", "target"))
            applied_target_kc_ids = _string_list(
                progression.get("applied_target_kc_ids")
            )
            transfer_target_kc_ids = _string_list(
                progression.get("transfer_target_kc_ids")
            )
            if (
                predicted_type == RequestedContentType.assessment_probe
                and progression_action == "attempt_transfer"
            ):
                return (
                    transfer_target_kc_ids
                    or applied_target_kc_ids
                    or default_target_kc_ids
                )
            if predicted_type in {
                RequestedContentType.practice_problem,
                RequestedContentType.worked_example,
                RequestedContentType.remedial_micro_module,
            } and target_stage in {"repair", "bridge"}:
                return applied_target_kc_ids[:1] or default_target_kc_ids
        sequencing = request_context.get("sequencing")
        if not isinstance(sequencing, dict):
            return default_target_kc_ids
        action = str(sequencing.get("action", "monitor"))
        ordered_kc_ids = _string_list(sequencing.get("ordered_kc_ids"))
        deferred_kc_ids = _string_list(sequencing.get("deferred_kc_ids"))
        if (
            predicted_type == RequestedContentType.assessment_probe
            and action == "attempt_transfer"
        ):
            return deferred_kc_ids or default_target_kc_ids
        if predicted_type in {
            RequestedContentType.practice_problem,
            RequestedContentType.worked_example,
            RequestedContentType.remedial_micro_module,
        } and action in {
            "rebuild_prerequisite_first",
            "hold_repair_target",
            "hold_bridge_target",
            "hold_target",
        }:
            return ordered_kc_ids[:1] or default_target_kc_ids
        return default_target_kc_ids


def _intent_for_content_type(content_type: RequestedContentType) -> ContentIntent:
    mapping = {
        RequestedContentType.micro_explanation: ContentIntent.explanation,
        RequestedContentType.worked_example: ContentIntent.explanation,
        RequestedContentType.practice_problem: ContentIntent.practice,
        RequestedContentType.remedial_micro_module: ContentIntent.remediation,
        RequestedContentType.assessment_probe: ContentIntent.assessment,
    }
    return mapping[content_type]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
