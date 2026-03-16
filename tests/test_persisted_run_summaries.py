from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.persisted_run_summaries import PersistedRunSummaryResolver
from dibble.storage import ensure_database


def test_persisted_run_summary_resolver_prefers_richer_summary_for_generation(tmp_path):
    database_path = str(tmp_path / "persisted-run-summary-resolver.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={"generation_id": "gen-1"},
    )
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "source_generation_event_id": generation_event.event_id,
            "generation_id": "gen-1",
            "run_summary_score": 0.71,
            "run_calibration_signal": "mixed",
            "run_calibration_confidence": 0.64,
            "run_direct_source_count": 1,
            "run_event_count": 2,
        },
    )
    richer_summary = audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "source_generation_event_id": generation_event.event_id,
            "generation_id": "gen-1",
            "run_summary_score": 0.82,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.79,
            "run_direct_source_count": 2,
            "run_event_count": 4,
        },
    )

    resolved = PersistedRunSummaryResolver().resolve_for_generation(
        generation_event=generation_event,
        summary_events=audit_store.list(limit=10),
    )

    assert resolved is not None
    assert resolved.event_id == richer_summary.event_id
    assert resolved.summary.run_outcome_score == 0.82
    assert resolved.summary.event_count == 4


def test_persisted_run_summary_resolver_ignores_unrelated_summaries(tmp_path):
    database_path = str(tmp_path / "persisted-run-summary-resolver-ignore.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={"generation_id": "gen-target"},
    )
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "source_generation_event_id": "other-event",
            "generation_id": "other-generation",
            "run_summary_score": 0.88,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.9,
            "run_direct_source_count": 2,
            "run_event_count": 4,
        },
    )

    resolved = PersistedRunSummaryResolver().resolve_for_generation(
        generation_event=generation_event,
        summary_events=audit_store.list(limit=10),
    )

    assert resolved is None
