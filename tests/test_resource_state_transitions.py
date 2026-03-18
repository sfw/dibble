"""Tests for resource state transition tracking (ADAPT-006 + ORCH-001)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from dibble.models.profile import CurriculumResourceProgressSummary
from dibble.services.resource_state_transitions import (
    ResourceStateTransitionTracker,
)


class StubAuditStore:
    """Minimal audit store for transition tracking tests."""

    def __init__(self, events: list | None = None) -> None:
        self._events = list(events or [])

    def list(self, limit: int = 100):
        return self._events[:limit]

    def append(self, *, event_type: str, status: str, student_id: str, payload: dict):
        self._events.insert(
            0,
            _AuditEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                status=status,
                student_id=student_id,
                payload=payload,
                created_at=datetime.now(timezone.utc),
            ),
        )


class _AuditEvent:
    def __init__(
        self,
        *,
        event_id: str,
        event_type: str,
        status: str,
        student_id: str,
        payload: dict,
        created_at: datetime,
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.status = status
        self.student_id = student_id
        self.payload = payload
        self.created_at = created_at


def _resource(
    resource_id: str,
    state: str,
    mastery_quality: str | None = None,
    mastery_ratio: float = 0.5,
) -> CurriculumResourceProgressSummary:
    return CurriculumResourceProgressSummary(
        resource_id=resource_id,
        title=f"Resource {resource_id}",
        state=state,
        mastery_ratio=mastery_ratio,
        mastery_quality=mastery_quality,
    )


STUDENT_ID = str(uuid4())


def test_first_observation_records_unseen_to_current():
    """Resources seen for the first time should record transitions from 'unseen'."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    resources = [
        _resource("R1", "ready"),
        _resource("R2", "blocked"),
    ]
    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=resources,
    )

    assert len(transitions) == 2
    assert transitions[0].from_state == "unseen"
    assert transitions[0].to_state == "ready"
    assert transitions[1].from_state == "unseen"
    assert transitions[1].to_state == "blocked"


def test_no_transitions_when_states_unchanged():
    """When resources have the same state as before, no transitions are emitted."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    resources = [_resource("R1", "ready")]

    # First build: records unseen -> ready.
    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=resources,
    )
    tracker.record_transitions(transitions)
    assert len(transitions) == 1

    # Second build: same state, no transitions.
    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=resources,
    )
    assert len(transitions) == 0


def test_state_change_records_transition():
    """A change from ready to mastered should be recorded."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    # First build: ready.
    tracker.record_transitions(
        tracker.detect_transitions(
            student_id=STUDENT_ID,
            current_resources=[_resource("R1", "ready")],
        )
    )

    # Second build: mastered.
    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=[_resource("R1", "mastered", mastery_ratio=0.9)],
    )
    assert len(transitions) == 1
    assert transitions[0].from_state == "ready"
    assert transitions[0].to_state == "mastered"
    assert transitions[0].mastery_ratio == 0.9


def test_quality_gate_involved_when_gating_active():
    """Transitions involving quality gate signals should be flagged."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    # First build: mastery blocked by quality gate.
    tracker.record_transitions(
        tracker.detect_transitions(
            student_id=STUDENT_ID,
            current_resources=[
                _resource("R1", "ready", mastery_quality="support_dependent")
            ],
        )
    )

    # Second build: gate clears, resource is mastered.
    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=[_resource("R1", "mastered")],
    )
    assert len(transitions) == 1
    assert transitions[0].quality_gate_involved is True
    assert transitions[0].from_mastery_quality == "support_dependent"
    assert transitions[0].to_mastery_quality is None
    assert "cleared" in transitions[0].rationale.lower()


def test_quality_gate_activating():
    """When quality gate activates on a resource, it should be flagged."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    # First build: ready, no gate.
    tracker.record_transitions(
        tracker.detect_transitions(
            student_id=STUDENT_ID,
            current_resources=[_resource("R1", "ready")],
        )
    )

    # Second build: still ready but now with fragile quality gate.
    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=[_resource("R1", "ready", mastery_quality="fragile")],
    )
    assert len(transitions) == 1
    assert transitions[0].quality_gate_involved is True
    assert transitions[0].to_mastery_quality == "fragile"
    assert "active" in transitions[0].rationale.lower()


def test_mastered_to_ready_regression():
    """A resource that loses mastery (e.g. due to decay) should record a regression."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    tracker.record_transitions(
        tracker.detect_transitions(
            student_id=STUDENT_ID,
            current_resources=[_resource("R1", "mastered", mastery_ratio=0.85)],
        )
    )

    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=[_resource("R1", "ready", mastery_ratio=0.55)],
    )
    assert len(transitions) == 1
    assert transitions[0].from_state == "mastered"
    assert transitions[0].to_state == "ready"


def test_only_changed_resources_emit_transitions():
    """Only resources whose state changed should produce transitions."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    tracker.record_transitions(
        tracker.detect_transitions(
            student_id=STUDENT_ID,
            current_resources=[
                _resource("R1", "ready"),
                _resource("R2", "blocked"),
            ],
        )
    )

    # R1 changes, R2 stays the same.
    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=[
            _resource("R1", "active"),
            _resource("R2", "blocked"),
        ],
    )
    assert len(transitions) == 1
    assert transitions[0].resource_id == "R1"


def test_recording_persists_events():
    """Recording transitions should add events to the audit store."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    transitions = tracker.detect_transitions(
        student_id=STUDENT_ID,
        current_resources=[_resource("R1", "ready")],
    )
    tracker.record_transitions(transitions)

    events = store.list(limit=10)
    assert len(events) == 1
    assert events[0].event_type == "curriculum.resource.transition"
    assert events[0].payload["resource_id"] == "R1"
    assert events[0].payload["from_state"] == "unseen"
    assert events[0].payload["to_state"] == "ready"


def test_different_students_are_isolated():
    """Transitions for different students should not interfere."""
    store = StubAuditStore()
    tracker = ResourceStateTransitionTracker(audit_store=store)

    student_a = str(uuid4())
    student_b = str(uuid4())

    tracker.record_transitions(
        tracker.detect_transitions(
            student_id=student_a,
            current_resources=[_resource("R1", "ready")],
        )
    )

    # Student B should see R1 as unseen even though A already has it.
    transitions = tracker.detect_transitions(
        student_id=student_b,
        current_resources=[_resource("R1", "mastered")],
    )
    assert len(transitions) == 1
    assert transitions[0].from_state == "unseen"
    assert transitions[0].to_state == "mastered"
