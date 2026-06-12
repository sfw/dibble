from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.telemetry import AuditEvent
from dibble.services.mastery_progression_measurement import (
    MasteryProgressionMeasurementService,
)


class StubAuditStore:
    def __init__(self, events: list[AuditEvent]) -> None:
        self._events = events

    def list(self, *, limit: int = 50) -> list[AuditEvent]:
        return self._events[:limit]


def test_mastery_progression_measurement_computes_all_required_metrics() -> None:
    student_id = uuid4()
    other_student_id = uuid4()
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        _progression_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=8),
            action="hold_target",
            outcome="positive",
        ),
        _progression_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=7),
            action="hold_repair_target",
            outcome="negative",
        ),
        _progression_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=6),
            action="hold_bridge_target",
            outcome="inconclusive",
        ),
        _progression_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=5),
            action="attempt_transfer",
            outcome="positive",
        ),
        _progression_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=4),
            action="attempt_transfer",
            outcome="negative",
        ),
        _progression_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=3),
            action="rebuild_prerequisite_first",
            outcome="positive",
        ),
        _transition_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=2),
            outcome_id="OUT-1",
            from_state="mastered",
            to_state="ready",
        ),
        _transition_event(
            student_id=student_id,
            created_at=base + timedelta(minutes=1),
            outcome_id="OUT-2",
            from_state="ready",
            to_state="mastered",
        ),
        _transition_event(
            student_id=student_id,
            created_at=base,
            outcome_id="OUT-1",
            from_state="ready",
            to_state="mastered",
        ),
        _transition_event(
            student_id=other_student_id,
            created_at=base,
            outcome_id="OUT-OTHER",
            from_state="ready",
            to_state="mastered",
        ),
    ]
    service = MasteryProgressionMeasurementService(
        audit_store=StubAuditStore(events)
    )

    summary = service.summarize(
        learner_id=student_id,
        limit=20,
        lookback_days=365,
    )

    assert summary.scope == "learner"
    assert summary.learner_id == str(student_id)
    assert summary.hold_positive_rate.numerator == 1
    assert summary.hold_positive_rate.denominator == 2
    assert summary.hold_positive_rate.rate == 0.5
    assert summary.transfer_positive_rate.rate == 0.5
    assert summary.prerequisite_rebuild_positive_rate.rate == 1.0
    assert summary.release_regret_rate.rate == 0.5
    assert summary.over_hold_rate.rate == 0.5
    assert summary.false_positive_mastery_rate.numerator == 1
    assert summary.false_positive_mastery_rate.denominator == 2
    assert summary.false_positive_mastery_rate.rate == 0.5
    assert summary.outcome_mastery_stability.numerator == 1
    assert summary.outcome_mastery_stability.denominator == 2
    assert summary.outcome_mastery_stability.rate == 0.5
    assert summary.progression_outcome_event_count == 6
    assert summary.outcome_transition_event_count == 3


def test_mastery_progression_measurement_returns_empty_rates_without_evidence() -> None:
    service = MasteryProgressionMeasurementService(audit_store=StubAuditStore([]))

    summary = service.summarize(limit=10)

    assert summary.scope == "aggregate"
    assert summary.hold_positive_rate.rate is None
    assert summary.false_positive_mastery_rate.rate is None
    assert summary.outcome_mastery_stability.rate is None


def _progression_event(
    *,
    student_id,
    created_at: datetime,
    action: str,
    outcome: str,
) -> AuditEvent:
    return AuditEvent(
        event_id=f"progression-{created_at.timestamp()}",
        event_type="progression.outcome",
        status=outcome,
        student_id=student_id,
        created_at=created_at,
        payload={
            "decision_action": action,
            "outcome": outcome,
        },
    )


def _transition_event(
    *,
    student_id,
    created_at: datetime,
    outcome_id: str,
    from_state: str,
    to_state: str,
) -> AuditEvent:
    return AuditEvent(
        event_id=f"transition-{outcome_id}-{created_at.timestamp()}",
        event_type="curriculum.outcome.transition",
        status=to_state,
        student_id=student_id,
        created_at=created_at,
        payload={
            "outcome_id": outcome_id,
            "from_state": from_state,
            "to_state": to_state,
        },
    )
