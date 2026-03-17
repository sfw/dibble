from datetime import datetime, timezone
from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GeneratedContent,
    GeneratedBlock,
    GenerationMetadata,
    GenerationResponse,
    InterventionType,
    RouteCalibrationSummary,
)
from dibble.services.predictive_content_warming import PredictiveContentWarmer


def test_predictive_content_warmer_plans_follow_ups_for_worked_examples():
    generated_content = _build_generated_content(
        content_type="worked_example",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "worked_example",
        },
    )

    plan = PredictiveContentWarmer(content_warmer=None).plan_follow_ups(generated_content)

    assert plan.content_types == ["practice_problem", "assessment_probe"]
    assert len(plan.requests) == 2
    assert plan.requests[0].predictive_warm is True
    assert plan.requests[0].source_generation_id == generated_content.generation_id
    assert plan.requests[0].learning_session_id == "session-1"
    assert plan.requests[0].target_kc_ids == ["KC-1"]
    assert plan.requests[1].intent == "assessment"


def test_predictive_content_warmer_skips_existing_predictive_content():
    generated_content = _build_generated_content(
        content_type="practice_problem",
        request_context={
            "is_predictive_warm": True,
            "selected_content_type": "practice_problem",
            "source_generation_id": "source-gen",
        },
    )

    plan = PredictiveContentWarmer(content_warmer=None).plan_follow_ups(generated_content)

    assert plan.requests == []
    assert plan.content_types == []


def test_predictive_content_warmer_uses_adaptive_follow_up_selection_for_negative_practice():
    generated_content = _build_generated_content(
        content_type="practice_problem",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "practice_problem",
            "mode_calibration": {"support_bias": -1},
        },
    )
    generated_content.response.route.calibration = {
        "signal": "negative",
        "source": "progress_profile",
        "confidence": 0.78,
        "average_run_outcome_score": 0.42,
        "matched_run_count": 4,
        "positive_run_rate": 0.0,
        "negative_run_rate": 0.75,
        "progress_signal": "declining",
        "progress_delta": -0.14,
    }
    generated_content.response.route.calibration = RouteCalibrationSummary.model_validate(
        generated_content.response.route.calibration
    )

    plan = PredictiveContentWarmer(content_warmer=None).plan_follow_ups(generated_content)

    assert plan.content_types == ["worked_example"]


def test_predictive_content_warmer_uses_strategy_trajectory_for_relapsing_practice():
    generated_content = _build_generated_content(
        content_type="practice_problem",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "practice_problem",
            "mode_calibration": {
                "support_bias": 0,
                "strategy_trajectory_state": "relapsing",
                "strategy_recommended_next_action": "rebuild_prerequisite",
                "strategy_relapse_risk": 0.71,
            },
        },
    )

    plan = PredictiveContentWarmer(content_warmer=None).plan_follow_ups(generated_content)

    assert plan.content_types == ["remedial_micro_module"]


def test_predictive_content_warmer_respects_progression_hold_for_practice():
    generated_content = _build_generated_content(
        content_type="practice_problem",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "practice_problem",
            "progression": {
                "action": "hold_target",
                "confidence": 0.72,
                "observation_count": 2,
                "assessment_count": 0,
            },
        },
    )

    plan = PredictiveContentWarmer(content_warmer=None).plan_follow_ups(generated_content)

    assert plan.content_types == ["practice_problem"]


def test_predictive_content_warmer_uses_explicit_transfer_target_for_transfer_check():
    generated_content = _build_generated_content(
        content_type="practice_problem",
        request_context={
            "learning_session_id": "session-transfer",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "practice_problem",
            "progression": {
                "action": "attempt_transfer",
                "target_stage": "transfer",
                "applied_target_kc_ids": ["KC-1"],
                "transfer_target_kc_ids": ["KC-3"],
                "confidence": 0.76,
            },
        },
    )

    plan = PredictiveContentWarmer(content_warmer=None).plan_follow_ups(generated_content)

    assert plan.content_types == ["assessment_probe"]
    assert plan.requests[0].target_kc_ids == ["KC-3"]


def test_predictive_content_warmer_targets_primary_sequence_kc_for_repair_follow_up():
    generated_content = _build_generated_content(
        content_type="remedial_micro_module",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1", "KC-2"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "remedial_micro_module",
            "mode_calibration": {"support_bias": 0, "strategy_sequence_action": "hold_repair_target"},
            "sequencing": {
                "action": "hold_repair_target",
                "primary_kc_id": "KC-1",
                "ordered_kc_ids": ["KC-1", "KC-2"],
                "deferred_kc_ids": ["KC-2"],
            },
        },
    )

    plan = PredictiveContentWarmer(content_warmer=None).plan_follow_ups(generated_content)

    assert plan.content_types == ["practice_problem"]
    assert plan.requests[0].target_kc_ids == ["KC-1"]


def _build_generated_content(*, content_type: str, request_context: dict[str, object]) -> GeneratedContent:
    student_id = uuid4()
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    metadata = GenerationMetadata(quality_score=0.8, validation_passed=True, grounding_count=1)
    response = GenerationResponse(
        student_id=student_id,
        route=route,
        blocks=[GeneratedBlock(kind="summary", title="Summary", body="Example body.")],
        curriculum_context=["Equivalent fractions"],
        grounding=[],
        safety_notes=["test"],
        generation_id="gen-1",
        generation_metadata=metadata,
    )
    return GeneratedContent(
        generation_id="gen-1",
        student_id=student_id,
        content_type=content_type,
        request_context=request_context,
        response=response,
        quality=metadata,
        created_at=datetime.now(timezone.utc),
    )
