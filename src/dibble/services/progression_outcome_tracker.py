"""Tracks whether progression decisions led to improved learner outcomes.

After each observation, the tracker looks back at recent progression decisions
for the same learner and KCs, evaluates whether the outcome matches what the
decision predicted, and records the result as a ``progression.outcome`` audit
event.  This is the validation layer that tells us whether the mastery-loop
heuristics are actually helping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dibble.services.protocols import AuditStore


@dataclass(frozen=True, slots=True)
class ProgressionOutcome:
    """A single evaluated progression decision outcome."""

    decision_event_id: str
    student_id: str
    decision_action: str
    decision_target_kc_ids: list[str] = field(default_factory=list)
    decision_target_stage: str = "target"
    decision_timestamp: str = ""
    outcome: str = "inconclusive"  # positive, negative, inconclusive
    mastery_at_decision: float | None = None
    mastery_at_evaluation: float | None = None
    observation_count_since: int = 0
    rationale: str = ""


# Progression actions that represent hold decisions.
_HOLD_ACTIONS = frozenset(
    {
        "hold_target",
        "hold_repair_target",
        "hold_bridge_target",
    }
)

# Minimum observations after a decision to produce a non-inconclusive outcome.
_MIN_OBSERVATIONS_FOR_HOLD = 2
_MIN_OBSERVATIONS_FOR_TRANSFER = 1
_MIN_OBSERVATIONS_FOR_PREREQUISITE = 2

# Decision lookback window.
_LOOKBACK_DAYS = 14


@dataclass(slots=True)
class ProgressionOutcomeTracker:
    """Evaluates recent progression decisions against subsequent evidence."""

    audit_store: AuditStore

    def evaluate_recent_decisions(
        self,
        *,
        student_id: str,
        current_kc_mastery: dict[str, float],
    ) -> list[ProgressionOutcome]:
        """Look back at recent progression decisions and evaluate outcomes.

        Returns only outcomes that have not already been recorded.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=_LOOKBACK_DAYS)

        events = self.audit_store.list(limit=500)

        evaluable_actions = _HOLD_ACTIONS | {
            "attempt_transfer",
            "rebuild_prerequisite_first",
        }

        # Find content.generate events for this student that carry a
        # progression decision worth evaluating.
        decision_events = [
            event
            for event in events
            if event.event_type == "content.generate"
            and str(event.student_id) == student_id
            and event.payload.get("progression_action") in evaluable_actions
            and _parse_timestamp(event.created_at) >= cutoff
        ]

        if not decision_events:
            return []

        # Find already-evaluated decision ids so we don't re-evaluate.
        already_evaluated = {
            event.payload.get("decision_event_id")
            for event in events
            if event.event_type == "progression.outcome"
            and str(event.student_id) == student_id
        }

        # Find observation events after each decision.
        observation_events = [
            event
            for event in events
            if event.event_type == "learner.observe"
            and str(event.student_id) == student_id
        ]

        outcomes: list[ProgressionOutcome] = []
        for decision_event in decision_events:
            if decision_event.event_id in already_evaluated:
                continue

            decision_time = _parse_timestamp(decision_event.created_at)
            action = str(decision_event.payload.get("progression_action", ""))
            target_kc_ids = _str_list(
                decision_event.payload.get("applied_target_kc_ids")
            )
            stage = str(
                decision_event.payload.get("progression_target_stage", "target")
            )
            mastery_at_decision = _decision_mastery(
                decision_event.payload, target_kc_ids
            )

            # Find observations after this decision that touch the same KCs.
            subsequent = [
                obs
                for obs in observation_events
                if _parse_timestamp(obs.created_at) > decision_time
                and _has_kc_overlap(obs.payload, target_kc_ids)
            ]

            outcome = self._evaluate(
                action=action,
                stage=stage,
                target_kc_ids=target_kc_ids,
                mastery_at_decision=mastery_at_decision,
                current_kc_mastery=current_kc_mastery,
                subsequent_observations=subsequent,
            )

            outcomes.append(
                ProgressionOutcome(
                    decision_event_id=decision_event.event_id,
                    student_id=student_id,
                    decision_action=action,
                    decision_target_kc_ids=target_kc_ids,
                    decision_target_stage=stage,
                    decision_timestamp=(
                        decision_time.isoformat()
                        if isinstance(decision_time, datetime)
                        else str(decision_time)
                    ),
                    outcome=outcome.outcome,
                    mastery_at_decision=mastery_at_decision,
                    mastery_at_evaluation=outcome.mastery_at_evaluation,
                    observation_count_since=len(subsequent),
                    rationale=outcome.rationale,
                )
            )

        return outcomes

    def record_outcomes(self, outcomes: list[ProgressionOutcome]) -> None:
        """Persist evaluated outcomes as audit events."""
        for outcome in outcomes:
            self.audit_store.append(
                event_type="progression.outcome",
                status=outcome.outcome,
                student_id=outcome.student_id,
                payload={
                    "decision_event_id": outcome.decision_event_id,
                    "decision_action": outcome.decision_action,
                    "decision_target_kc_ids": outcome.decision_target_kc_ids,
                    "decision_target_stage": outcome.decision_target_stage,
                    "decision_timestamp": outcome.decision_timestamp,
                    "outcome": outcome.outcome,
                    "mastery_at_decision": outcome.mastery_at_decision,
                    "mastery_at_evaluation": outcome.mastery_at_evaluation,
                    "observation_count_since": outcome.observation_count_since,
                    "rationale": outcome.rationale,
                },
            )

    def _evaluate(
        self,
        *,
        action: str,
        stage: str,
        target_kc_ids: list[str],
        mastery_at_decision: float | None,
        current_kc_mastery: dict[str, float],
        subsequent_observations: list,
    ) -> _EvalResult:
        current_mastery = _average_mastery(target_kc_ids, current_kc_mastery)

        if action in _HOLD_ACTIONS:
            return self._evaluate_hold(
                mastery_at_decision=mastery_at_decision,
                current_mastery=current_mastery,
                observation_count=len(subsequent_observations),
            )
        if action == "attempt_transfer":
            return self._evaluate_transfer(
                current_mastery=current_mastery,
                observation_count=len(subsequent_observations),
            )
        if action == "rebuild_prerequisite_first":
            return self._evaluate_prerequisite_rebuild(
                mastery_at_decision=mastery_at_decision,
                current_mastery=current_mastery,
                observation_count=len(subsequent_observations),
            )
        return _EvalResult(
            outcome="inconclusive",
            mastery_at_evaluation=current_mastery,
            rationale="Unknown action type.",
        )

    def _evaluate_hold(
        self,
        *,
        mastery_at_decision: float | None,
        current_mastery: float | None,
        observation_count: int,
    ) -> _EvalResult:
        if observation_count < _MIN_OBSERVATIONS_FOR_HOLD:
            return _EvalResult(
                outcome="inconclusive",
                mastery_at_evaluation=current_mastery,
                rationale=f"Only {observation_count} observation(s) since hold; need at least {_MIN_OBSERVATIONS_FOR_HOLD}.",
            )
        if current_mastery is None:
            return _EvalResult(
                outcome="inconclusive",
                mastery_at_evaluation=None,
                rationale="No current mastery data for target KCs.",
            )

        baseline = mastery_at_decision if mastery_at_decision is not None else 0.0

        if current_mastery >= 0.7:
            return _EvalResult(
                outcome="positive",
                mastery_at_evaluation=current_mastery,
                rationale=f"Mastery reached {current_mastery:.2f} (above 0.70 threshold) after hold.",
            )
        if current_mastery > baseline + 0.05:
            return _EvalResult(
                outcome="positive",
                mastery_at_evaluation=current_mastery,
                rationale=f"Mastery improved from {baseline:.2f} to {current_mastery:.2f} after hold.",
            )
        if observation_count >= 4 and current_mastery <= baseline:
            return _EvalResult(
                outcome="negative",
                mastery_at_evaluation=current_mastery,
                rationale=f"Mastery stuck at {current_mastery:.2f} (was {baseline:.2f}) after {observation_count} observations.",
            )
        return _EvalResult(
            outcome="inconclusive",
            mastery_at_evaluation=current_mastery,
            rationale=f"Mastery at {current_mastery:.2f} (was {baseline:.2f}); not enough movement to judge.",
        )

    def _evaluate_transfer(
        self,
        *,
        current_mastery: float | None,
        observation_count: int,
    ) -> _EvalResult:
        if observation_count < _MIN_OBSERVATIONS_FOR_TRANSFER:
            return _EvalResult(
                outcome="inconclusive",
                mastery_at_evaluation=current_mastery,
                rationale=f"Only {observation_count} observation(s) since transfer; need at least {_MIN_OBSERVATIONS_FOR_TRANSFER}.",
            )
        if current_mastery is None:
            return _EvalResult(
                outcome="inconclusive",
                mastery_at_evaluation=None,
                rationale="No current mastery data for transfer target KCs.",
            )
        if current_mastery >= 0.7:
            return _EvalResult(
                outcome="positive",
                mastery_at_evaluation=current_mastery,
                rationale=f"Transfer target mastery at {current_mastery:.2f} (above 0.70 threshold).",
            )
        if current_mastery < 0.5:
            return _EvalResult(
                outcome="negative",
                mastery_at_evaluation=current_mastery,
                rationale=f"Transfer target mastery at {current_mastery:.2f} (below 0.50) — transfer may have been premature.",
            )
        return _EvalResult(
            outcome="inconclusive",
            mastery_at_evaluation=current_mastery,
            rationale=f"Transfer target mastery at {current_mastery:.2f}; borderline.",
        )

    def _evaluate_prerequisite_rebuild(
        self,
        *,
        mastery_at_decision: float | None,
        current_mastery: float | None,
        observation_count: int,
    ) -> _EvalResult:
        if observation_count < _MIN_OBSERVATIONS_FOR_PREREQUISITE:
            return _EvalResult(
                outcome="inconclusive",
                mastery_at_evaluation=current_mastery,
                rationale=f"Only {observation_count} observation(s) since prerequisite rebuild; need at least {_MIN_OBSERVATIONS_FOR_PREREQUISITE}.",
            )
        if current_mastery is None:
            return _EvalResult(
                outcome="inconclusive",
                mastery_at_evaluation=None,
                rationale="No current mastery data for prerequisite KCs.",
            )

        baseline = mastery_at_decision if mastery_at_decision is not None else 0.0

        if current_mastery > baseline + 0.05:
            return _EvalResult(
                outcome="positive",
                mastery_at_evaluation=current_mastery,
                rationale=f"Prerequisite mastery improved from {baseline:.2f} to {current_mastery:.2f}.",
            )
        if observation_count >= 3 and current_mastery <= baseline:
            return _EvalResult(
                outcome="negative",
                mastery_at_evaluation=current_mastery,
                rationale=f"Prerequisite mastery stuck at {current_mastery:.2f} (was {baseline:.2f}) after {observation_count} observations.",
            )
        return _EvalResult(
            outcome="inconclusive",
            mastery_at_evaluation=current_mastery,
            rationale=f"Prerequisite mastery at {current_mastery:.2f} (was {baseline:.2f}); not enough movement.",
        )


@dataclass(frozen=True, slots=True)
class _EvalResult:
    outcome: str = "inconclusive"
    mastery_at_evaluation: float | None = None
    rationale: str = ""


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _has_kc_overlap(payload: dict, target_kc_ids: list[str]) -> bool:
    obs_kc_ids = payload.get("target_kc_ids")
    if not isinstance(obs_kc_ids, list) or not target_kc_ids:
        return False
    target_set = set(target_kc_ids)
    return any(str(kc) in target_set for kc in obs_kc_ids)


def _decision_mastery(
    payload: dict, target_kc_ids: list[str]
) -> float | None:
    mastery = payload.get("progression_average_observed_mastery")
    if mastery is not None:
        try:
            return float(mastery)
        except (ValueError, TypeError):
            pass
    return None


def _average_mastery(
    kc_ids: list[str], kc_mastery: dict[str, float]
) -> float | None:
    values = [kc_mastery[kc] for kc in kc_ids if kc in kc_mastery]
    if not values:
        return None
    return sum(values) / len(values)
