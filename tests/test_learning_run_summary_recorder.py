from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learning_run_summary_recorder import LearningRunSummaryRecorder
from dibble.storage import ensure_database


def test_learning_run_summary_recorder_records_summary_for_observation_trigger(
    tmp_path,
):
    database_path = str(tmp_path / "learning-run-summary-recorder.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    recorder = LearningRunSummaryRecorder(audit_store=audit_store)
    student_id = str(uuid4())
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "generation_id": "gen-1",
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "content_type": "practice_problem",
            "prompt_template_name": "practice_problem.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.78,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    trigger_event = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "learning_session_id": "session-1",
            "observed_content_type": "practice_problem",
            "task_type": "practice",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.22,
            "confidence_calibration": 0.84,
            "help_seeking": "low",
        },
    )

    recorded = recorder.record_from_trigger_event(trigger_event=trigger_event)

    assert len(recorded) == 1
    summary_event = recorded[0]
    assert summary_event.event_type == "learning.run.summary"
    assert summary_event.payload["trigger_event_id"] == trigger_event.event_id
    assert summary_event.payload["generation_id"] == "gen-1"
    assert summary_event.payload["run_summary_score"] is not None
    assert summary_event.payload["run_calibration_signal"] == "positive"
