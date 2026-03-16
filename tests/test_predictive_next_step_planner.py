from datetime import datetime, timezone
from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationResponse,
    InterventionType,
    RequestedContentType,
    RouteCalibrationSummary,
)
from dibble.services.predictive_next_step_planner import PredictiveNextStepPlanner


def test_predictive_next_step_planner_uses_worked_example_after_negative_practice():
    generated_content = _build_generated_content(
        content_type="practice_problem",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "practice_problem",
            "mode_calibration": {"support_bias": -1},
        },
        route_calibration=RouteCalibrationSummary(
            signal="negative",
            source="progress_profile",
            confidence=0.78,
            average_run_outcome_score=0.42,
            matched_run_count=4,
            progress_signal="declining",
            progress_delta=-0.14,
        ),
    )

    plan = PredictiveNextStepPlanner().plan(generated_content)

    assert plan == [
        (
            RequestedContentType.worked_example,
            "Recent struggle suggests warming a modeled example before another independent step.",
        )
    ]


def test_predictive_next_step_planner_skips_assessment_after_declining_worked_example():
    generated_content = _build_generated_content(
        content_type="worked_example",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "worked_example",
            "mode_calibration": {"support_bias": -1},
        },
        route_calibration=RouteCalibrationSummary(
            signal="mixed",
            source="progress_profile",
            confidence=0.75,
            average_run_outcome_score=0.61,
            matched_run_count=4,
            progress_signal="declining",
            progress_delta=-0.11,
        ),
    )

    plan = PredictiveNextStepPlanner().plan(generated_content)

    assert [content_type.value for content_type, _ in plan] == ["practice_problem"]


def test_predictive_next_step_planner_adds_assessment_after_improving_remediation():
    generated_content = _build_generated_content(
        content_type="remedial_micro_module",
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "selected_content_type": "remedial_micro_module",
            "mode_calibration": {"support_bias": 1},
        },
        route_calibration=RouteCalibrationSummary(
            signal="positive",
            source="progress_profile",
            confidence=0.81,
            average_run_outcome_score=0.79,
            matched_run_count=5,
            progress_signal="improving",
            progress_delta=0.17,
        ),
    )

    plan = PredictiveNextStepPlanner().plan(generated_content)

    assert [content_type.value for content_type, _ in plan] == ["practice_problem", "assessment_probe"]


def _build_generated_content(
    *,
    content_type: str,
    request_context: dict[str, object],
    route_calibration: RouteCalibrationSummary,
) -> GeneratedContent:
    student_id = uuid4()
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
        calibration=route_calibration,
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
