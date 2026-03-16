from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationModeCalibration,
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
    assert plan.request_context["selection_mode"] == "intent_default"
    assert plan.request_context["requested_content_type"] is None
    assert plan.request_context["selected_content_type"] == "practice_problem"
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
    assert plan.request_context["selection_mode"] == "explicit"
    assert plan.request_context["requested_content_type"] == "worked_example"
    assert plan.request_context["selected_content_type"] == "worked_example"
    assert plan.request_context["fading_strategy"] == "completion"
    assert plan.request_context["worked_steps_visible"] == 2
    assert "final step" in plan.prompt_guidance


def test_generation_mode_plan_auto_selects_worked_example_for_high_help_seeking():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.35,
            kc_mastery={"KC-1": 0.58},
            engagement="medium",
            confidence_calibration=0.3,
            help_seeking="high",
        )
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="explanation")
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.worked_example
    assert plan.request_context["selection_mode"] == "adaptive"
    assert plan.request_context["requested_content_type"] is None
    assert plan.request_context["selected_content_type"] == "worked_example"
    assert "selection_rationale" in plan.request_context


def test_generation_mode_plan_assigns_independent_fading_for_stable_high_mastery_worked_example():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.3,
            kc_mastery={"KC-1": 0.88},
            engagement="high",
            confidence_calibration=0.82,
            help_seeking="low",
            self_monitoring=0.82,
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        requested_content_type="worked_example",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.stretch,
        delivery_mode=DeliveryMode.blended,
        scaffolding_level="low",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["fading_strategy"] == "independent"
    assert plan.request_context["worked_steps_visible"] == 1


def test_generation_mode_plan_uses_positive_mode_calibration_to_raise_practice_difficulty():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.3,
            kc_mastery={"KC-1": 0.2},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
        mode_calibration=GenerationModeCalibration(
            signal="positive",
            source="profile",
            confidence=0.78,
            matched_run_count=4,
            average_run_outcome_score=0.84,
            support_bias=1,
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["difficulty_band"] == "on_grade"
    assert plan.request_context["mode_calibration"]["support_bias"] == 1
    assert plan.request_context["mode_calibration_applied"] is True
    assert "on_grade difficulty" in plan.prompt_guidance


def test_generation_mode_plan_uses_negative_mode_calibration_to_increase_worked_example_support():
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
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="run_summary",
            confidence=0.81,
            matched_run_count=2,
            average_run_outcome_score=0.34,
            support_bias=-1,
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["fading_strategy"] == "full"
    assert plan.request_context["worked_steps_visible"] == 3
    assert plan.request_context["mode_calibration"]["source"] == "run_summary"
    assert plan.request_context["mode_calibration_applied"] is True
