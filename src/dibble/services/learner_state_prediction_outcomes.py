"""Evaluates whether learner-state predictions correlated with subsequent outcomes.

When the observation pipeline infers a current-evidence classification
(productive_struggle, overload, disengagement, support_dependence) and records
it in the audit trail, this service later checks whether subsequent observations
confirmed or contradicted that prediction.  The result is a per-classification
accuracy signal that tells the system (and teachers) when state inference is
trustworthy versus noisy.

Follows the same Tracker → Signal pattern as ProgressionOutcomeTracker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.services.protocols import AuditStore


@dataclass(frozen=True, slots=True)
class StatePredictionOutcome:
    """One evaluated state prediction."""

    event_id: str
    student_id: str
    predicted_signal: str  # productive_struggle | overload | disengagement | support_dependence
    predicted_confidence: float
    outcome: str  # positive | negative | inconclusive
    subsequent_observation_count: int
    subsequent_completion_rate: float
    subsequent_mastery_delta: float | None
    rationale: str
    predicted_at: datetime
    evaluated_at: datetime


# ---------------------------------------------------------------------------
# Outcome evaluation thresholds
# ---------------------------------------------------------------------------

_MIN_SUBSEQUENT_OBSERVATIONS = 2
_MAX_LOOKBACK_EVENTS = 600
_ALREADY_EVALUATED_EVENT = "learner_state_prediction.outcome"


@dataclass(slots=True)
class LearnerStatePredictionOutcomeTracker:
    """Looks back at state-prediction audit events and evaluates them
    against subsequent learner observations."""

    audit_store: AuditStore

    def evaluate_recent_predictions(
        self,
        *,
        student_id: str,
        current_kc_mastery: dict[str, float] | None = None,
    ) -> list[StatePredictionOutcome]:
        # Audit store returns newest-first; reverse to get chronological order
        events = list(
            reversed(
                [
                    e
                    for e in self.audit_store.list(limit=_MAX_LOOKBACK_EVENTS)
                    if e.student_id is not None
                    and str(e.student_id) == str(student_id)
                ]
            )
        )

        # Gather prediction events not yet evaluated
        already_evaluated: set[str] = set()
        # Map event_id → chronological index for ordering
        event_index: dict[str, int] = {}
        prediction_indices: list[int] = []
        observation_indices: list[int] = []

        for idx, event in enumerate(events):
            event_index[event.event_id] = idx
            if event.event_type == _ALREADY_EVALUATED_EVENT:
                source_id = event.payload.get("source_event_id")
                if source_id:
                    already_evaluated.add(str(source_id))
            elif event.event_type == "learner.observe":
                if event.payload.get("current_evidence_signal"):
                    prediction_indices.append(idx)
                observation_indices.append(idx)

        outcomes: list[StatePredictionOutcome] = []
        for pred_idx in prediction_indices:
            pred_event = events[pred_idx]
            if pred_event.event_id in already_evaluated:
                continue
            predicted_signal = str(pred_event.payload.get("current_evidence_signal", ""))
            if predicted_signal not in {
                "productive_struggle",
                "overload",
                "disengagement",
                "support_dependence",
            }:
                continue

            predicted_confidence = float(
                pred_event.payload.get("current_evidence_confidence", 0.0)
            )

            # Find subsequent observations (later in chronological order)
            subsequent = [
                events[obs_idx]
                for obs_idx in observation_indices
                if obs_idx > pred_idx
            ]
            if len(subsequent) < _MIN_SUBSEQUENT_OBSERVATIONS:
                continue

            pred_baseline_mastery = float(
                pred_event.payload.get(
                    "observation_average_recent_mastery", 0.0
                )
                or 0.0
            )
            outcome = self._evaluate_prediction(
                predicted_signal=predicted_signal,
                predicted_confidence=predicted_confidence,
                pred_event_id=pred_event.event_id,
                student_id=student_id,
                subsequent=subsequent,
                predicted_at=pred_event.created_at,
                current_kc_mastery=current_kc_mastery,
                pred_target_kc_ids=_string_list(
                    pred_event.payload.get("target_kc_ids")
                ),
                pred_baseline_mastery=pred_baseline_mastery,
            )
            if outcome is not None:
                outcomes.append(outcome)

        return outcomes

    def record_outcomes(self, outcomes: list[StatePredictionOutcome]) -> None:
        for outcome in outcomes:
            self.audit_store.append(
                event_type=_ALREADY_EVALUATED_EVENT,
                status=outcome.outcome,
                student_id=outcome.student_id,
                payload={
                    "source_event_id": outcome.event_id,
                    "predicted_signal": outcome.predicted_signal,
                    "predicted_confidence": outcome.predicted_confidence,
                    "outcome": outcome.outcome,
                    "subsequent_observation_count": outcome.subsequent_observation_count,
                    "subsequent_completion_rate": round(
                        outcome.subsequent_completion_rate, 3
                    ),
                    "subsequent_mastery_delta": (
                        round(outcome.subsequent_mastery_delta, 4)
                        if outcome.subsequent_mastery_delta is not None
                        else None
                    ),
                    "rationale": outcome.rationale,
                },
            )

    # ------------------------------------------------------------------
    # Internal evaluation
    # ------------------------------------------------------------------

    def _evaluate_prediction(
        self,
        *,
        predicted_signal: str,
        predicted_confidence: float,
        pred_event_id: str,
        student_id: str,
        subsequent: list,
        predicted_at: datetime,
        current_kc_mastery: dict[str, float] | None,
        pred_target_kc_ids: list[str],
        pred_baseline_mastery: float,
    ) -> StatePredictionOutcome | None:
        completed_count = sum(
            1
            for obs in subsequent
            if obs.payload.get("completed") is True
            or obs.payload.get("observation_mastery_applied") is True
        )
        completion_rate = completed_count / max(1, len(subsequent))

        # Mastery delta for target KCs if available
        mastery_delta: float | None = None
        if current_kc_mastery and pred_target_kc_ids:
            current_avg = sum(
                current_kc_mastery.get(kc, 0.0) for kc in pred_target_kc_ids
            ) / max(1, len(pred_target_kc_ids))
            mastery_delta = current_avg - pred_baseline_mastery

        now = datetime.now(timezone.utc)
        outcome, rationale = self._classify_outcome(
            predicted_signal=predicted_signal,
            completion_rate=completion_rate,
            mastery_delta=mastery_delta,
            observation_count=len(subsequent),
        )

        return StatePredictionOutcome(
            event_id=pred_event_id,
            student_id=student_id,
            predicted_signal=predicted_signal,
            predicted_confidence=predicted_confidence,
            outcome=outcome,
            subsequent_observation_count=len(subsequent),
            subsequent_completion_rate=completion_rate,
            subsequent_mastery_delta=mastery_delta,
            rationale=rationale,
            predicted_at=predicted_at,
            evaluated_at=now,
        )

    def _classify_outcome(
        self,
        *,
        predicted_signal: str,
        completion_rate: float,
        mastery_delta: float | None,
        observation_count: int,
    ) -> tuple[str, str]:
        """Classify whether the prediction was confirmed by subsequent behavior.

        Each signal has different expected subsequent behavior:
        - productive_struggle → improvement with reasonable completion
        - overload → continued low completion or mastery decline
        - disengagement → continued low completion
        - support_dependence → continued high-support dependency
        """
        if observation_count < _MIN_SUBSEQUENT_OBSERVATIONS:
            return "inconclusive", "Too few subsequent observations to evaluate."

        if predicted_signal == "productive_struggle":
            # Positive: learner improved or maintained good completion
            if completion_rate >= 0.55:
                if mastery_delta is not None and mastery_delta >= 0.02:
                    return "positive", (
                        f"Productive struggle prediction confirmed: "
                        f"completion rate {completion_rate:.0%} with "
                        f"mastery improvement of {mastery_delta:+.2f}."
                    )
                return "positive", (
                    f"Productive struggle prediction confirmed: "
                    f"completion rate {completion_rate:.0%} suggests "
                    f"sustained engagement after challenge."
                )
            if mastery_delta is not None and mastery_delta < -0.05:
                return "negative", (
                    f"Productive struggle prediction contradicted: "
                    f"mastery declined by {mastery_delta:+.2f} with "
                    f"completion rate {completion_rate:.0%}, suggesting "
                    f"actual overload rather than productive struggle."
                )
            return "inconclusive", (
                f"Productive struggle prediction ambiguous: completion "
                f"rate {completion_rate:.0%} is borderline."
            )

        if predicted_signal == "overload":
            # Positive (prediction confirmed): learner continued to struggle
            if completion_rate < 0.5:
                return "positive", (
                    f"Overload prediction confirmed: completion rate "
                    f"stayed at {completion_rate:.0%}."
                )
            if mastery_delta is not None and mastery_delta < -0.03:
                return "positive", (
                    f"Overload prediction confirmed: mastery declined "
                    f"by {mastery_delta:+.2f}."
                )
            if completion_rate >= 0.65:
                return "negative", (
                    f"Overload prediction contradicted: learner recovered "
                    f"to {completion_rate:.0%} completion, suggesting the "
                    f"difficulty was temporary."
                )
            return "inconclusive", (
                f"Overload prediction ambiguous: completion rate "
                f"{completion_rate:.0%} is mixed."
            )

        if predicted_signal == "disengagement":
            if completion_rate < 0.45:
                return "positive", (
                    f"Disengagement prediction confirmed: completion "
                    f"rate {completion_rate:.0%} shows continued low engagement."
                )
            if completion_rate >= 0.6:
                return "negative", (
                    f"Disengagement prediction contradicted: learner "
                    f"re-engaged to {completion_rate:.0%} completion."
                )
            return "inconclusive", (
                f"Disengagement prediction ambiguous: completion rate "
                f"{completion_rate:.0%} is borderline."
            )

        if predicted_signal == "support_dependence":
            # Check if subsequent observations still show high support
            # (We approximate via completion rate + mastery delta)
            if completion_rate >= 0.7 and (
                mastery_delta is None or mastery_delta < 0.05
            ):
                return "positive", (
                    f"Support dependence prediction confirmed: high "
                    f"completion ({completion_rate:.0%}) without "
                    f"corresponding mastery growth suggests continued "
                    f"scaffold reliance."
                )
            if mastery_delta is not None and mastery_delta >= 0.08:
                return "negative", (
                    f"Support dependence prediction contradicted: "
                    f"mastery improved by {mastery_delta:+.2f}, "
                    f"suggesting the learner gained genuine independence."
                )
            return "inconclusive", (
                f"Support dependence prediction ambiguous: completion "
                f"rate {completion_rate:.0%} with "
                f"{'mastery delta ' + f'{mastery_delta:+.2f}' if mastery_delta is not None else 'unknown mastery change'}."
            )

        return "inconclusive", f"Unknown signal: {predicted_signal}."


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []
