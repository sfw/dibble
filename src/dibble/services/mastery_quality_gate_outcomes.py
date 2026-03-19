"""Evaluates whether mastery quality gate decisions led to good outcomes.

The mastery quality gate (ADAPT-006) prevents outcomes from being marked
mastered when their KCs show ``support_dependent`` or ``fragile`` evidence.
This service closes the feedback loop by evaluating whether those gate holds
actually helped — did the learner eventually demonstrate independent mastery,
or did the gate just create friction without improving outcomes?

The tracker reads ``curriculum.outcome.transition`` events to find:
1. Gate holds: transitions where quality gate was active (to_state != mastered
   because quality gate prevented it).
2. Gate releases: subsequent transitions where the same outcome achieved
   mastered after previously being held by the quality gate.
3. Gate stalls: outcomes held by the gate for extended periods without
   mastery improvement.

Outcomes are recorded as ``mastery_quality_gate.outcome`` audit events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.services.protocols import AuditStore


@dataclass(frozen=True, slots=True)
class QualityGateOutcome:
    """A single evaluated quality gate decision outcome."""

    outcome_id: str
    student_id: str
    gate_signal: str  # support_dependent or fragile
    outcome: str  # positive, negative, inconclusive
    mastery_at_gate: float = 0.0
    mastery_at_evaluation: float = 0.0
    transition_count_since_gate: int = 0
    days_since_gate: float = 0.0
    rationale: str = ""


# How long to wait before evaluating a gate hold.
_MIN_DAYS_FOR_EVALUATION = 1.0

# A gate hold with no mastery improvement after this many days is negative.
_STALL_DAYS = 14.0

# Minimum mastery improvement to consider the gate hold successful.
_IMPROVEMENT_THRESHOLD = 0.05


@dataclass(slots=True)
class MasteryQualityGateOutcomeTracker:
    """Evaluates recent quality gate holds against subsequent evidence."""

    audit_store: AuditStore
    max_lookback_events: int = 800

    def evaluate_gate_outcomes(
        self,
        *,
        student_id: str,
        current_outcome_mastery: dict[str, float],
    ) -> list[QualityGateOutcome]:
        """Look back at quality gate holds and evaluate whether they helped.

        Returns only outcomes not already recorded.
        """
        events = self.audit_store.list(limit=self.max_lookback_events)
        now = datetime.now(timezone.utc)

        # Find gate hold events (transitions where quality_gate_involved=True
        # and to_state != mastered).
        gate_holds: list[dict] = []
        # Find gate release events (quality_gate_involved=True and to_state=mastered).
        gate_releases: dict[str, datetime] = {}
        # Already evaluated gate holds.
        already_evaluated: set[str] = set()

        for event in events:
            if event.student_id is None or str(event.student_id) != student_id:
                continue

            if event.event_type == "curriculum.outcome.transition":
                payload = event.payload
                if not payload.get("quality_gate_involved"):
                    continue

                outcome_id = str(payload.get("outcome_id", ""))
                to_state = str(payload.get("to_state", ""))

                if to_state == "mastered":
                    # This is a gate release — outcome achieved mastery
                    if outcome_id not in gate_releases:
                        gate_releases[outcome_id] = _parse_timestamp(event.created_at)
                elif to_state in {"ready", "active"}:
                    gate_holds.append(
                        {
                            "event_id": event.event_id,
                            "outcome_id": outcome_id,
                            "mastery_ratio": float(payload.get("mastery_ratio", 0.0)),
                            "gate_signal": str(
                                payload.get("to_mastery_quality", "unknown")
                            ),
                            "timestamp": _parse_timestamp(event.created_at),
                        }
                    )

            elif event.event_type == "mastery_quality_gate.outcome":
                gate_event_id = event.payload.get("gate_event_id")
                if gate_event_id:
                    already_evaluated.add(str(gate_event_id))

        outcomes: list[QualityGateOutcome] = []

        for hold in gate_holds:
            if hold["event_id"] in already_evaluated:
                continue

            outcome_id = hold["outcome_id"]
            days_since = (now - hold["timestamp"]).total_seconds() / 86_400.0

            if days_since < _MIN_DAYS_FOR_EVALUATION:
                continue

            current_mastery = current_outcome_mastery.get(outcome_id, 0.0)
            mastery_at_gate = hold["mastery_ratio"]
            improvement = current_mastery - mastery_at_gate

            # Count transitions since the gate hold for this outcome.
            transitions_since = sum(
                1
                for e in events
                if e.event_type == "curriculum.outcome.transition"
                and e.student_id is not None
                and str(e.student_id) == student_id
                and e.payload.get("outcome_id") == outcome_id
                and _parse_timestamp(e.created_at) > hold["timestamp"]
            )

            outcome = self._evaluate(
                outcome_id=outcome_id,
                gate_signal=hold["gate_signal"],
                mastery_at_gate=mastery_at_gate,
                current_mastery=current_mastery,
                improvement=improvement,
                days_since=days_since,
                released=outcome_id in gate_releases,
            )

            outcomes.append(
                QualityGateOutcome(
                    outcome_id=outcome_id,
                    student_id=student_id,
                    gate_signal=hold["gate_signal"],
                    outcome=outcome.verdict,
                    mastery_at_gate=mastery_at_gate,
                    mastery_at_evaluation=current_mastery,
                    transition_count_since_gate=transitions_since,
                    days_since_gate=round(days_since, 1),
                    rationale=outcome.rationale,
                )
            )

        return outcomes

    def record_outcomes(self, outcomes: list[QualityGateOutcome]) -> None:
        """Persist evaluated outcomes as audit events."""
        for outcome in outcomes:
            self.audit_store.append(
                event_type="mastery_quality_gate.outcome",
                status=outcome.outcome,
                student_id=outcome.student_id,
                payload={
                    "outcome_id": outcome.outcome_id,
                    "gate_signal": outcome.gate_signal,
                    "outcome": outcome.outcome,
                    "mastery_at_gate": outcome.mastery_at_gate,
                    "mastery_at_evaluation": outcome.mastery_at_evaluation,
                    "transition_count_since_gate": outcome.transition_count_since_gate,
                    "days_since_gate": outcome.days_since_gate,
                    "rationale": outcome.rationale,
                },
            )

    def _evaluate(
        self,
        *,
        outcome_id: str,
        gate_signal: str,
        mastery_at_gate: float,
        current_mastery: float,
        improvement: float,
        days_since: float,
        released: bool,
    ) -> _EvalResult:
        if released:
            return _EvalResult(
                verdict="positive",
                rationale=(
                    f"Outcome {outcome_id} was held by quality gate ({gate_signal}) "
                    f"and later achieved mastery. Mastery improved from "
                    f"{mastery_at_gate:.2f} to {current_mastery:.2f}."
                ),
            )

        if improvement >= _IMPROVEMENT_THRESHOLD:
            return _EvalResult(
                verdict="positive",
                rationale=(
                    f"Outcome {outcome_id} held by quality gate ({gate_signal}) "
                    f"shows mastery improvement from {mastery_at_gate:.2f} to "
                    f"{current_mastery:.2f} (+{improvement:.2f}) — gate hold is helping."
                ),
            )

        if days_since >= _STALL_DAYS and improvement < _IMPROVEMENT_THRESHOLD:
            return _EvalResult(
                verdict="negative",
                rationale=(
                    f"Outcome {outcome_id} held by quality gate ({gate_signal}) "
                    f"for {days_since:.0f} days with no meaningful improvement "
                    f"({mastery_at_gate:.2f} → {current_mastery:.2f}) — "
                    f"gate may be too conservative."
                ),
            )

        return _EvalResult(
            verdict="inconclusive",
            rationale=(
                f"Outcome {outcome_id} held by quality gate ({gate_signal}) "
                f"for {days_since:.0f} days, mastery at {current_mastery:.2f} "
                f"(was {mastery_at_gate:.2f}) — not enough evidence yet."
            ),
        )


@dataclass(frozen=True, slots=True)
class _EvalResult:
    verdict: str = "inconclusive"
    rationale: str = ""


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)
