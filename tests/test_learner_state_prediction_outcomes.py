from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learner_state_prediction_outcomes import (
    LearnerStatePredictionOutcomeTracker,
)
from dibble.storage import ensure_database


def _store(tmp_path) -> SQLiteAuditStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    return SQLiteAuditStore(db)


def _observation_with_prediction(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    signal: str,
    confidence: float = 0.7,
    target_kc_ids: list[str] | None = None,
    completed: bool = True,
    observation_average_recent_mastery: float = 0.5,
):
    """Write a learner.observe event with a current evidence signal."""
    return audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "current_evidence_signal": signal,
            "current_evidence_confidence": confidence,
            "target_kc_ids": target_kc_ids or [],
            "completed": completed,
            "observation_mastery_applied": completed,
            "observation_average_recent_mastery": observation_average_recent_mastery,
        },
    )


def _subsequent_observation(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    completed: bool = True,
    target_kc_ids: list[str] | None = None,
):
    """Write a subsequent learner.observe event (no evidence signal)."""
    return audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "target_kc_ids": target_kc_ids or [],
            "completed": completed,
            "observation_mastery_applied": completed,
        },
    )


def test_positive_productive_struggle_when_completion_stays_high(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store,
        student_id=student,
        signal="productive_struggle",
        target_kc_ids=["KC-1"],
    )
    _subsequent_observation(store, student_id=student, completed=True)
    _subsequent_observation(store, student_id=student, completed=True)

    outcomes = tracker.evaluate_recent_predictions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.65},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"
    assert outcomes[0].predicted_signal == "productive_struggle"
    assert outcomes[0].subsequent_observation_count == 2


def test_negative_productive_struggle_when_mastery_declines(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store,
        student_id=student,
        signal="productive_struggle",
        target_kc_ids=["KC-1"],
        observation_average_recent_mastery=0.6,
    )
    _subsequent_observation(store, student_id=student, completed=False)
    _subsequent_observation(store, student_id=student, completed=False)

    outcomes = tracker.evaluate_recent_predictions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.42},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "negative"
    assert "contradicted" in outcomes[0].rationale


def test_positive_overload_when_completion_stays_low(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="overload"
    )
    _subsequent_observation(store, student_id=student, completed=False)
    _subsequent_observation(store, student_id=student, completed=False)
    _subsequent_observation(store, student_id=student, completed=False)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"
    assert outcomes[0].predicted_signal == "overload"


def test_negative_overload_when_learner_recovers(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="overload"
    )
    _subsequent_observation(store, student_id=student, completed=True)
    _subsequent_observation(store, student_id=student, completed=True)
    _subsequent_observation(store, student_id=student, completed=True)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "negative"
    assert "contradicted" in outcomes[0].rationale


def test_positive_disengagement_when_low_completion_continues(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="disengagement"
    )
    _subsequent_observation(store, student_id=student, completed=False)
    _subsequent_observation(store, student_id=student, completed=False)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"


def test_negative_disengagement_when_learner_re_engages(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="disengagement"
    )
    _subsequent_observation(store, student_id=student, completed=True)
    _subsequent_observation(store, student_id=student, completed=True)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "negative"


def test_positive_support_dependence_when_completion_without_mastery(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store,
        student_id=student,
        signal="support_dependence",
        target_kc_ids=["KC-1"],
        observation_average_recent_mastery=0.5,
    )
    _subsequent_observation(store, student_id=student, completed=True)
    _subsequent_observation(store, student_id=student, completed=True)

    outcomes = tracker.evaluate_recent_predictions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.52},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"
    assert "confirmed" in outcomes[0].rationale


def test_negative_support_dependence_when_mastery_improves(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store,
        student_id=student,
        signal="support_dependence",
        target_kc_ids=["KC-1"],
        observation_average_recent_mastery=0.5,
    )
    _subsequent_observation(store, student_id=student, completed=True)
    _subsequent_observation(store, student_id=student, completed=True)

    outcomes = tracker.evaluate_recent_predictions(
        student_id=student,
        current_kc_mastery={"KC-1": 0.72},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "negative"
    assert "independence" in outcomes[0].rationale


def test_insufficient_subsequent_observations_returns_empty(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="overload"
    )
    # Only one subsequent
    _subsequent_observation(store, student_id=student, completed=False)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)

    assert len(outcomes) == 0


def test_steady_signals_are_skipped(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="steady"
    )
    _subsequent_observation(store, student_id=student, completed=True)
    _subsequent_observation(store, student_id=student, completed=True)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)
    assert len(outcomes) == 0


def test_already_evaluated_predictions_are_skipped(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="overload"
    )
    _subsequent_observation(store, student_id=student, completed=False)
    _subsequent_observation(store, student_id=student, completed=False)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)
    assert len(outcomes) == 1
    tracker.record_outcomes(outcomes)

    # Second evaluation should skip the already-evaluated prediction
    outcomes2 = tracker.evaluate_recent_predictions(student_id=student)
    assert len(outcomes2) == 0


def test_record_outcomes_persists_audit_events(tmp_path):
    store = _store(tmp_path)
    student = str(uuid4())
    tracker = LearnerStatePredictionOutcomeTracker(audit_store=store)

    _observation_with_prediction(
        store, student_id=student, signal="overload"
    )
    _subsequent_observation(store, student_id=student, completed=False)
    _subsequent_observation(store, student_id=student, completed=False)

    outcomes = tracker.evaluate_recent_predictions(student_id=student)
    tracker.record_outcomes(outcomes)

    events = [
        e
        for e in store.list(limit=100)
        if e.event_type == "learner_state_prediction.outcome"
    ]
    assert len(events) == 1
    assert events[0].status == "positive"
    assert events[0].payload["predicted_signal"] == "overload"
