from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GeneratedContent,
    GeneratedBlock,
    GenerationMetadata,
    GenerationResponse,
    InterventionType,
)
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.predictive_content_invalidator import PredictiveContentInvalidator
from dibble.services.predictive_warm_queue_store import SQLitePredictiveWarmQueueStore
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def test_predictive_content_invalidator_expires_only_matching_predictive_entries(
    tmp_path,
):
    database_path = str(tmp_path / "predictive-cache.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    generated_content_store = SQLiteGeneratedContentStore(conn)
    queue_store = SQLitePredictiveWarmQueueStore(conn)
    audit_store = SQLiteAuditStore(conn)
    student_id = str(uuid4())

    generated_content_store.upsert(
        cache_key="predictive-match",
        content=_build_generated_content(
            generation_id="gen-match",
            student_id=student_id,
            request_context={
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
                "is_predictive_warm": True,
            },
        ),
    )
    generated_content_store.upsert(
        cache_key="predictive-other-session",
        content=_build_generated_content(
            generation_id="gen-other-session",
            student_id=student_id,
            request_context={
                "learning_session_id": "session-2",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
                "is_predictive_warm": True,
            },
        ),
    )
    generated_content_store.upsert(
        cache_key="non-predictive",
        content=_build_generated_content(
            generation_id="gen-non-predictive",
            student_id=student_id,
            request_context={
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
            },
        ),
    )
    trigger_event = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
        },
    )
    from dibble.models.generation import GenerationRequest

    queue_store.enqueue(
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "learning_session_id": "session-1",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
                "intent": "practice",
                "requested_content_type": "practice_problem",
                "predictive_warm": True,
                "warm_reason": "test",
                "source_generation_id": "gen-source",
            }
        )
    )

    invalidation_event = PredictiveContentInvalidator(
        generated_content_store,
        audit_store,
        predictive_warm_task_store=queue_store,
    ).invalidate_from_trigger_event(trigger_event)

    assert invalidation_event.payload["expired_entries"] == 1
    assert invalidation_event.payload["canceled_queue_tasks"] == 1
    assert generated_content_store.get_fresh(cache_key="predictive-match") is None
    assert (
        generated_content_store.get_fresh(cache_key="predictive-other-session")
        is not None
    )
    assert generated_content_store.get_fresh(cache_key="non-predictive") is not None


def _build_generated_content(
    *,
    generation_id: str,
    student_id: str,
    request_context: dict[str, object],
) -> GeneratedContent:
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    metadata = GenerationMetadata(
        quality_score=0.75, validation_passed=True, grounding_count=1
    )
    response = GenerationResponse(
        student_id=student_id,
        route=route,
        blocks=[GeneratedBlock(kind="summary", title="Summary", body="Body")],
        curriculum_context=["Equivalent fractions"],
        grounding=[],
        safety_notes=["test"],
        generation_id=generation_id,
        generation_metadata=metadata,
    )
    created_at = datetime.now(timezone.utc)
    return GeneratedContent(
        generation_id=generation_id,
        student_id=student_id,
        content_type="practice_problem",
        request_context=request_context,
        response=response,
        quality=metadata,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )
