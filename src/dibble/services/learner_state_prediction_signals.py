"""Aggregates state-prediction outcomes into per-classification reliability signals.

This service reads ``learner_state_prediction.outcome`` audit events and
produces a compact signal that tells downstream consumers how trustworthy
each state classification has been for a given learner.  The signal is
surfaced on the learner summary so teachers and the backend itself can
see when heuristic state inference is reliable versus noisy.

Follows the same pattern as ProgressionOutcomeSignalService and
MasteryQualityGateSignalService.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dibble.services.protocols import AuditStore
from dibble.services.recency import recency_weight


@dataclass(frozen=True, slots=True)
class ClassificationReliability:
    """Per-classification accuracy breakdown."""

    classification: str
    evaluated_count: int
    positive_count: int
    negative_count: int
    weighted_positive_rate: float
    weighted_negative_rate: float

    @property
    def accuracy_rate(self) -> float:
        total = self.positive_count + self.negative_count
        if total == 0:
            return 0.0
        return self.positive_count / total


@dataclass(frozen=True, slots=True)
class StatePredictionReliabilitySignal:
    """Aggregate reliability of state-prediction heuristics for a learner."""

    evaluated_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    overall_accuracy: float = 0.0
    weighted_accuracy: float = 0.0
    per_classification: dict[str, ClassificationReliability] = field(
        default_factory=dict
    )
    weakest_classification: str | None = None
    strongest_classification: str | None = None
    rationale: str = "Insufficient prediction outcomes to evaluate reliability."

    @property
    def has_signal(self) -> bool:
        return self.evaluated_count >= _MIN_OUTCOMES_FOR_SIGNAL


_MIN_OUTCOMES_FOR_SIGNAL = 3
_MAX_EVENTS = 600


@dataclass(slots=True)
class LearnerStatePredictionSignalService:
    """Aggregates state-prediction outcomes into reliability signals."""

    audit_store: AuditStore

    def signal_for_student(
        self, *, student_id: str
    ) -> StatePredictionReliabilitySignal:
        events = [
            e
            for e in self.audit_store.list(limit=_MAX_EVENTS)
            if e.student_id is not None
            and str(e.student_id) == str(student_id)
            and e.event_type == "learner_state_prediction.outcome"
            and e.status in ("positive", "negative")
        ]

        if len(events) < _MIN_OUTCOMES_FOR_SIGNAL:
            return StatePredictionReliabilitySignal(
                evaluated_count=len(events),
                positive_count=sum(1 for e in events if e.status == "positive"),
                negative_count=sum(1 for e in events if e.status == "negative"),
            )

        # Per-classification tracking
        class_stats: dict[str, _ClassAccumulator] = {}
        total_weighted_positive = 0.0
        total_weighted_negative = 0.0
        total_weight = 0.0

        reference_time = events[0].created_at if events else None

        for event in events:
            classification = str(event.payload.get("predicted_signal", "unknown"))
            is_positive = event.status == "positive"
            weight = (
                recency_weight(event.created_at, reference_time)
                if reference_time
                else 1.0
            )

            if classification not in class_stats:
                class_stats[classification] = _ClassAccumulator()
            acc = class_stats[classification]
            if is_positive:
                acc.positive_count += 1
                acc.weighted_positive += weight
            else:
                acc.negative_count += 1
                acc.weighted_negative += weight
            acc.total_weight += weight
            total_weight += weight

            if is_positive:
                total_weighted_positive += weight
            else:
                total_weighted_negative += weight

        positive_count = sum(1 for e in events if e.status == "positive")
        negative_count = len(events) - positive_count
        overall_accuracy = positive_count / max(1, len(events))
        weighted_accuracy = (
            total_weighted_positive / max(0.001, total_weight)
            if total_weight > 0
            else 0.0
        )

        per_classification: dict[str, ClassificationReliability] = {}
        for cls_name, acc in class_stats.items():
            w_total = acc.weighted_positive + acc.weighted_negative
            per_classification[cls_name] = ClassificationReliability(
                classification=cls_name,
                evaluated_count=acc.positive_count + acc.negative_count,
                positive_count=acc.positive_count,
                negative_count=acc.negative_count,
                weighted_positive_rate=(
                    acc.weighted_positive / w_total if w_total > 0 else 0.0
                ),
                weighted_negative_rate=(
                    acc.weighted_negative / w_total if w_total > 0 else 0.0
                ),
            )

        # Identify weakest and strongest classification
        evaluable = {
            k: v for k, v in per_classification.items() if v.evaluated_count >= 2
        }
        weakest = (
            min(evaluable.values(), key=lambda v: v.accuracy_rate).classification
            if evaluable
            else None
        )
        strongest = (
            max(evaluable.values(), key=lambda v: v.accuracy_rate).classification
            if evaluable
            else None
        )

        rationale = _build_rationale(
            overall_accuracy=overall_accuracy,
            weighted_accuracy=weighted_accuracy,
            per_classification=per_classification,
            weakest=weakest,
            strongest=strongest,
            total_count=len(events),
        )

        return StatePredictionReliabilitySignal(
            evaluated_count=len(events),
            positive_count=positive_count,
            negative_count=negative_count,
            overall_accuracy=round(overall_accuracy, 3),
            weighted_accuracy=round(weighted_accuracy, 3),
            per_classification=per_classification,
            weakest_classification=weakest,
            strongest_classification=strongest,
            rationale=rationale,
        )


@dataclass
class _ClassAccumulator:
    positive_count: int = 0
    negative_count: int = 0
    weighted_positive: float = 0.0
    weighted_negative: float = 0.0
    total_weight: float = 0.0


def _build_rationale(
    *,
    overall_accuracy: float,
    weighted_accuracy: float,
    per_classification: dict[str, ClassificationReliability],
    weakest: str | None,
    strongest: str | None,
    total_count: int,
) -> str:
    if total_count < _MIN_OUTCOMES_FOR_SIGNAL:
        return "Insufficient prediction outcomes to evaluate reliability."

    parts = [
        f"State prediction accuracy: {overall_accuracy:.0%} overall "
        f"({weighted_accuracy:.0%} recency-weighted) across {total_count} evaluated predictions."
    ]

    if strongest and weakest and strongest != weakest:
        s = per_classification[strongest]
        w = per_classification[weakest]
        parts.append(
            f"Strongest: {strongest} ({s.accuracy_rate:.0%} accuracy, "
            f"{s.evaluated_count} evaluated). "
            f"Weakest: {weakest} ({w.accuracy_rate:.0%} accuracy, "
            f"{w.evaluated_count} evaluated)."
        )

    weak_classifications = [
        v
        for v in per_classification.values()
        if v.evaluated_count >= 2 and v.accuracy_rate < 0.5
    ]
    if weak_classifications:
        names = ", ".join(v.classification for v in weak_classifications)
        parts.append(
            f"Low-reliability classifications ({names}) may need "
            f"a different approach or more evidence."
        )

    return " ".join(parts)
