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
