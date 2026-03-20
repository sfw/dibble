from uuid import uuid4

from dibble.models.observations import LearnerObservation
from dibble.models.profile import SignalLevel
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learner_state_signal import LearnerStateSignalService
from dibble.services.sqlite_connection import create_connection
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.storage import ensure_database


def test_state_inference_detects_high_frustration_and_load():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=28000,
            hints_used=3,
            error_count=3,
            pause_count=4,
            modality_switches=2,
            completed=False,
            confidence=0.2,
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=32000,
            hints_used=2,
            error_count=2,
            pause_count=3,
            modality_switches=1,
            completed=False,
            confidence=0.25,
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.affective_state.frustration == SignalLevel.high
    assert inferred.affective_state.confusion in {SignalLevel.medium, SignalLevel.high}
    assert inferred.cognitive_load.total_load >= 0.6
    assert inferred.metacognitive_state.help_seeking in {
        SignalLevel.medium,
        SignalLevel.high,
    }
    assert inferred.metacognitive_state.confidence_calibration >= 0.7
    assert inferred.metacognitive_state.self_monitoring <= 0.5
    assert inferred.observation_count == 2


def test_state_inference_tracks_calibrated_confidence_when_performance_matches():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=9000,
            hints_used=1,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.9,
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=11000,
            hints_used=0,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.85,
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.metacognitive_state.confidence_calibration >= 0.8
    assert inferred.metacognitive_state.help_seeking in {
        SignalLevel.none,
        SignalLevel.low,
    }
    assert inferred.metacognitive_state.self_monitoring >= 0.6


def test_state_inference_is_task_aware_for_supported_vs_assessment_work():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    worked_example = LearnerObservation(
        observation_id="obs-1",
        student_id=student_id,
        response_time_ms=18000,
        hints_used=1,
        error_count=1,
        pause_count=1,
        modality_switches=1,
        completed=True,
        confidence=0.7,
        task_type="worked_example",
        support_level="high",
        expected_duration_ms=18000,
    )
    assessment = LearnerObservation(
        observation_id="obs-2",
        student_id=student_id,
        response_time_ms=18000,
        hints_used=1,
        error_count=1,
        pause_count=1,
        modality_switches=1,
        completed=True,
        confidence=0.7,
        task_type="assessment",
        support_level="low",
        expected_duration_ms=18000,
    )

    supported = service.infer(student_id=student_id, observations=[worked_example])
    assessed = service.infer(student_id=student_id, observations=[assessment])

    assert assessed.cognitive_load.total_load > supported.cognitive_load.total_load
    assert assessed.affective_state.confusion.value in {"low", "medium", "high"}
    assert assessed.metacognitive_state.help_seeking in {
        SignalLevel.medium,
        SignalLevel.high,
    }
    assert supported.metacognitive_state.help_seeking in {
        SignalLevel.none,
        SignalLevel.low,
    }


def test_state_inference_blends_high_confidence_durable_state_profile(tmp_path):
    database_path = str(tmp_path / "state-inference-durable.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.42,
            "average_run_confidence": 0.82,
            "matched_run_count": 6,
            "matched_session_count": 4,
            "state_profile_signal": "support_needed",
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.82,
            "confidence_calibration": 0.34,
            "help_seeking": "high",
            "self_monitoring": 0.32,
            "affective_reliability": 0.74,
            "load_reliability": 0.82,
            "recovery_stability": 0.34,
            "overload_risk": 0.84,
            "metacognitive_reliability": 0.78,
        },
    )
    service = LearnerStateInferenceService(
        state_profile_signal_service=LearnerStateSignalService(audit_store=audit_store)
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=18000,
            hints_used=1,
            error_count=1,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.7,
            task_type="practice",
            support_level="medium",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=17000,
            hints_used=1,
            error_count=1,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.68,
            task_type="practice",
            support_level="medium",
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.cognitive_load.total_load >= 0.55
    assert inferred.metacognitive_state.confidence_calibration < 0.8
    assert inferred.metacognitive_state.self_monitoring < 0.7


def test_state_inference_ignores_weak_mismatched_durable_profile(tmp_path):
    database_path = str(tmp_path / "state-inference-durable-mismatch.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.15,
            "average_run_confidence": 0.61,
            "matched_run_count": 2,
            "matched_session_count": 2,
            "state_profile_signal": "support_needed",
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.9,
            "confidence_calibration": 0.2,
            "help_seeking": "high",
            "self_monitoring": 0.22,
            "affective_reliability": 0.46,
            "load_reliability": 0.5,
            "recovery_stability": 0.36,
            "overload_risk": 0.88,
            "metacognitive_reliability": 0.42,
        },
    )
    baseline_service = LearnerStateInferenceService()
    blended_service = LearnerStateInferenceService(
        state_profile_signal_service=LearnerStateSignalService(audit_store=audit_store)
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=9000,
            hints_used=0,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.86,
            task_type="practice",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=10000,
            hints_used=0,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.84,
            task_type="assessment",
            support_level="low",
        ),
    ]

    baseline = baseline_service.infer(student_id=student_id, observations=observations)
    blended = blended_service.infer(student_id=student_id, observations=observations)

    assert blended.cognitive_load.total_load == baseline.cognitive_load.total_load
    assert (
        blended.metacognitive_state.self_monitoring
        == baseline.metacognitive_state.self_monitoring
    )


def test_state_inference_downweights_high_confidence_durable_profile_when_current_evidence_is_rich_and_contradictory(
    tmp_path,
):
    database_path = str(tmp_path / "state-inference-rich-current.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.88,
            "average_run_confidence": 0.87,
            "matched_run_count": 8,
            "matched_session_count": 5,
            "state_profile_signal": "independence_ready",
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.28,
            "confidence_calibration": 0.86,
            "help_seeking": "low",
            "self_monitoring": 0.84,
            "affective_reliability": 0.82,
            "load_reliability": 0.8,
            "recovery_stability": 0.8,
            "overload_risk": 0.22,
            "metacognitive_reliability": 0.83,
        },
    )
    baseline_service = LearnerStateInferenceService()
    blended_service = LearnerStateInferenceService(
        state_profile_signal_service=LearnerStateSignalService(audit_store=audit_store)
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=25000,
            hints_used=2,
            error_count=2,
            pause_count=2,
            modality_switches=1,
            completed=False,
            confidence=0.4,
            task_type="practice",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=27000,
            hints_used=3,
            error_count=2,
            pause_count=2,
            modality_switches=1,
            completed=False,
            confidence=0.38,
            task_type="assessment",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-3",
            student_id=student_id,
            response_time_ms=22000,
            hints_used=2,
            error_count=1,
            pause_count=1,
            modality_switches=1,
            completed=True,
            confidence=0.45,
            task_type="remediation",
            support_level="medium",
        ),
    ]

    baseline = baseline_service.infer(student_id=student_id, observations=observations)
    blended = blended_service.infer(student_id=student_id, observations=observations)

    assert (
        blended.cognitive_load.total_load >= baseline.cognitive_load.total_load - 0.04
    )
    assert (
        blended.metacognitive_state.self_monitoring
        <= baseline.metacognitive_state.self_monitoring + 0.06
    )
    assert blended.metacognitive_state.help_seeking in {
        SignalLevel.medium,
        SignalLevel.high,
    }


def test_state_inference_blends_durable_load_more_than_affect_when_reliability_is_dimension_specific(
    tmp_path,
):
    database_path = str(tmp_path / "state-inference-dimension-specific.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.5,
            "average_run_confidence": 0.84,
            "matched_run_count": 7,
            "matched_session_count": 4,
            "state_profile_signal": "support_needed",
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.86,
            "confidence_calibration": 0.4,
            "help_seeking": "high",
            "self_monitoring": 0.36,
            "affective_reliability": 0.22,
            "load_reliability": 0.86,
            "recovery_stability": 0.42,
            "overload_risk": 0.88,
            "metacognitive_reliability": 0.58,
        },
    )
    baseline_service = LearnerStateInferenceService()
    blended_service = LearnerStateInferenceService(
        state_profile_signal_service=LearnerStateSignalService(audit_store=audit_store)
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=15000,
            hints_used=1,
            error_count=1,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.72,
            task_type="practice",
            support_level="medium",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=16000,
            hints_used=1,
            error_count=1,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.7,
            task_type="practice",
            support_level="medium",
        ),
    ]

    baseline = baseline_service.infer(student_id=student_id, observations=observations)
    blended = blended_service.infer(student_id=student_id, observations=observations)

    assert (
        blended.cognitive_load.total_load - baseline.cognitive_load.total_load >= 0.08
    )
    assert (
        abs(
            _signal_rank(blended.affective_state.frustration)
            - _signal_rank(baseline.affective_state.frustration)
        )
        <= 1
    )


def _signal_rank(value: SignalLevel) -> int:
    return {
        SignalLevel.none: 0,
        SignalLevel.low: 1,
        SignalLevel.medium: 2,
        SignalLevel.high: 3,
    }[value]


def test_state_inference_marks_productive_struggle_for_low_support_recoverable_friction():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=17000,
            hints_used=1,
            error_count=1,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.62,
            task_type="practice",
            support_level="low",
            expected_duration_ms=15000,
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=18000,
            hints_used=1,
            error_count=1,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.58,
            task_type="assessment",
            support_level="low",
            expected_duration_ms=16000,
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.current_evidence is not None
    assert inferred.current_evidence.signal == "productive_struggle"
    assert inferred.current_evidence.challenge_exposure >= 0.5


def test_state_inference_marks_overload_for_heavy_pressure():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=32000,
            hints_used=3,
            error_count=3,
            pause_count=4,
            modality_switches=1,
            completed=False,
            confidence=0.18,
            task_type="practice",
            support_level="low",
            expected_duration_ms=16000,
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=28000,
            hints_used=2,
            error_count=2,
            pause_count=3,
            modality_switches=1,
            completed=False,
            confidence=0.22,
            task_type="assessment",
            support_level="low",
            expected_duration_ms=18000,
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.current_evidence is not None
    assert inferred.current_evidence.signal == "overload"
    assert inferred.current_evidence.confidence >= 0.58


def test_state_inference_marks_support_dependence_for_high_support_success():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=15000,
            hints_used=2,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.7,
            task_type="practice",
            support_level="high",
            expected_duration_ms=17000,
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=16000,
            hints_used=2,
            error_count=1,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.68,
            task_type="practice",
            support_level="high",
            expected_duration_ms=17000,
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.current_evidence is not None
    assert inferred.current_evidence.signal == "support_dependence"
    assert inferred.current_evidence.support_dependence_score >= 0.55
