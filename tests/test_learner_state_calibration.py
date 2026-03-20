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
from dibble.services.learner_state_signal import LearnerStateSignalService
from dibble.services.learner_state_calibration import LearnerStateCalibrator
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def test_learner_state_calibrator_strengthens_metacognition_after_positive_run(
    tmp_path,
):
    database_path = str(tmp_path / "learner-state-positive.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
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
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
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
    assert result.state.metacognitive_state.help_seeking in {
        SignalLevel.none,
        SignalLevel.low,
    }


def test_learner_state_calibrator_reduces_metacognitive_readiness_after_negative_run(
    tmp_path,
):
    database_path = str(tmp_path / "learner-state-negative.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
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
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
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
    assert result.state.metacognitive_state.help_seeking in {
        SignalLevel.medium,
        SignalLevel.high,
    }


def test_learner_state_calibrator_leaves_state_unchanged_without_durable_signal(
    tmp_path,
):
    database_path = str(tmp_path / "learner-state-insufficient.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
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


def test_learner_state_calibrator_blends_durable_state_profile_when_available(tmp_path):
    database_path = str(tmp_path / "learner-state-profile-calibration.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.85,
            "average_run_confidence": 0.8,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "progress_signal": "improving",
            "progress_delta": 0.14,
            "strategy_signal": "independence_ready",
            "strategy_trajectory_state": "accelerating",
            "state_profile_signal": "independence_ready",
            "engagement": "high",
            "frustration": "none",
            "total_load": 0.42,
            "confidence_calibration": 0.78,
            "help_seeking": "low",
            "self_monitoring": 0.8,
            "affective_reliability": 0.82,
            "load_reliability": 0.76,
            "recovery_stability": 0.81,
            "overload_risk": 0.32,
            "metacognitive_reliability": 0.8,
            "state_profile_rationale": "Recent outcomes stay strong across sessions.",
        },
    )

    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
    )
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=AffectiveState(
            engagement=SignalLevel.medium,
            frustration=SignalLevel.medium,
            confidence=0.48,
        ),
        cognitive_load=CognitiveLoadState(
            intrinsic_load=0.42,
            extraneous_load=0.34,
            germane_load=0.38,
            total_load=0.66,
            capacity_utilization=0.7,
        ),
        metacognitive_state=MetacognitiveState(
            confidence_calibration=0.46,
            help_seeking=SignalLevel.medium,
            help_seeking_effectiveness=0.44,
            self_monitoring=0.48,
        ),
        observation_count=3,
    )

    result = calibrator.calibrate(
        student_id=student_id,
        observation=LearnerObservationCreate(
            response_time_ms=9000,
            task_type="practice",
            support_level="medium",
            target_kc_ids=["KC-1"],
        ),
        inferred_state=inferred_state,
    )

    assert result.applied is True
    assert result.signal == "independence_ready"
    assert result.source == "state_profile"
    assert result.matched_session_count == 3
    assert result.recovery_stability == 0.81
    assert result.overload_risk == 0.32
    assert result.metacognitive_reliability == 0.8
    assert result.state.affective_state.engagement == SignalLevel.high
    assert result.state.affective_state.frustration == SignalLevel.low


def test_learner_state_calibrator_skips_durable_independence_when_current_observation_is_sharply_strained(
    tmp_path,
):
    database_path = str(tmp_path / "learner-state-profile-strain-guard.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.84,
            "average_run_confidence": 0.81,
            "matched_run_count": 5,
            "matched_session_count": 4,
            "progress_signal": "improving",
            "progress_delta": 0.16,
            "strategy_signal": "independence_ready",
            "strategy_trajectory_state": "accelerating",
            "state_profile_signal": "independence_ready",
            "engagement": "high",
            "frustration": "none",
            "total_load": 0.4,
            "confidence_calibration": 0.82,
            "help_seeking": "low",
            "self_monitoring": 0.83,
            "affective_reliability": 0.84,
            "load_reliability": 0.8,
            "recovery_stability": 0.86,
            "overload_risk": 0.24,
            "metacognitive_reliability": 0.84,
        },
    )
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "generation_id": "gen-1",
            "target_kc_ids": ["KC-1"],
            "content_type": "practice_problem",
            "prompt_template_name": "practice_problem.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.8,
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
            "task_type": "practice",
            "target_kc_ids": ["KC-1"],
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.92,
            "confidence_calibration": 0.24,
            "help_seeking": "high",
        },
    )

    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
    )
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=AffectiveState(
            engagement=SignalLevel.low,
            frustration=SignalLevel.high,
            confidence=0.3,
        ),
        cognitive_load=CognitiveLoadState(
            intrinsic_load=0.58,
            extraneous_load=0.42,
            germane_load=0.26,
            total_load=0.84,
            capacity_utilization=0.86,
        ),
        metacognitive_state=MetacognitiveState(
            confidence_calibration=0.34,
            help_seeking=SignalLevel.high,
            help_seeking_effectiveness=0.36,
            self_monitoring=0.4,
        ),
        observation_count=2,
    )

    result = calibrator.calibrate(
        student_id=student_id,
        observation=LearnerObservationCreate(
            response_time_ms=34000,
            hints_used=3,
            error_count=3,
            completed=False,
            task_type="practice",
            support_level="low",
            expected_duration_ms=16000,
            target_kc_ids=["KC-1"],
        ),
        inferred_state=inferred_state,
    )

    assert result.source != "state_profile"
    assert result.overload_risk >= 0.7
    assert result.state.cognitive_load.total_load == 0.84
    assert result.state.metacognitive_state.help_seeking == SignalLevel.high
    assert result.state.metacognitive_state.confidence_calibration < 0.34
    assert result.state.metacognitive_state.self_monitoring < 0.4


def test_learner_state_calibrator_does_not_force_support_profile_over_productive_struggle(
    tmp_path,
):
    database_path = str(tmp_path / "learner-state-productive-struggle.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "matched_run_count": 4,
            "matched_session_count": 3,
            "state_profile_signal": "support_needed",
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.78,
            "confidence_calibration": 0.34,
            "help_seeking": "high",
            "self_monitoring": 0.28,
            "affective_reliability": 0.76,
            "load_reliability": 0.78,
            "recovery_stability": 0.32,
            "overload_risk": 0.82,
            "metacognitive_reliability": 0.7,
        },
    )
    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
    )
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=AffectiveState(
            engagement=SignalLevel.medium, frustration=SignalLevel.low, confidence=0.6
        ),
        cognitive_load=CognitiveLoadState(total_load=0.42, capacity_utilization=0.48),
        metacognitive_state=MetacognitiveState(
            confidence_calibration=0.58,
            help_seeking=SignalLevel.low,
            help_seeking_effectiveness=0.58,
            self_monitoring=0.56,
        ),
        current_evidence={
            "signal": "productive_struggle",
            "confidence": 0.74,
            "challenge_exposure": 1.0,
            "productive_struggle_score": 0.76,
            "overload_score": 0.36,
            "disengagement_score": 0.18,
            "support_dependence_score": 0.1,
            "rationale": "Recent low-support work looks like productive struggle.",
        },
        observation_count=2,
    )

    result = calibrator.calibrate(
        student_id=student_id,
        observation=LearnerObservationCreate(
            response_time_ms=16000,
            task_type="practice",
            support_level="low",
            target_kc_ids=["KC-1"],
        ),
        inferred_state=inferred_state,
    )

    assert result.applied is False
    assert result.current_evidence_signal == "productive_struggle"


def test_learner_state_calibrator_blocks_release_profile_when_current_evidence_shows_overload(
    tmp_path,
):
    database_path = str(tmp_path / "learner-state-overload-guardrail.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "matched_run_count": 4,
            "matched_session_count": 3,
            "state_profile_signal": "independence_ready",
            "engagement": "high",
            "frustration": "none",
            "total_load": 0.34,
            "confidence_calibration": 0.78,
            "help_seeking": "low",
            "self_monitoring": 0.8,
            "affective_reliability": 0.82,
            "load_reliability": 0.74,
            "recovery_stability": 0.84,
            "overload_risk": 0.22,
            "metacognitive_reliability": 0.78,
        },
    )
    calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
    )
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=AffectiveState(
            engagement=SignalLevel.medium,
            frustration=SignalLevel.medium,
            confidence=0.4,
        ),
        cognitive_load=CognitiveLoadState(total_load=0.74, capacity_utilization=0.82),
        metacognitive_state=MetacognitiveState(
            confidence_calibration=0.42,
            help_seeking=SignalLevel.high,
            help_seeking_effectiveness=0.32,
            self_monitoring=0.38,
        ),
        current_evidence={
            "signal": "overload",
            "confidence": 0.78,
            "challenge_exposure": 0.5,
            "productive_struggle_score": 0.32,
            "overload_score": 0.82,
            "disengagement_score": 0.4,
            "support_dependence_score": 0.22,
            "rationale": "Recent observations look overloaded.",
        },
        observation_count=2,
    )

    result = calibrator.calibrate(
        student_id=student_id,
        observation=LearnerObservationCreate(
            response_time_ms=28000,
            task_type="practice",
            support_level="low",
            target_kc_ids=["KC-1"],
        ),
        inferred_state=inferred_state,
    )

    assert result.applied is False
    assert result.current_evidence_signal == "overload"
