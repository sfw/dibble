"""Tests for mastery quality gate outcome tracking (ADAPT-006)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.services.mastery_quality_gate_outcomes import (
    MasteryQualityGateOutcomeTracker,
)


class _AuditEvent:
    def __init__(
        self,
        *,
        event_id: str = "",
        event_type: str = "",
        status: str = "",
        student_id: str | None = None,
        payload: dict | None = None,
        created_at: datetime | None = None,
    ):
        self.event_id = event_id or str(uuid4())
        self.event_type = event_type
        self.status = status
        self.student_id = student_id
        self.payload = payload or {}
        self.created_at = created_at or datetime.now(timezone.utc)


class StubAuditStore:
    def __init__(self, events: list | None = None) -> None:
        self._events = list(events or [])

    def list(self, limit: int = 100):
        return self._events[:limit]

    def append(self, *, event_type: str, status: str, student_id: str, payload: dict):
        self._events.insert(
            0,
            _AuditEvent(
                event_type=event_type,
                status=status,
                student_id=student_id,
                payload=payload,
            ),
        )


STUDENT = str(uuid4())
NOW = datetime.now(timezone.utc)


def _gate_hold_event(
    outcome_id: str,
    gate_signal: str = "support_dependent",
    mastery_ratio: float = 0.75,
    days_ago: float = 7.0,
    event_id: str = "",
) -> _AuditEvent:
    return _AuditEvent(
        event_id=event_id or str(uuid4()),
        event_type="curriculum.outcome.transition",
        status="ready",
        student_id=STUDENT,
        payload={
            "outcome_id": outcome_id,
            "from_state": "ready",
            "to_state": "ready",
            "from_mastery_quality": None,
            "to_mastery_quality": gate_signal,
            "mastery_ratio": mastery_ratio,
            "quality_gate_involved": True,
        },
        created_at=NOW - timedelta(days=days_ago),
    )


def _gate_release_event(outcome_id: str, days_ago: float = 1.0) -> _AuditEvent:
    return _AuditEvent(
        event_type="curriculum.outcome.transition",
        status="mastered",
        student_id=STUDENT,
        payload={
            "outcome_id": outcome_id,
            "from_state": "ready",
            "to_state": "mastered",
            "quality_gate_involved": True,
        },
        created_at=NOW - timedelta(days=days_ago),
    )


def test_positive_outcome_when_gate_released():
    """A gate hold that eventually leads to mastery should be positive."""
    hold_id = str(uuid4())
    store = StubAuditStore(
        [
            _gate_release_event("R1", days_ago=1),
            _gate_hold_event("R1", event_id=hold_id, days_ago=7),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.88},
    )
    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"
    assert outcomes[0].outcome_id == "R1"
    assert "mastery" in outcomes[0].rationale.lower()


def test_positive_outcome_when_mastery_improves():
    """A gate hold where mastery improved beyond threshold is positive."""
    store = StubAuditStore(
        [
            _gate_hold_event("R1", mastery_ratio=0.70, days_ago=5),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.82},
    )
    assert len(outcomes) == 1
    assert outcomes[0].outcome == "positive"


def test_negative_outcome_when_stalled():
    """A gate hold with no improvement after 14+ days is negative."""
    store = StubAuditStore(
        [
            _gate_hold_event("R1", mastery_ratio=0.75, days_ago=16),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.76},
    )
    assert len(outcomes) == 1
    assert outcomes[0].outcome == "negative"
    assert "conservative" in outcomes[0].rationale.lower()


def test_inconclusive_when_too_early():
    """A gate hold that is too recent should be inconclusive."""
    store = StubAuditStore(
        [
            _gate_hold_event("R1", days_ago=0.5),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.75},
    )
    assert len(outcomes) == 0  # filtered out by min days


def test_inconclusive_when_moderate_wait_no_improvement():
    """A gate hold with moderate wait and no improvement is inconclusive."""
    store = StubAuditStore(
        [
            _gate_hold_event("R1", mastery_ratio=0.75, days_ago=5),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.76},
    )
    assert len(outcomes) == 1
    assert outcomes[0].outcome == "inconclusive"


def test_already_evaluated_not_repeated():
    """Gate holds that already have an outcome event should be skipped."""
    hold_id = "hold-123"
    store = StubAuditStore(
        [
            _AuditEvent(
                event_type="mastery_quality_gate.outcome",
                status="positive",
                student_id=STUDENT,
                payload={"gate_event_id": hold_id},
            ),
            _gate_hold_event("R1", event_id=hold_id, days_ago=7),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.88},
    )
    assert len(outcomes) == 0


def test_recording_persists_events():
    """Recording outcomes should add events to the audit store."""
    store = StubAuditStore(
        [
            _gate_hold_event("R1", mastery_ratio=0.70, days_ago=5),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.82},
    )
    tracker.record_outcomes(outcomes)

    events = [
        e
        for e in store.list(limit=100)
        if e.event_type == "mastery_quality_gate.outcome"
    ]
    assert len(events) == 1
    assert events[0].payload["outcome"] == "positive"
    assert events[0].payload["outcome_id"] == "R1"


def test_fragile_gate_signal_tracked():
    """Fragile gate holds should be tracked with their signal type."""
    store = StubAuditStore(
        [
            _gate_hold_event(
                "R1", gate_signal="fragile", mastery_ratio=0.72, days_ago=5
            ),
        ]
    )
    tracker = MasteryQualityGateOutcomeTracker(audit_store=store)

    outcomes = tracker.evaluate_gate_outcomes(
        student_id=STUDENT,
        current_outcome_mastery={"R1": 0.80},
    )
    assert len(outcomes) == 1
    assert outcomes[0].gate_signal == "fragile"
    assert outcomes[0].outcome == "positive"
