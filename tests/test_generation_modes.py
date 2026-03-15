from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.services.generation_modes import build_generation_mode_plan
from tests.support import build_profile


def test_generation_mode_plan_assigns_support_difficulty_for_low_mastery():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.3,
            kc_mastery={"KC-1": 0.2},
            engagement="medium",
        )
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="practice")
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.practice_problem
    assert plan.request_context["difficulty_band"] == "support"
    assert "support difficulty" in plan.prompt_guidance


def test_generation_mode_plan_assigns_completion_fading_for_worked_examples():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.45,
            kc_mastery={"KC-1": 0.55},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        requested_content_type="worked_example",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.worked_example
    assert plan.request_context["fading_strategy"] == "completion"
    assert plan.request_context["worked_steps_visible"] == 2
    assert "final step" in plan.prompt_guidance
