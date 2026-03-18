from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learner_state_signal import LearnerStateSignalService
from dibble.services.learning_state_recorder import LearningStateProfileRecorder
from dibble.storage import ensure_database


def test_learning_state_profile_recorder_persists_durable_state_targets(tmp_path):
    database_path = str(tmp_path / "learning-state-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    recorder = LearningStateProfileRecorder(audit_store=audit_store)
    student_id = str(uuid4())

    summary_event = audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-4",
            "intent": "practice",
            "learning_session_id": "session-4",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "run_summary_score": 0.84,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.79,
        },
    )
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=student_id,
        payload={
            "source_run_summary_event_id": summary_event.event_id,
            "average_run_outcome_score": 0.82,
            "average_run_confidence": 0.78,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "positive_run_rate": 0.75,
            "negative_run_rate": 0.0,
            "progress_delta": 0.12,
            "progress_signal": "improving",
        },
    )
    audit_store.append(
        event_type="learning.strategy.profile",
        status="success",
        student_id=student_id,
        payload={
            "source_run_summary_event_id": summary_event.event_id,
            "average_run_outcome_score": 0.82,
            "average_run_confidence": 0.78,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "progress_signal": "improving",
            "progress_delta": 0.12,
            "strategy_signal": "independence_ready",
            "strategy_support_bias": 1,
            "strategy_trajectory_state": "accelerating",
        },
    )

    recorded = recorder.record_from_summary_events(summary_events=[summary_event])

    assert len(recorded) == 1
    profile_event = recorded[0]
    assert profile_event.event_type == "learning.state.profile"
    assert (
        profile_event.payload["source_run_summary_event_id"] == summary_event.event_id
    )
    assert profile_event.payload["state_profile_signal"] == "independence_ready"
    assert profile_event.payload["engagement"] in {"medium", "high"}
    assert profile_event.payload["frustration"] in {"none", "low"}
    assert profile_event.payload["total_load"] < 0.6
    assert profile_event.payload["confidence_calibration"] > 0.6
    assert profile_event.payload["self_monitoring"] > 0.6
    assert profile_event.payload["affective_reliability"] > 0.4
    assert profile_event.payload["load_reliability"] > 0.5
    assert profile_event.payload["recovery_stability"] > 0.6
    assert profile_event.payload["overload_risk"] < 0.5
    assert profile_event.payload["metacognitive_reliability"] > 0.6


def test_learner_state_signal_service_prefers_matching_state_profiles(tmp_path):
    database_path = str(tmp_path / "learning-state-profile-signal.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.44,
            "average_run_confidence": 0.74,
            "matched_run_count": 5,
            "matched_session_count": 3,
            "progress_signal": "declining",
            "progress_delta": -0.16,
            "strategy_signal": "support_intensive",
            "strategy_trajectory_state": "relapsing",
            "state_profile_signal": "support_needed",
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.74,
            "confidence_calibration": 0.36,
            "help_seeking": "high",
            "self_monitoring": 0.41,
            "recovery_stability": 0.28,
            "overload_risk": 0.82,
            "metacognitive_reliability": 0.34,
            "state_profile_rationale": "Recent outcomes are slipping across sessions.",
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
        }
    )
    summary = LearnerStateSignalService(audit_store=audit_store).state_for(
        student_id=request.student_id,
        request=request,
    )

    assert summary.source == "state_profile"
    assert summary.signal == "support_needed"
    assert summary.progress_signal == "declining"
    assert summary.strategy_signal == "support_intensive"
    assert summary.frustration == "high"
    assert summary.total_load == 0.74
    assert summary.confidence_calibration == 0.36
    assert summary.affective_reliability == 0.0
    assert summary.load_reliability == 0.0
    assert summary.recovery_stability == 0.28
    assert summary.overload_risk == 0.82
    assert summary.metacognitive_reliability == 0.34
