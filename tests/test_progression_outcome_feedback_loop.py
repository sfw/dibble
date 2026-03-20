"""Integration tests for the full progression outcome feedback loop.

These tests verify the end-to-end cycle:
1. ProgressionOutcomeTracker evaluates and records outcome verdicts
2. ProgressionOutcomeSignalService aggregates those verdicts into signals
3. ProgressionOwnershipService uses those signals to adjust hold/transfer thresholds

This is the validation loop that ADAPT-006 and DATA-004 need to tell us
whether our progression heuristics are actually helping learners.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.progression_outcome_signals import (
    ProgressionOutcomeSignalService,
)
from dibble.services.progression_outcome_tracker import ProgressionOutcomeTracker
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def _store(tmp_path) -> SQLiteAuditStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    conn = create_connection(db)
    return SQLiteAuditStore(conn)


def _decision_event(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    action: str,
    target_kc_ids: list[str],
    stage: str = "target",
    avg_mastery: float | None = None,
):
    return audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "progression_action": action,
            "progression_target_stage": stage,
            "applied_target_kc_ids": target_kc_ids,
            "progression_average_observed_mastery": avg_mastery,
        },
    )


def _observation_event(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    target_kc_ids: list[str],
):
    return audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={"target_kc_ids": target_kc_ids},
    )


def test_full_loop_negative_holds_raise_signal_threshold(tmp_path):
    """Hold decisions that consistently fail should produce a positive
    hold_threshold_adjustment, making future holds harder to trigger."""
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)
    signal_service = ProgressionOutcomeSignalService(audit_store=store)

    # Simulate 3 hold decisions that all fail (learner stuck at baseline).
    for i in range(3):
        _decision_event(
            store,
            student_id=student,
            action="hold_target",
            target_kc_ids=["KC-1"],
            avg_mastery=0.35,
        )
        # 4+ observations each so verdicts are not inconclusive
        for _ in range(4):
            _observation_event(store, student_id=student, target_kc_ids=["KC-1"])

        outcomes = tracker.evaluate_recent_decisions(
            student_id=student,
            current_kc_mastery={"KC-1": 0.33},  # stuck below baseline
        )
        tracker.record_outcomes(outcomes)

    # Now check the signal
    signal = signal_service.signal_for_student(
        student_id=UUID(student),
        target_kc_ids=["KC-1"],
    )

    assert signal.hold_evaluated_count >= 3
    assert signal.hold_negative_rate >= 0.5
    assert signal.hold_threshold_adjustment > 0.0, (
        "Negative hold outcomes should raise the threshold"
    )


def test_full_loop_positive_holds_lower_signal_threshold(tmp_path):
    """Hold decisions that consistently help should produce a negative
    hold_threshold_adjustment, making future holds easier to trigger."""
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)
    signal_service = ProgressionOutcomeSignalService(audit_store=store)

    # Simulate 4 hold decisions that all succeed (learner masters target).
    for i in range(4):
        _decision_event(
            store,
            student_id=student,
            action="hold_target",
            target_kc_ids=["KC-1"],
            avg_mastery=0.4,
        )
        for _ in range(3):
            _observation_event(store, student_id=student, target_kc_ids=["KC-1"])

        outcomes = tracker.evaluate_recent_decisions(
            student_id=student,
            current_kc_mastery={"KC-1": 0.8},  # mastery improved well
        )
        tracker.record_outcomes(outcomes)

    signal = signal_service.signal_for_student(
        student_id=UUID(student),
        target_kc_ids=["KC-1"],
    )

    assert signal.hold_evaluated_count >= 4
    assert signal.hold_positive_rate >= 0.75
    assert signal.hold_threshold_adjustment < 0.0, (
        "Positive hold outcomes should lower the threshold"
    )


def test_full_loop_negative_transfers_raise_confidence(tmp_path):
    """Transfer decisions that fail should raise the confidence required
    for future transfers."""
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)
    signal_service = ProgressionOutcomeSignalService(audit_store=store)

    # 2 premature transfers
    for _ in range(2):
        _decision_event(
            store,
            student_id=student,
            action="attempt_transfer",
            target_kc_ids=["KC-2"],
            stage="transfer",
        )
        _observation_event(store, student_id=student, target_kc_ids=["KC-2"])

        outcomes = tracker.evaluate_recent_decisions(
            student_id=student,
            current_kc_mastery={"KC-2": 0.35},  # low mastery after transfer
        )
        tracker.record_outcomes(outcomes)

    signal = signal_service.signal_for_student(
        student_id=UUID(student),
        target_kc_ids=["KC-2"],
    )

    assert signal.transfer_evaluated_count >= 2
    assert signal.transfer_negative_rate >= 0.5
    assert signal.transfer_confidence_adjustment > 0.0, (
        "Negative transfer outcomes should raise the confidence requirement"
    )


def test_outcome_signal_only_counts_matching_student(tmp_path):
    """Outcome events for a different student should not affect the signal."""
    store = _store(tmp_path)
    student_a = str(uuid4())
    student_b = str(uuid4())

    # Write negative outcomes for student_a
    for _ in range(3):
        store.append(
            event_type="progression.outcome",
            status="negative",
            student_id=student_a,
            payload={
                "decision_event_id": str(uuid4()),
                "decision_action": "hold_target",
                "decision_target_kc_ids": ["KC-1"],
                "outcome": "negative",
            },
        )

    signal_service = ProgressionOutcomeSignalService(audit_store=store)
    signal_b = signal_service.signal_for_student(student_id=UUID(student_b))

    assert signal_b.hold_evaluated_count == 0
    assert signal_b.hold_threshold_adjustment == 0.0
