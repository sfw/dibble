"""Tracks curriculum resource state transitions for audit and outcome validation.

When curriculum progression is computed, this service compares the current
resource states against previously recorded states and emits
``curriculum.resource.transition`` audit events for any changes.  These
events form the audit trail that downstream outcome validation (e.g. the
mastery quality gate feedback loop) uses to measure whether progression
decisions are actually helping learners.

Design principles:
- Only transitions are recorded — unchanged resources produce no events.
- Quality gate metadata is captured so downstream services can evaluate
  whether the gate held appropriately.
- The previous state is reconstructed from the most recent transition
  events in the audit store, so there is no separate state store to manage.
"""

from __future__ import annotations

from dataclasses import dataclass

from dibble.models.profile import CurriculumResourceProgressSummary
from dibble.services.protocols import AuditStore


@dataclass(frozen=True, slots=True)
class ResourceStateTransition:
    """A single observed resource state change."""

    resource_id: str
    student_id: str
    from_state: str
    to_state: str
    from_mastery_quality: str | None = None
    to_mastery_quality: str | None = None
    mastery_ratio: float = 0.0
    quality_gate_involved: bool = False
    rationale: str = ""


@dataclass(slots=True)
class ResourceStateTransitionTracker:
    """Detects and records resource state transitions."""

    audit_store: AuditStore
    max_lookback_events: int = 800

    def detect_transitions(
        self,
        *,
        student_id: str,
        current_resources: list[CurriculumResourceProgressSummary],
    ) -> list[ResourceStateTransition]:
        """Compare current resource states against the last recorded states
        and return any transitions.

        Resources appearing for the first time are recorded as transitions
        from ``"unseen"`` to their current state.
        """
        previous_states = self._previous_states(student_id=student_id)
        transitions: list[ResourceStateTransition] = []

        for resource in current_resources:
            prev = previous_states.get(resource.resource_id)
            prev_state = prev["state"] if prev else "unseen"
            prev_quality = prev.get("mastery_quality") if prev else None

            if prev_state == resource.state and prev_quality == resource.mastery_quality:
                continue

            quality_gate_involved = (
                resource.mastery_quality in {"support_dependent", "fragile"}
                or (prev_quality in {"support_dependent", "fragile"} if prev else False)
            )

            rationale = self._transition_rationale(
                from_state=prev_state,
                to_state=resource.state,
                from_quality=prev_quality,
                to_quality=resource.mastery_quality,
                resource_rationale=resource.rationale,
            )

            transitions.append(
                ResourceStateTransition(
                    resource_id=resource.resource_id,
                    student_id=student_id,
                    from_state=prev_state,
                    to_state=resource.state,
                    from_mastery_quality=prev_quality,
                    to_mastery_quality=resource.mastery_quality,
                    mastery_ratio=resource.mastery_ratio,
                    quality_gate_involved=quality_gate_involved,
                    rationale=rationale,
                )
            )

        return transitions

    def record_transitions(
        self, transitions: list[ResourceStateTransition]
    ) -> None:
        """Persist transitions as audit events."""
        for t in transitions:
            self.audit_store.append(
                event_type="curriculum.resource.transition",
                status=t.to_state,
                student_id=t.student_id,
                payload={
                    "resource_id": t.resource_id,
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "from_mastery_quality": t.from_mastery_quality,
                    "to_mastery_quality": t.to_mastery_quality,
                    "mastery_ratio": t.mastery_ratio,
                    "quality_gate_involved": t.quality_gate_involved,
                    "rationale": t.rationale,
                },
            )

    def _previous_states(
        self, *, student_id: str
    ) -> dict[str, dict[str, object]]:
        """Reconstruct the most recent known state per resource from
        prior ``curriculum.resource.transition`` events."""
        events = self.audit_store.list(limit=self.max_lookback_events)
        states: dict[str, dict[str, object]] = {}

        # Events are returned most-recent-first.  We want the latest
        # transition per resource_id.
        for event in events:
            if event.event_type != "curriculum.resource.transition":
                continue
            if event.student_id is None or str(event.student_id) != student_id:
                continue
            resource_id = event.payload.get("resource_id")
            if resource_id is None or resource_id in states:
                continue
            states[str(resource_id)] = {
                "state": str(event.payload.get("to_state", "unknown")),
                "mastery_quality": event.payload.get("to_mastery_quality"),
            }

        return states

    def _transition_rationale(
        self,
        *,
        from_state: str,
        to_state: str,
        from_quality: str | None,
        to_quality: str | None,
        resource_rationale: str | None,
    ) -> str:
        parts: list[str] = []

        if from_state == "unseen":
            parts.append(f"Resource first observed in state '{to_state}'.")
        else:
            parts.append(f"State changed from '{from_state}' to '{to_state}'.")

        if from_quality != to_quality:
            if to_quality in {"support_dependent", "fragile"}:
                parts.append(
                    f"Quality gate now active ({to_quality})."
                )
            elif from_quality in {"support_dependent", "fragile"} and to_quality not in {
                "support_dependent",
                "fragile",
            }:
                parts.append(
                    f"Quality gate cleared (was {from_quality})."
                )

        if resource_rationale:
            parts.append(resource_rationale)

        return " ".join(parts)
