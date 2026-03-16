from __future__ import annotations

from uuid import uuid4

from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learning_state_profiles import LearnerStateSignalService
from dibble.services.learning_trait_profiles import LearnerTraitProfileSignalService
from dibble.services.learner_strategy_profiles import LearnerStrategySignalService
from dibble.services.learner_summary_service import LearnerSummaryService
from dibble.services.profile_store import SQLiteProfileStore
from dibble.storage import ensure_database
from tests.support import build_profile


def test_learner_summary_service_prefers_calibration_profile_and_recent_activity(tmp_path):
    database_path = str(tmp_path / "learner-summary-service.db")
    ensure_database(database_path)
    profile_store = SQLiteProfileStore(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    profile_store.upsert(LearnerProfile.model_validate(build_profile(student_id, engagement="high", help_seeking="medium")))
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "gen-summary-1",
            "learning_session_id": "summary-session-1",
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "gen-summary-1",
            "learning_session_id": "summary-session-1",
        },
    )
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "gen-summary-1",
            "learning_session_id": "summary-session-1",
        },
    )
    audit_store.append(
        event_type="learning.calibration.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "average_run_outcome_score": 0.81,
            "average_run_confidence": 0.77,
            "matched_run_count": 5,
            "matched_session_count": 3,
            "profile_signal": "positive",
        },
    )
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.8,
            "average_run_confidence": 0.76,
            "matched_run_count": 5,
            "matched_session_count": 3,
            "positive_run_rate": 0.8,
            "negative_run_rate": 0.0,
            "recent_average_run_outcome_score": 0.84,
            "prior_average_run_outcome_score": 0.71,
            "progress_delta": 0.13,
            "progress_signal": "improving",
        },
    )
    audit_store.append(
        event_type="learning.strategy.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "average_run_outcome_score": 0.8,
            "average_run_confidence": 0.76,
            "matched_run_count": 5,
            "matched_session_count": 3,
            "progress_signal": "improving",
            "progress_delta": 0.13,
            "strategy_signal": "independence_ready",
            "strategy_support_bias": 1,
            "strategy_recovery_focus": "independent_practice",
            "strategy_trajectory_state": "accelerating",
            "strategy_recommended_next_action": "check_transfer_readiness",
            "strategy_volatility_index": 0.0,
            "strategy_relapse_risk": 0.05,
            "strategy_rationale": "Support can fade because the learner has stayed strong across sessions.",
        },
    )
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.8,
            "average_run_confidence": 0.76,
            "matched_run_count": 5,
            "matched_session_count": 3,
            "progress_signal": "improving",
            "progress_delta": 0.13,
            "strategy_signal": "independence_ready",
            "strategy_trajectory_state": "accelerating",
            "state_profile_signal": "independence_ready",
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.43,
            "confidence_calibration": 0.79,
            "help_seeking": "low",
            "self_monitoring": 0.81,
        },
    )
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "matched_observation_count": 6,
            "matched_session_count": 3,
            "profile_signal": "stable",
            "processing_speed": {"value": 0.76, "confidence": 0.79},
            "working_memory": {"value": 0.72, "confidence": 0.77},
            "spatial_reasoning": {"value": 0.68, "confidence": 0.65},
        },
    )

    summary = LearnerSummaryService(
        profile_store=profile_store,
        audit_store=audit_store,
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
        trait_profile_signal_service=LearnerTraitProfileSignalService(audit_store=audit_store),
    ).build_for_student(student_id=student_id)

    assert summary is not None
    assert summary.engagement == "high"
    assert summary.help_seeking == "medium"
    assert summary.calibration.source == "profile"
    assert summary.calibration.signal == "positive"
    assert summary.calibration.matched_session_count == 3
    assert summary.progress.source == "profile"
    assert summary.progress.signal == "improving"
    assert summary.progress.progress_delta == 0.13
    assert summary.strategy.source == "strategy_profile"
    assert summary.strategy.signal == "independence_ready"
    assert summary.strategy.support_bias == 1
    assert summary.strategy.trajectory_state == "accelerating"
    assert summary.strategy.recommended_next_action == "check_transfer_readiness"
    assert summary.state_profile.source == "state_profile"
    assert summary.state_profile.signal == "independence_ready"
    assert summary.state_profile.total_load == 0.43
    assert summary.trait_profile.source == "trait_profile"
    assert summary.trait_profile.processing_speed is not None
    assert summary.trait_profile.processing_speed.value == 0.76
    assert summary.recent_activity.generation_count == 1
    assert summary.recent_activity.observation_count == 1
    assert summary.recent_activity.socratic_assessment_count == 1
    assert summary.recent_activity.last_generation_id == "gen-summary-1"
    assert summary.recent_activity.last_learning_session_id == "summary-session-1"


def test_learner_summary_service_falls_back_to_run_summary_when_profile_missing(tmp_path):
    database_path = str(tmp_path / "learner-summary-service-fallback.db")
    ensure_database(database_path)
    profile_store = SQLiteProfileStore(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    profile_store.upsert(LearnerProfile.model_validate(build_profile(student_id)))
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "explanation",
            "content_type": "worked_example",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "run_summary_score": 0.43,
            "run_calibration_signal": "negative",
            "run_calibration_confidence": 0.7,
            "run_event_count": 4,
            "learning_session_id": "fallback-session",
            "generation_id": "fallback-gen",
        },
    )

    summary = LearnerSummaryService(
        profile_store=profile_store,
        audit_store=audit_store,
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
        trait_profile_signal_service=LearnerTraitProfileSignalService(audit_store=audit_store),
    ).build_for_student(student_id=student_id)

    assert summary is not None
    assert summary.calibration.source == "run_summary"
    assert summary.calibration.signal == "negative"
    assert summary.calibration.average_run_outcome_score == 0.43
    assert summary.progress.source == "insufficient"
    assert summary.strategy.source == "insufficient"
    assert summary.state_profile.source == "insufficient"
    assert summary.trait_profile.source == "insufficient"
    assert summary.recent_activity.last_generation_id == "fallback-gen"
