from __future__ import annotations

from uuid import uuid4

from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
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

    summary = LearnerSummaryService(profile_store=profile_store, audit_store=audit_store).build_for_student(
        student_id=student_id
    )

    assert summary is not None
    assert summary.engagement == "high"
    assert summary.help_seeking == "medium"
    assert summary.calibration.source == "profile"
    assert summary.calibration.signal == "positive"
    assert summary.calibration.matched_session_count == 3
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

    summary = LearnerSummaryService(profile_store=profile_store, audit_store=audit_store).build_for_student(
        student_id=student_id
    )

    assert summary is not None
    assert summary.calibration.source == "run_summary"
    assert summary.calibration.signal == "negative"
    assert summary.calibration.average_run_outcome_score == 0.43
    assert summary.recent_activity.last_generation_id == "fallback-gen"
