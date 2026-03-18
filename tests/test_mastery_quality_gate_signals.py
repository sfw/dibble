"""Tests for mastery quality gate signal service (ADAPT-006)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.services.mastery_quality_gate_signals import (
    MasteryQualityGateSignalService,
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


NOW = datetime.now(timezone.utc)
STUDENT = uuid4()


def _outcome_event(
    verdict: str,
    gate_signal: str = "support_dependent",
    days_ago: float = 1.0,
) -> _AuditEvent:
    return _AuditEvent(
        event_type="mastery_quality_gate.outcome",
        status=verdict,
        student_id=str(STUDENT),
        payload={
            "outcome": verdict,
            "gate_signal": gate_signal,
        },
        created_at=NOW - timedelta(days=days_ago),
    )


def test_empty_signal_with_no_outcomes():
    """With no outcome events, the signal should be neutral."""
    store = StubAuditStore()
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert signal.evaluated_count == 0
    assert signal.confidence_threshold_adjustment == 0.0
    assert signal.rationale is None


def test_insufficient_outcomes_no_adjustment():
    """With fewer than the minimum outcomes, no adjustment is made."""
    store = StubAuditStore(
        [
            _outcome_event("positive"),
            _outcome_event("positive"),
        ]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert signal.evaluated_count == 2
    assert signal.confidence_threshold_adjustment == 0.0


def test_mostly_positive_outcomes_lower_threshold():
    """When gate holds mostly succeed, the confidence threshold should be lowered."""
    store = StubAuditStore(
        [
            _outcome_event("positive", days_ago=1),
            _outcome_event("positive", days_ago=2),
            _outcome_event("positive", days_ago=3),
            _outcome_event("positive", days_ago=4),
        ]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert signal.evaluated_count == 4
    assert signal.positive_rate == 1.0
    assert signal.confidence_threshold_adjustment < 0.0
    assert signal.rationale is not None
    assert "lowering" in signal.rationale.lower()


def test_mostly_negative_outcomes_raise_threshold():
    """When gate holds mostly fail, the confidence threshold should be raised."""
    store = StubAuditStore(
        [
            _outcome_event("negative", days_ago=1),
            _outcome_event("negative", days_ago=2),
            _outcome_event("negative", days_ago=3),
        ]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert signal.evaluated_count == 3
    assert signal.negative_rate == 1.0
    assert signal.confidence_threshold_adjustment > 0.0
    assert signal.rationale is not None
    assert "raising" in signal.rationale.lower()


def test_inconclusive_outcomes_are_excluded():
    """Inconclusive outcomes should not count toward the signal."""
    store = StubAuditStore(
        [
            _outcome_event("inconclusive", days_ago=1),
            _outcome_event("inconclusive", days_ago=2),
            _outcome_event("inconclusive", days_ago=3),
        ]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert signal.evaluated_count == 0
    assert signal.confidence_threshold_adjustment == 0.0


def test_mixed_outcomes_no_strong_adjustment():
    """A mix of positive and negative outcomes should not produce a strong adjustment."""
    store = StubAuditStore(
        [
            _outcome_event("positive", days_ago=1),
            _outcome_event("negative", days_ago=2),
            _outcome_event("positive", days_ago=3),
        ]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert signal.evaluated_count == 3
    assert signal.confidence_threshold_adjustment == 0.0


def test_per_signal_breakdowns_tracked():
    """The signal should break down outcomes by gate signal type."""
    store = StubAuditStore(
        [
            _outcome_event("positive", gate_signal="support_dependent", days_ago=1),
            _outcome_event("positive", gate_signal="support_dependent", days_ago=2),
            _outcome_event("negative", gate_signal="fragile", days_ago=3),
        ]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert len(signal.signal_breakdowns) == 2
    sd_breakdown = next(
        (b for b in signal.signal_breakdowns if b.signal == "support_dependent"), None
    )
    assert sd_breakdown is not None
    assert sd_breakdown.raw_count == 2


def test_different_students_isolated():
    """Outcomes for different students should not affect each other."""
    other_student = uuid4()
    store = StubAuditStore(
        [
            _outcome_event("negative", days_ago=1),
            _outcome_event("negative", days_ago=2),
            _outcome_event("negative", days_ago=3),
        ]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=other_student)
    assert signal.evaluated_count == 0


def test_adjustment_is_bounded():
    """The adjustment should never exceed the maximum bound."""
    store = StubAuditStore(
        [_outcome_event("negative", days_ago=i) for i in range(1, 20)]
    )
    service = MasteryQualityGateSignalService(audit_store=store)

    signal = service.signal_for_student(student_id=STUDENT)
    assert signal.confidence_threshold_adjustment <= 0.08


def test_quality_gate_confidence_adjustment_in_progression():
    """Integration: the quality gate confidence threshold should be adjusted
    when the signal service reports positive outcomes."""
    from dibble.services.learner_progression_service import (
        LearnerProgressionService,
        MASTERY_QUALITY_GATE_CONFIDENCE,
    )

    class StubSignalService:
        def signal_for_student(self, *, student_id):
            from dibble.services.mastery_quality_gate_signals import (
                MasteryQualityGateSignal,
            )

            return MasteryQualityGateSignal(confidence_threshold_adjustment=-0.05)

    service = LearnerProgressionService(
        profile_store=None,
        curriculum_store=None,
        knowledge_component_store=None,
        learner_flow_service=None,
        quality_gate_signal_service=StubSignalService(),
    )

    effective = service._effective_quality_gate_confidence(student_id=uuid4())
    assert effective == MASTERY_QUALITY_GATE_CONFIDENCE - 0.05
