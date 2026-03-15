from __future__ import annotations

from uuid import uuid4

from dibble.models.observations import InferredLearnerState, LearnerObservationCreate
from dibble.models.profile import (
    AffectiveState,
    CognitiveLoadState,
    MetacognitiveState,
    SignalLevel,
)
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learner_state_calibration import LearnerStateCalibrator
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.storage import ensure_database


def test_learner_state_calibrator_strengthens_metacognition_after_positive_run(tmp_path):
    database_path = str(tmp_path / "learner-state-positive.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "generation_id": "gen-1",
            "learning_session_id": "run-1",
            "target_kc_ids": ["KC-1"],
            "content_type": "practice_problem",
            "prompt_template_name": "practice_problem.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.78,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "gen-1",
            "learning_session_id": "run-1",
            "observed_content_type": "practice_problem",
            "task_type": "practice",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.22,
            "confidence_calibration": 0.86,
            "help_seeking": "low",
        },
    )

    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
    )
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=AffectiveState(),
        cognitive_load=CognitiveLoadState(),
        metacognitive_state=MetacognitiveState(
            confidence_calibration=0.52,
            help_seeking=SignalLevel.medium,
            help_seeking_effectiveness=0.5,
            self_monitoring=0.48,
        ),
        observation_count=1,
    )

    result = calibrator.calibrate(
        student_id=student_id,
        observation=LearnerObservationCreate(
            response_time_ms=10000,
            task_type="practice",
            support_level="medium",
            learning_session_id="run-1",
            generation_id="gen-2",
            target_kc_ids=["KC-1"],
        ),
        inferred_state=inferred_state,
    )

    assert result.applied is True
    assert result.signal == "positive"
    assert result.state.metacognitive_state.confidence_calibration > 0.52
    assert result.state.metacognitive_state.self_monitoring > 0.48
    assert result.state.metacognitive_state.help_seeking in {SignalLevel.none, SignalLevel.low}


def test_learner_state_calibrator_reduces_metacognitive_readiness_after_negative_run(tmp_path):
    database_path = str(tmp_path / "learner-state-negative.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "explanation",
            "generation_id": "gen-1",
            "target_kc_ids": ["KC-1"],
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.baseline",
            "prompt_template_variant": "baseline",
            "quality_score": 0.82,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "gen-1",
            "observed_content_type": "micro_explanation",
            "task_type": "explanation",
            "target_kc_ids": ["KC-1"],
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.9,
            "confidence_calibration": 0.2,
            "help_seeking": "high",
        },
    )

    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
    )
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=AffectiveState(),
        cognitive_load=CognitiveLoadState(),
        metacognitive_state=MetacognitiveState(
            confidence_calibration=0.7,
            help_seeking=SignalLevel.low,
            help_seeking_effectiveness=0.64,
            self_monitoring=0.66,
        ),
        observation_count=1,
    )

    result = calibrator.calibrate(
        student_id=student_id,
        observation=LearnerObservationCreate(
            response_time_ms=18000,
            task_type="explanation",
            support_level="low",
            target_kc_ids=["KC-1"],
        ),
        inferred_state=inferred_state,
    )

    assert result.applied is True
    assert result.signal == "negative"
    assert result.state.metacognitive_state.confidence_calibration < 0.7
    assert result.state.metacognitive_state.self_monitoring < 0.66
    assert result.state.metacognitive_state.help_seeking in {SignalLevel.medium, SignalLevel.high}


def test_learner_state_calibrator_leaves_state_unchanged_without_durable_signal(tmp_path):
    database_path = str(tmp_path / "learner-state-insufficient.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
    )
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=AffectiveState(),
        cognitive_load=CognitiveLoadState(),
        metacognitive_state=MetacognitiveState(
            confidence_calibration=0.6,
            help_seeking=SignalLevel.low,
            help_seeking_effectiveness=0.5,
            self_monitoring=0.6,
        ),
        observation_count=1,
    )

    result = calibrator.calibrate(
        student_id=student_id,
        observation=LearnerObservationCreate(
            response_time_ms=12000,
            task_type="practice",
            support_level="medium",
            target_kc_ids=["KC-1"],
        ),
        inferred_state=inferred_state,
    )

    assert result.applied is False
    assert result.signal == "insufficient"
    assert result.state == inferred_state
