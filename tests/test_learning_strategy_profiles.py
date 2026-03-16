from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learner_strategy_profiles import (
    LearnerStrategySignalService,
    LearningStrategyProfileRecorder,
)
from dibble.storage import ensure_database


def test_learning_strategy_profile_recorder_persists_support_intensive_signal(tmp_path):
    database_path = str(tmp_path / "learning-strategy-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    recorder = LearningStrategyProfileRecorder(audit_store=audit_store)
    student_id = str(uuid4())

    summary_event = audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "intent": "practice",
            "learning_session_id": "session-3",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "run_summary_score": 0.48,
            "run_calibration_signal": "negative",
            "run_calibration_confidence": 0.78,
        },
    )
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=student_id,
        payload={
            "source_run_summary_event_id": summary_event.event_id,
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "average_run_outcome_score": 0.55,
            "average_run_confidence": 0.77,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "positive_run_rate": 0.0,
            "negative_run_rate": 0.5,
            "progress_delta": -0.14,
            "progress_signal": "declining",
        },
    )

    recorded = recorder.record_from_summary_events(summary_events=[summary_event])

    assert len(recorded) == 1
    profile_event = recorded[0]
    assert profile_event.event_type == "learning.strategy.profile"
    assert profile_event.payload["strategy_signal"] == "support_intensive"
    assert profile_event.payload["strategy_support_bias"] == -1
    assert profile_event.payload["strategy_recovery_focus"] == "prerequisite_rebuild"
    assert profile_event.payload["strategy_trajectory_state"] == "relapsing"
    assert profile_event.payload["strategy_recommended_next_action"] == "rebuild_prerequisite"
    assert profile_event.payload["strategy_relapse_risk"] > 0.5


def test_learner_strategy_signal_service_prefers_matching_strategy_profile(tmp_path):
    database_path = str(tmp_path / "learner-strategy-service.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.strategy.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "average_run_outcome_score": 0.82,
            "average_run_confidence": 0.8,
            "matched_run_count": 5,
            "matched_session_count": 3,
            "progress_signal": "improving",
            "progress_delta": 0.18,
            "strategy_signal": "independence_ready",
            "strategy_support_bias": 1,
            "strategy_recovery_focus": "independent_practice",
            "strategy_trajectory_state": "accelerating",
            "strategy_recommended_next_action": "check_transfer_readiness",
            "strategy_volatility_index": 0.0,
            "strategy_relapse_risk": 0.08,
            "strategy_rationale": "Support can fade because the learner has stayed strong across sessions.",
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
    strategy = LearnerStrategySignalService(audit_store=audit_store).strategy_for(
        student_id=request.student_id,
        request=request,
    )

    assert strategy.source == "strategy_profile"
    assert strategy.signal == "independence_ready"
    assert strategy.support_bias == 1
    assert strategy.recovery_focus == "independent_practice"
    assert strategy.trajectory_state == "accelerating"
    assert strategy.recommended_next_action == "check_transfer_readiness"


def test_learner_strategy_signal_service_derives_plateau_from_progress_profiles(tmp_path):
    database_path = str(tmp_path / "learner-strategy-plateau.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "average_run_outcome_score": 0.68,
            "average_run_confidence": 0.77,
            "matched_run_count": 5,
            "matched_session_count": 4,
            "positive_run_rate": 0.25,
            "negative_run_rate": 0.0,
            "progress_signal": "stable",
            "progress_delta": 0.02,
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
    strategy = LearnerStrategySignalService(audit_store=audit_store).strategy_for(
        student_id=request.student_id,
        request=request,
    )

    assert strategy.source == "progress_profile"
    assert strategy.trajectory_state == "plateaued"
    assert strategy.recommended_next_action == "introduce_varied_support"
