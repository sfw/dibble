from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learner_state_prediction_signals import (
    LearnerStatePredictionSignalService,
)
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def _store(tmp_path) -> SQLiteAuditStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    conn = create_connection(db)
    return SQLiteAuditStore(conn)


def _outcome_event(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    predicted_signal: str,
    outcome: str,
):
    """Write a learner_state_prediction.outcome event."""
    return audit_store.append(
        event_type="learner_state_prediction.outcome",
        status=outcome,
        student_id=student_id,
        payload={
            "predicted_signal": predicted_signal,
            "outcome": outcome,
        },
    )


def test_insufficient_outcomes_returns_default(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    service = LearnerStatePredictionSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=student)

    assert signal.evaluated_count == 0
    assert not signal.has_signal
    assert "Insufficient" in signal.rationale


def test_below_minimum_does_not_produce_signal(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    service = LearnerStatePredictionSignalService(audit_store=store)

    _outcome_event(
        store, student_id=student, predicted_signal="overload", outcome="positive"
    )
    _outcome_event(
        store, student_id=student, predicted_signal="overload", outcome="positive"
    )

    signal = service.signal_for_student(student_id=student)
    assert signal.evaluated_count == 2
    assert not signal.has_signal


def test_high_accuracy_signal(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    service = LearnerStatePredictionSignalService(audit_store=store)

    for _ in range(4):
        _outcome_event(
            store,
            student_id=student,
            predicted_signal="overload",
            outcome="positive",
        )
    _outcome_event(
        store,
        student_id=student,
        predicted_signal="overload",
        outcome="negative",
    )

    signal = service.signal_for_student(student_id=student)

    assert signal.has_signal
    assert signal.evaluated_count == 5
    assert signal.positive_count == 4
    assert signal.negative_count == 1
    assert signal.overall_accuracy == 0.8


def test_per_classification_breakdown(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    service = LearnerStatePredictionSignalService(audit_store=store)

    # Overload: 3 positive, 0 negative
    for _ in range(3):
        _outcome_event(
            store,
            student_id=student,
            predicted_signal="overload",
            outcome="positive",
        )
    # Productive struggle: 0 positive, 3 negative
    for _ in range(3):
        _outcome_event(
            store,
            student_id=student,
            predicted_signal="productive_struggle",
            outcome="negative",
        )

    signal = service.signal_for_student(student_id=student)

    assert signal.has_signal
    assert "overload" in signal.per_classification
    assert "productive_struggle" in signal.per_classification
    assert signal.per_classification["overload"].accuracy_rate == 1.0
    assert signal.per_classification["productive_struggle"].accuracy_rate == 0.0
    assert signal.strongest_classification == "overload"
    assert signal.weakest_classification == "productive_struggle"


def test_weak_classification_rationale(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    service = LearnerStatePredictionSignalService(audit_store=store)

    # Disengagement: 1 positive, 3 negative -> 25% accuracy
    _outcome_event(
        store,
        student_id=student,
        predicted_signal="disengagement",
        outcome="positive",
    )
    for _ in range(3):
        _outcome_event(
            store,
            student_id=student,
            predicted_signal="disengagement",
            outcome="negative",
        )

    signal = service.signal_for_student(student_id=student)

    assert signal.has_signal
    assert "Low-reliability" in signal.rationale
    assert "disengagement" in signal.rationale


def test_inconclusive_outcomes_are_excluded(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    service = LearnerStatePredictionSignalService(audit_store=store)

    # 3 inconclusive (shouldn't count)
    for _ in range(3):
        store.append(
            event_type="learner_state_prediction.outcome",
            status="inconclusive",
            student_id=student,
            payload={"predicted_signal": "overload", "outcome": "inconclusive"},
        )
    # 3 positive
    for _ in range(3):
        _outcome_event(
            store,
            student_id=student,
            predicted_signal="overload",
            outcome="positive",
        )

    signal = service.signal_for_student(student_id=student)

    assert signal.has_signal
    assert signal.evaluated_count == 3
    assert signal.overall_accuracy == 1.0


def test_mixed_classifications_overall_accuracy(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    service = LearnerStatePredictionSignalService(audit_store=store)

    # 2 correct overload, 1 wrong overload
    _outcome_event(
        store, student_id=student, predicted_signal="overload", outcome="positive"
    )
    _outcome_event(
        store, student_id=student, predicted_signal="overload", outcome="positive"
    )
    _outcome_event(
        store, student_id=student, predicted_signal="overload", outcome="negative"
    )
    # 1 correct disengagement, 1 wrong disengagement
    _outcome_event(
        store, student_id=student, predicted_signal="disengagement", outcome="positive"
    )
    _outcome_event(
        store, student_id=student, predicted_signal="disengagement", outcome="negative"
    )

    signal = service.signal_for_student(student_id=student)

    assert signal.has_signal
    assert signal.evaluated_count == 5
    assert signal.positive_count == 3
    assert signal.negative_count == 2
    assert signal.overall_accuracy == 0.6
