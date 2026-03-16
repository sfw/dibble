from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.predictive_warm_queue_store import SQLitePredictiveWarmQueueStore
from dibble.storage import ensure_database


def test_predictive_warm_queue_store_deduplicates_pending_requests(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path)
    request = GenerationRequest.model_validate(
        {
            "student_id": str(uuid4()),
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
            "predictive_warm": True,
            "warm_reason": "test",
            "source_generation_id": "gen-1",
        }
    )

    first_task = store.enqueue(request=request)
    duplicate_task = store.enqueue(request=request)

    assert first_task is not None
    assert duplicate_task is None
    assert store.stats()["pending"] == 1


def test_predictive_warm_queue_store_cancels_matching_pending_requests(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue-cancel.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path)
    student_id = str(uuid4())
    store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-1"],
                "intent": "practice",
                "requested_content_type": "practice_problem",
                "predictive_warm": True,
                "warm_reason": "test",
                "source_generation_id": "gen-1",
            }
        )
    )
    store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "learning_session_id": "session-2",
                "target_kc_ids": ["KC-2"],
                "intent": "practice",
                "requested_content_type": "practice_problem",
                "predictive_warm": True,
                "warm_reason": "test",
                "source_generation_id": "gen-2",
            }
        )
    )

    canceled = store.cancel_pending(
        student_id=student_id,
        learning_session_id="session-1",
        target_kc_ids=["KC-1"],
        target_lo_ids=[],
    )

    stats = store.stats()
    assert canceled == 1
    assert stats["pending"] == 1
    assert stats["canceled"] == 1


def test_predictive_warm_queue_store_claims_higher_priority_tasks_first(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue-priority.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path)
    student_id = str(uuid4())
    practice_task = store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-1"],
                "intent": "practice",
                "requested_content_type": "practice_problem",
                "predictive_warm": True,
                "warm_reason": "practice follow-up",
                "source_generation_id": "gen-1",
            }
        )
    )
    assessment_task = store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-1"],
                "intent": "assessment",
                "requested_content_type": "assessment_probe",
                "predictive_warm": True,
                "warm_reason": "transfer check after bridge",
                "source_generation_id": "gen-1",
                "mode_calibration": {
                    "session_phase": "bridge",
                    "sequence_action": "attempt_transfer",
                },
            }
        )
    )

    claimed = store.claim_pending(limit=1)

    assert practice_task is not None
    assert assessment_task is not None
    assert len(claimed) == 1
    assert claimed[0].task_id == assessment_task.task_id
    assert claimed[0].priority_score > practice_task.priority_score


def test_predictive_warm_queue_store_cancels_stale_pending_tasks_before_claim(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue-stale.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path, stale_after_minutes=1)
    task = store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": str(uuid4()),
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-1"],
                "intent": "practice",
                "requested_content_type": "practice_problem",
                "predictive_warm": True,
                "warm_reason": "test",
                "source_generation_id": "gen-1",
            }
        )
    )

    assert task is not None
    store._update_status(task_id=task.task_id, status="pending", last_error=None)
    from datetime import datetime, timedelta, timezone
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        connection.execute(
            """
            UPDATE predictive_warm_queue
            SET created_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (stale_time, stale_time, task.task_id),
        )
        connection.commit()

    claimed = store.claim_pending(limit=1)

    assert claimed == []
    assert store.stats()["canceled"] == 1
