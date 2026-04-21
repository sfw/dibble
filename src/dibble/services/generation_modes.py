from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import (
    AdaptiveRouteDecision,
    GenerationRequest,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.services.harness.authoring_rules import (
    PracticeProgressionPlan,
    WorkedExampleProgressionPlan,
    _append_socratic_guidance,
    _micro_explanation_guidance,
    _worked_example_guidance,
    _worked_steps_visible,
    apply_support_bias_to_difficulty_band,
    apply_support_bias_to_fading,
    plan_practice_progression,
    plan_worked_example_progression,
    resolve_content_type,
    select_content_type,
    select_practice_difficulty_band,
    select_worked_example_fading,
)


@dataclass(frozen=True, slots=True)
class GenerationModePlan:
    content_type: RequestedContentType
    prompt_guidance: str
    request_context: dict[str, object]


def build_generation_mode_plan(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
) -> GenerationModePlan:
    from dibble.services.harness.policy import HarnessAuthoringPolicyBuilder

    policy = HarnessAuthoringPolicyBuilder().build(
        profile=profile,
        request=request,
        route=route,
    )
    return GenerationModePlan(
        content_type=policy.content_type,
        prompt_guidance=policy.prompt_guidance,
        request_context=policy.request_context,
    )


__all__ = [
    "GenerationModePlan",
    "PracticeProgressionPlan",
    "WorkedExampleProgressionPlan",
    "build_generation_mode_plan",
    "resolve_content_type",
    "select_content_type",
    "select_practice_difficulty_band",
    "select_worked_example_fading",
    "apply_support_bias_to_difficulty_band",
    "apply_support_bias_to_fading",
    "plan_practice_progression",
    "plan_worked_example_progression",
    "_worked_example_guidance",
    "_worked_steps_visible",
    "_append_socratic_guidance",
    "_micro_explanation_guidance",
]
