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
    store._update_status(task_id=task.task_id, status="pending", last_error=None, next_attempt_at=None)
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


def test_predictive_warm_queue_store_spreads_claims_across_priority_classes(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue-bounded-batch.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path)
    student_id = str(uuid4())
    store.enqueue(
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
            }
        )
    )
    store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-2"],
                "intent": "remediation",
                "requested_content_type": "remedial_micro_module",
                "predictive_warm": True,
                "warm_reason": "repair prerequisite",
                "source_generation_id": "gen-2",
            }
        )
    )
    routine_task = store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-3"],
                "intent": "explanation",
                "requested_content_type": "micro_explanation",
                "predictive_warm": True,
                "warm_reason": "quick recap",
                "source_generation_id": "gen-3",
            }
        )
    )

    claimed = store.claim_pending(limit=3)

    assert routine_task is not None
    assert len(claimed) == 3
    assert any(task.priority_class == "routine" for task in claimed)
    assert any(task.task_id == routine_task.task_id for task in claimed)


def test_predictive_warm_queue_store_defers_retry_until_backoff_expires(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue-retry.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path, retry_backoff_seconds=30)
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
    claimed = store.claim_pending(limit=1)
    deferred = store.defer_retry(task_id=claimed[0].task_id, error="provider timeout")

    assert deferred is not None
    assert store.stats()["deferred"] == 1
    assert store.claim_pending(limit=1) == []

    from datetime import datetime, timedelta, timezone
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        ready_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        connection.execute(
            """
            UPDATE predictive_warm_queue
            SET next_attempt_at = ?
            WHERE task_id = ?
            """,
            (ready_time, task.task_id),
        )
        connection.commit()

    claimed_retry = store.claim_pending(limit=1)

    assert len(claimed_retry) == 1
    assert claimed_retry[0].attempt_count == 2


def test_predictive_warm_queue_store_sweep_requeues_stale_processing_tasks(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue-sweep.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path, processing_timeout_seconds=30)
    task = store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": str(uuid4()),
                "learning_session_id": "session-sweep",
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
    claimed = store.claim_pending(limit=1)
    assert claimed

    from datetime import datetime, timedelta, timezone
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        connection.execute(
            """
            UPDATE predictive_warm_queue
            SET updated_at = ?
            WHERE task_id = ?
            """,
            (stale_time, task.task_id),
        )
        connection.commit()

    sweep_result = store.sweep()

    assert sweep_result.requeued_tasks == 1
    assert store.stats()["deferred"] == 1


def test_predictive_warm_queue_store_uses_lower_retry_cap_for_routine_tasks(tmp_path):
    database_path = str(tmp_path / "predictive-warm-queue-routine-cap.db")
    ensure_database(database_path)
    store = SQLitePredictiveWarmQueueStore(database_path, max_retry_attempts=3)
    task = store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": str(uuid4()),
                "learning_session_id": "session-routine-cap",
                "target_kc_ids": ["KC-1"],
                "intent": "explanation",
                "requested_content_type": "micro_explanation",
                "predictive_warm": True,
                "warm_reason": "quick recap",
                "source_generation_id": "gen-1",
            }
        )
    )

    assert task is not None
    first_claim = store.claim_pending(limit=1)
    assert first_claim
    first_defer = store.defer_retry(task_id=first_claim[0].task_id, error="timeout")
    assert first_defer is not None

    from datetime import datetime, timedelta, timezone
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        ready_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        connection.execute(
            """
            UPDATE predictive_warm_queue
            SET next_attempt_at = ?
            WHERE task_id = ?
            """,
            (ready_time, task.task_id),
        )
        connection.commit()

    second_claim = store.claim_pending(limit=1)
    assert second_claim
    second_defer = store.defer_retry(task_id=second_claim[0].task_id, error="timeout")

    assert second_defer is None
    assert store.stats()["failed"] == 1
