from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learning_progress_profiles import (
    LearningProgressProfileBuilder,
    LearningProgressProfileRecorder,
)
from dibble.storage import ensure_database


def test_learning_progress_profile_recorder_persists_progress_trend(tmp_path):
    database_path = str(tmp_path / "learning-progress-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    recorder = LearningProgressProfileRecorder(audit_store=audit_store)
    student_id = str(uuid4())

    summary_events = [
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-1",
                "intent": "practice",
                "learning_session_id": "session-1",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.52,
                "run_calibration_signal": "mixed",
                "run_calibration_confidence": 0.72,
            },
        ),
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-2",
                "intent": "practice",
                "learning_session_id": "session-2",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.64,
                "run_calibration_signal": "positive",
                "run_calibration_confidence": 0.74,
            },
        ),
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-3",
                "intent": "practice",
                "learning_session_id": "session-3",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.79,
                "run_calibration_signal": "positive",
                "run_calibration_confidence": 0.78,
            },
        ),
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-4",
                "intent": "practice",
                "learning_session_id": "session-4",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.86,
                "run_calibration_signal": "positive",
                "run_calibration_confidence": 0.81,
            },
        ),
    ]

    recorded = recorder.record_from_summary_events(summary_events=[summary_events[-1]])

    assert len(recorded) == 1
    profile_event = recorded[0]
    assert profile_event.event_type == "learning.progress.profile"
    assert profile_event.payload["matched_session_count"] == 4
    assert (
        profile_event.payload["recent_average_run_outcome_score"]
        > profile_event.payload["prior_average_run_outcome_score"]
    )
    assert profile_event.payload["progress_signal"] == "improving"


def test_learning_progress_profile_builder_marks_declining_when_recent_runs_drop(
    tmp_path,
):
    database_path = str(tmp_path / "learning-progress-profile-declining.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    builder = LearningProgressProfileBuilder()
    student_id = str(uuid4())

    summary_events = [
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-1",
                "intent": "practice",
                "learning_session_id": "session-1",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.9,
                "run_calibration_signal": "positive",
                "run_calibration_confidence": 0.82,
            },
        ),
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-2",
                "intent": "practice",
                "learning_session_id": "session-2",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.84,
                "run_calibration_signal": "positive",
                "run_calibration_confidence": 0.79,
            },
        ),
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-3",
                "intent": "practice",
                "learning_session_id": "session-3",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.61,
                "run_calibration_signal": "mixed",
                "run_calibration_confidence": 0.76,
            },
        ),
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": "gen-4",
                "intent": "practice",
                "learning_session_id": "session-4",
                "content_type": "practice_problem",
                "target_kc_ids": ["KC-1"],
                "run_summary_score": 0.48,
                "run_calibration_signal": "negative",
                "run_calibration_confidence": 0.73,
            },
        ),
    ]

    snapshot = builder.build_from_summary_event(
        summary_event=summary_events[-1],
        summary_events=list(reversed(summary_events)),
    )

    assert snapshot is not None
    assert (
        snapshot.recent_average_run_outcome_score
        < snapshot.prior_average_run_outcome_score
    )
    assert snapshot.progress_delta < 0
    assert snapshot.progress_signal == "declining"


def test_learning_progress_profile_builder_marks_tentative_without_prior_history(
    tmp_path,
):
    database_path = str(tmp_path / "learning-progress-profile-tentative.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    builder = LearningProgressProfileBuilder()
    student_id = str(uuid4())

    summary_event = audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "intent": "practice",
            "learning_session_id": "session-1",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "run_summary_score": 0.66,
            "run_calibration_signal": "mixed",
            "run_calibration_confidence": 0.7,
        },
    )

    snapshot = builder.build_from_summary_event(
        summary_event=summary_event, summary_events=[summary_event]
    )

    assert snapshot is not None
    assert snapshot.prior_average_run_outcome_score is None
    assert snapshot.progress_delta == 0.0
    assert snapshot.progress_signal == "tentative"
