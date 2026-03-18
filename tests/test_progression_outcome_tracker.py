from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.progression_outcome_tracker import ProgressionOutcomeTracker
from dibble.storage import ensure_database


def _store(tmp_path) -> SQLiteAuditStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    return SQLiteAuditStore(db)


def _decision_event(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    action: str,
    target_kc_ids: list[str],
    stage: str = "target",
    avg_mastery: float | None = None,
    minutes_ago: int = 60,
):
    """Write a content.generate event with progression metadata."""
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
    """Write a learner.observe event for the given KCs."""
    return audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "target_kc_ids": target_kc_ids,
        },
    )


def test_positive_outcome_for_hold_when_mastery_improved(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

    _decision_event(
        store,
        student_id=student,
        action="hold_target",
        target_kc_ids=["KC-1"],
        avg_mastery=0.4,
    )
    _observation_event(store, student_id=student, target_kc_ids=["KC-1"])
    _observation_event(store, student_id=student, target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.75},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"
    assert outcomes[0].decision_action == "hold_target"
    assert outcomes[0].observation_count_since == 2
    assert "0.75" in outcomes[0].rationale


def test_negative_outcome_for_hold_when_mastery_stuck(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

    _decision_event(
        store,
        student_id=student,
        action="hold_repair_target",
        target_kc_ids=["KC-1"],
        stage="repair",
        avg_mastery=0.35,
    )
    for _ in range(4):
        _observation_event(store, student_id=student, target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.33},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "negative"
    assert outcomes[0].decision_action == "hold_repair_target"
    assert "stuck" in outcomes[0].rationale


def test_positive_outcome_for_transfer_when_mastery_high(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

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
        current_kc_mastery={"KC-2": 0.82},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"
    assert "0.82" in outcomes[0].rationale


def test_negative_outcome_for_transfer_when_mastery_low(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

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
        current_kc_mastery={"KC-2": 0.38},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "negative"
    assert "premature" in outcomes[0].rationale


def test_positive_outcome_for_prerequisite_rebuild(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

    _decision_event(
        store,
        student_id=student,
        action="rebuild_prerequisite_first",
        target_kc_ids=["KC-prereq"],
        stage="repair",
        avg_mastery=0.3,
    )
    _observation_event(store, student_id=student, target_kc_ids=["KC-prereq"])
    _observation_event(store, student_id=student, target_kc_ids=["KC-prereq"])

    outcomes = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-prereq": 0.55},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"
    assert "improved" in outcomes[0].rationale


def test_inconclusive_when_insufficient_evidence(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

    _decision_event(
        store,
        student_id=student,
        action="hold_target",
        target_kc_ids=["KC-1"],
        avg_mastery=0.4,
    )
    # Only 1 observation — below the minimum of 2 for holds
    _observation_event(store, student_id=student, target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.8},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "inconclusive"


def test_idempotency_does_not_reevaluate_recorded_outcomes(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

    _decision_event(
        store,
        student_id=student,
        action="hold_target",
        target_kc_ids=["KC-1"],
        avg_mastery=0.4,
    )
    _observation_event(store, student_id=student, target_kc_ids=["KC-1"])
    _observation_event(store, student_id=student, target_kc_ids=["KC-1"])

    # First evaluation
    outcomes = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.75},
    )
    assert len(outcomes) == 1
    tracker.record_outcomes(outcomes)

    # Second evaluation should return nothing (already recorded)
    outcomes_again = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.8},
    )
    assert len(outcomes_again) == 0


def test_record_outcomes_persists_audit_events(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

    _decision_event(
        store,
        student_id=student,
        action="hold_target",
        target_kc_ids=["KC-1"],
        avg_mastery=0.4,
    )
    _observation_event(store, student_id=student, target_kc_ids=["KC-1"])
    _observation_event(store, student_id=student, target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.75},
    )
    tracker.record_outcomes(outcomes)

    # Verify the audit event was written
    all_events = store.list(limit=100)
    outcome_events = [e for e in all_events if e.event_type == "progression.outcome"]
    assert len(outcome_events) == 1
    assert outcome_events[0].payload["outcome"] == "positive"
    assert outcome_events[0].payload["decision_action"] == "hold_target"
    assert str(outcome_events[0].student_id) == student


def test_ignores_observations_for_different_kcs(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = ProgressionOutcomeTracker(audit_store=store)

    _decision_event(
        store,
        student_id=student,
        action="hold_target",
        target_kc_ids=["KC-1"],
        avg_mastery=0.4,
    )
    # Observations for different KC — should not count
    _observation_event(store, student_id=student, target_kc_ids=["KC-other"])
    _observation_event(store, student_id=student, target_kc_ids=["KC-other"])

    outcomes = tracker.evaluate_recent_decisions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.9},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "inconclusive"
    assert outcomes[0].observation_count_since == 0
