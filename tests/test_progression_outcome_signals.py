"""Tests for the ProgressionOutcomeSignalService feedback loop.

These tests verify that progression outcome verdicts (recorded by
ProgressionOutcomeTracker) are correctly aggregated into reliability
signals that adjust hold and transfer thresholds.
"""

from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.progression_outcome_signals import (
    ProgressionOutcomeSignalService,
)
from dibble.storage import ensure_database


def _store(tmp_path) -> SQLiteAuditStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    return SQLiteAuditStore(db)


def _outcome_event(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    action: str,
    outcome: str,
    target_kc_ids: list[str] | None = None,
):
    """Write a progression.outcome event."""
    return audit_store.append(
        event_type="progression.outcome",
        status=outcome,
        student_id=student_id,
        payload={
            "decision_event_id": str(uuid4()),
            "decision_action": action,
            "decision_target_kc_ids": target_kc_ids or ["KC-1"],
            "outcome": outcome,
        },
    )


def test_empty_signal_when_no_outcomes(tmp_path):
    store = _store(tmp_path)
    service = ProgressionOutcomeSignalService(audit_store=store)
    student = uuid4()
    signal = service.signal_for_student(student_id=student)

    assert signal.hold_evaluated_count == 0
    assert signal.transfer_evaluated_count == 0
    assert signal.hold_threshold_adjustment == 0.0
    assert signal.transfer_confidence_adjustment == 0.0
    assert signal.prerequisite_threshold_adjustment == 0.0
    assert signal.rationale is None


def test_hold_negative_rate_raises_threshold(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 3 negative hold outcomes (above the _MIN_HOLD_OUTCOMES threshold of 3)
    for _ in range(3):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="negative",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.hold_evaluated_count == 3
    assert signal.hold_negative_count == 3
    assert signal.hold_negative_rate == 1.0
    # Holds are all negative → threshold should be raised (positive adjustment)
    assert signal.hold_threshold_adjustment > 0.0
    assert signal.rationale is not None
    assert "raising" in signal.rationale


def test_hold_positive_rate_lowers_threshold(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 4 positive hold outcomes
    for _ in range(4):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="positive",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.hold_evaluated_count == 4
    assert signal.hold_positive_count == 4
    assert signal.hold_positive_rate == 1.0
    # Holds are all positive → threshold should be lowered (negative adjustment)
    assert signal.hold_threshold_adjustment < 0.0
    assert "lowering" in signal.rationale


def test_transfer_negative_rate_raises_confidence(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 2 negative transfer outcomes
    for _ in range(2):
        _outcome_event(
            store,
            student_id=str(student),
            action="attempt_transfer",
            outcome="negative",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.transfer_evaluated_count == 2
    assert signal.transfer_negative_rate == 1.0
    # Transfers are premature → confidence requirement raised
    assert signal.transfer_confidence_adjustment > 0.0
    assert "Transfer outcomes" in signal.rationale


def test_transfer_positive_rate_lowers_confidence(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 3 positive transfer outcomes
    for _ in range(3):
        _outcome_event(
            store,
            student_id=str(student),
            action="attempt_transfer",
            outcome="positive",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.transfer_evaluated_count == 3
    assert signal.transfer_positive_rate == 1.0
    # Transfers are succeeding → confidence requirement lowered
    assert signal.transfer_confidence_adjustment < 0.0


def test_inconclusive_outcomes_are_ignored(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 5 inconclusive outcomes should not affect signal
    for _ in range(5):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="inconclusive",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.hold_evaluated_count == 0
    assert signal.hold_threshold_adjustment == 0.0


def test_below_minimum_count_produces_no_adjustment(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # Only 2 hold outcomes (below _MIN_HOLD_OUTCOMES of 3)
    for _ in range(2):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="negative",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.hold_evaluated_count == 2
    assert signal.hold_negative_rate == 1.0
    # Below minimum → no adjustment
    assert signal.hold_threshold_adjustment == 0.0


def test_mixed_outcomes_produce_moderate_signal(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 2 positive + 2 negative holds
    for _ in range(2):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="positive",
            target_kc_ids=["KC-1"],
        )
    for _ in range(2):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="negative",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.hold_evaluated_count == 4
    assert signal.hold_positive_rate == 0.5
    assert signal.hold_negative_rate == 0.5
    # 50/50 — neither threshold met for adjustment
    assert signal.hold_threshold_adjustment == 0.0


def test_target_kc_filtering(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # 3 negative hold outcomes on KC-1
    for _ in range(3):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="negative",
            target_kc_ids=["KC-1"],
        )
    # 3 positive hold outcomes on KC-2
    for _ in range(3):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="positive",
            target_kc_ids=["KC-2"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)

    # KC-1 only — should see negative
    signal_kc1 = service.signal_for_student(student_id=student, target_kc_ids=["KC-1"])
    assert signal_kc1.hold_negative_rate == 1.0
    assert signal_kc1.hold_threshold_adjustment > 0.0

    # KC-2 only — should see positive
    signal_kc2 = service.signal_for_student(student_id=student, target_kc_ids=["KC-2"])
    assert signal_kc2.hold_positive_rate == 1.0
    assert signal_kc2.hold_threshold_adjustment < 0.0

    # No filter — aggregated
    signal_all = service.signal_for_student(student_id=student)
    assert signal_all.hold_evaluated_count == 6
    assert signal_all.hold_positive_rate == 0.5


def test_prerequisite_outcomes_tracked_separately(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(3):
        _outcome_event(
            store,
            student_id=str(student),
            action="rebuild_prerequisite_first",
            outcome="positive",
            target_kc_ids=["KC-prereq"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.prerequisite_evaluated_count == 3
    assert signal.prerequisite_positive_rate == 1.0
    # Prerequisite outcomes don't directly adjust hold or transfer thresholds
    assert signal.hold_threshold_adjustment == 0.0
    assert signal.transfer_confidence_adjustment == 0.0


def test_threshold_adjustment_is_bounded(tmp_path):
    store = _store(tmp_path)
    student = uuid4()

    # Many negative hold outcomes
    for _ in range(20):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="negative",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    # Should be capped at _MAX_HOLD_ADJUSTMENT = 0.06
    assert signal.hold_threshold_adjustment <= 0.06
    assert signal.hold_threshold_adjustment > 0.0


# ---------- New tests for recency weighting and subtype granularity ----------


def test_hold_subtype_breakdowns_tracked(tmp_path):
    """Different hold subtypes appear as separate breakdowns."""
    store = _store(tmp_path)
    student = uuid4()

    # 2 positive hold_target + 2 negative hold_repair_target
    for _ in range(2):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="positive",
            target_kc_ids=["KC-1"],
        )
    for _ in range(2):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_repair_target",
            outcome="negative",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.hold_evaluated_count == 4
    assert len(signal.hold_subtype_breakdowns) == 2

    by_action = {b.action: b for b in signal.hold_subtype_breakdowns}
    assert "hold_target" in by_action
    assert "hold_repair_target" in by_action
    assert by_action["hold_target"].raw_count == 2
    assert by_action["hold_target"].positive_rate > 0.9
    assert by_action["hold_repair_target"].raw_count == 2
    assert by_action["hold_repair_target"].negative_rate > 0.9


def test_hold_subtype_rationale_when_multiple_subtypes(tmp_path):
    """Rationale mentions hold subtypes when more than one is present."""
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(2):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="positive",
            target_kc_ids=["KC-1"],
        )
    _outcome_event(
        store,
        student_id=str(student),
        action="hold_bridge_target",
        outcome="negative",
        target_kc_ids=["KC-1"],
    )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.rationale is not None
    assert "Hold subtypes" in signal.rationale
    assert "target:" in signal.rationale
    assert "bridge_target:" in signal.rationale


def test_prerequisite_negative_rate_raises_threshold(tmp_path):
    """When prerequisite rebuilds mostly fail, threshold is raised."""
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(4):
        _outcome_event(
            store,
            student_id=str(student),
            action="rebuild_prerequisite_first",
            outcome="negative",
            target_kc_ids=["KC-prereq"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.prerequisite_evaluated_count == 4
    assert signal.prerequisite_threshold_adjustment > 0.0
    assert "Prerequisite outcomes" in signal.rationale
    assert "raising" in signal.rationale


def test_prerequisite_positive_rate_lowers_threshold(tmp_path):
    """When prerequisite rebuilds reliably help, threshold is lowered."""
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(4):
        _outcome_event(
            store,
            student_id=str(student),
            action="rebuild_prerequisite_first",
            outcome="positive",
            target_kc_ids=["KC-prereq"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.prerequisite_evaluated_count == 4
    assert signal.prerequisite_threshold_adjustment < 0.0


def test_prerequisite_threshold_adjustment_bounded(tmp_path):
    """Prerequisite adjustment is bounded at _MAX_PREREQUISITE_ADJUSTMENT."""
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(20):
        _outcome_event(
            store,
            student_id=str(student),
            action="rebuild_prerequisite_first",
            outcome="negative",
            target_kc_ids=["KC-prereq"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.prerequisite_threshold_adjustment <= 0.04
    assert signal.prerequisite_threshold_adjustment > 0.0


def test_weighted_rates_present_on_signal(tmp_path):
    """Signal carries recency-weighted rates alongside raw rates."""
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(3):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="positive",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    # All events are recent (just created), so weighted rate should match raw rate.
    assert signal.hold_weighted_positive_rate == signal.hold_positive_rate
    assert signal.hold_weighted_negative_rate == signal.hold_negative_rate


def test_recency_weighted_rationale_present(tmp_path):
    """Rationale includes recency-weighted percentage breakdown."""
    store = _store(tmp_path)
    student = uuid4()

    for _ in range(3):
        _outcome_event(
            store,
            student_id=str(student),
            action="hold_target",
            outcome="positive",
            target_kc_ids=["KC-1"],
        )

    service = ProgressionOutcomeSignalService(audit_store=store)
    signal = service.signal_for_student(student_id=student)

    assert signal.rationale is not None
    assert "recency-weighted" in signal.rationale
