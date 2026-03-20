"""Tests for the MisconceptionRemediationOutcomeSignalService.

These tests verify that misconception.remediation.outcome audit events are
correctly aggregated into per-KC reliability signals that influence
misconception detection confidence.
"""

from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.misconception_remediation_outcome_signals import (
    MisconceptionRemediationOutcomeSignalService,
)
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def _store(tmp_path) -> SQLiteAuditStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    conn = create_connection(db)
    return SQLiteAuditStore(conn)


def _remediation_outcome_event(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    outcome: str,
    target_kc_id: str = "KC-1",
    focus_kc_ids: list[str] | None = None,
):
    """Write a misconception.remediation.outcome event."""
    return audit_store.append(
        event_type="misconception.remediation.outcome",
        status=outcome,
        student_id=student_id,
        payload={
            "session_id": str(uuid4()),
            "target_kc_id": target_kc_id,
            "focus_kc_ids": focus_kc_ids or [target_kc_id],
            "outcome": outcome,
        },
    )


def test_empty_bundle_when_no_outcomes(tmp_path):
    store = _store(tmp_path)
    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    student = uuid4()

    bundle = service.signal_bundle_for_student(student_id=student)

    assert len(bundle.signals_by_kc) == 0
    assert bundle.signal_for_kc("KC-1") is None
    assert bundle.confidence_adjustment_for_kc("KC-1") == 0.0
    assert not bundle.is_persistent_for_kc("KC-1")


def test_resolved_outcomes_temper_confidence(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(3):
        _remediation_outcome_event(
            store,
            student_id=str(student),
            outcome="resolved",
            target_kc_id="KC-1",
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    signal = bundle.signal_for_kc("KC-1")
    assert signal is not None
    assert signal.evaluated_count == 3
    assert signal.resolved_count == 3
    assert signal.resolution_rate == 1.0
    # Remediation resolving → slightly temper confidence (negative adjustment)
    assert signal.confidence_adjustment < 0.0
    assert not signal.persistent_misconception


def test_unresolved_outcomes_boost_confidence(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(3):
        _remediation_outcome_event(
            store,
            student_id=str(student),
            outcome="unresolved",
            target_kc_id="KC-1",
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    signal = bundle.signal_for_kc("KC-1")
    assert signal is not None
    assert signal.unresolved_count == 3
    assert signal.unresolution_rate == 1.0
    # Persistent misconception → boost detection confidence (positive adjustment)
    assert signal.confidence_adjustment > 0.0
    assert signal.persistent_misconception


def test_persistent_misconception_flagged(tmp_path):
    """Persistent flag requires >= 2 unresolved AND >= 60% unresolution rate."""
    store = _store(tmp_path)
    student = uuid4()

    _remediation_outcome_event(
        store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
    )
    _remediation_outcome_event(
        store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
    )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    assert bundle.is_persistent_for_kc("KC-1")


def test_single_unresolved_not_persistent(tmp_path):
    """One unresolved outcome is not enough to flag persistent."""
    store = _store(tmp_path)
    student = uuid4()

    _remediation_outcome_event(
        store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
    )
    _remediation_outcome_event(
        store, student_id=str(student), outcome="resolved", target_kc_id="KC-1"
    )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    # 1 unresolved, 1 resolved — 50% unresolution rate, below 60% threshold
    assert not bundle.is_persistent_for_kc("KC-1")


def test_inconclusive_outcomes_ignored(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(5):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="inconclusive", target_kc_id="KC-1"
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    assert len(bundle.signals_by_kc) == 0


def test_below_minimum_count_no_adjustment(tmp_path):
    """With only 1 outcome, no adjustment is applied."""
    store = _store(tmp_path)
    student = uuid4()

    _remediation_outcome_event(
        store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
    )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    signal = bundle.signal_for_kc("KC-1")
    assert signal is not None
    assert signal.evaluated_count == 1
    assert signal.confidence_adjustment == 0.0


def test_per_kc_signals_independent(tmp_path):
    """Different KCs get independent signals."""
    store = _store(tmp_path)
    student = uuid4()

    # KC-1: all unresolved
    for _ in range(3):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
        )
    # KC-2: all resolved
    for _ in range(3):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="resolved", target_kc_id="KC-2"
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    assert bundle.confidence_adjustment_for_kc("KC-1") > 0.0  # boosted
    assert bundle.confidence_adjustment_for_kc("KC-2") < 0.0  # tempered
    assert bundle.is_persistent_for_kc("KC-1")
    assert not bundle.is_persistent_for_kc("KC-2")


def test_mixed_outcomes_moderate_signal(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 2 resolved + 2 unresolved
    for _ in range(2):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="resolved", target_kc_id="KC-1"
        )
    for _ in range(2):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    signal = bundle.signal_for_kc("KC-1")
    assert signal is not None
    assert signal.evaluated_count == 4
    # 50/50 — no strong adjustment in either direction
    assert signal.confidence_adjustment == 0.0


def test_confidence_adjustment_bounded(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(20):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    signal = bundle.signal_for_kc("KC-1")
    assert signal is not None
    # Bounded at _MAX_CONFIDENCE_BOOST = 0.12
    assert signal.confidence_adjustment <= 0.12
    assert signal.confidence_adjustment > 0.0


def test_focus_kc_ids_distribute_outcomes(tmp_path):
    """When a remediation session covers multiple KCs, all get the signal."""
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(2):
        _remediation_outcome_event(
            store,
            student_id=str(student),
            outcome="unresolved",
            target_kc_id="KC-1",
            focus_kc_ids=["KC-1", "KC-2"],
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    # Both KCs should have signals
    assert bundle.signal_for_kc("KC-1") is not None
    assert bundle.signal_for_kc("KC-2") is not None
    assert bundle.signal_for_kc("KC-1").unresolved_count == 2
    assert bundle.signal_for_kc("KC-2").unresolved_count == 2


def test_rationale_includes_persistence_warning(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(3):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="unresolved", target_kc_id="KC-1"
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    signal = bundle.signal_for_kc("KC-1")
    assert signal is not None
    assert signal.rationale is not None
    assert "persistent misconception" in signal.rationale
    assert "teacher review" in signal.rationale


def test_rationale_includes_recency_weighted_rate(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(2):
        _remediation_outcome_event(
            store, student_id=str(student), outcome="resolved", target_kc_id="KC-1"
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)
    bundle = service.signal_bundle_for_student(student_id=student)

    signal = bundle.signal_for_kc("KC-1")
    assert signal is not None
    assert signal.rationale is not None
    assert "recency-weighted" in signal.rationale


def test_different_students_independent(tmp_path):
    store = _store(tmp_path)
    student_a = uuid4()
    student_b = uuid4()

    for _ in range(3):
        _remediation_outcome_event(
            store, student_id=str(student_a), outcome="unresolved", target_kc_id="KC-1"
        )
    for _ in range(3):
        _remediation_outcome_event(
            store, student_id=str(student_b), outcome="resolved", target_kc_id="KC-1"
        )

    service = MisconceptionRemediationOutcomeSignalService(audit_store=store)

    bundle_a = service.signal_bundle_for_student(student_id=student_a)
    bundle_b = service.signal_bundle_for_student(student_id=student_b)

    assert bundle_a.confidence_adjustment_for_kc("KC-1") > 0.0
    assert bundle_b.confidence_adjustment_for_kc("KC-1") < 0.0
