"""Aggregates mastery quality gate outcomes into confidence adjustment signals.

The :class:`MasteryQualityGateSignalService` closes the feedback loop between
quality gate decisions and future gate behavior.  It reads recent
``mastery_quality_gate.outcome`` events and produces a
:class:`MasteryQualityGateSignal` that tells
:class:`LearnerProgressionService` how to adjust the gate confidence threshold.

When gate holds are mostly positive (learners improve after being held),
the signal lowers the confidence floor so the gate activates more readily.
When gate holds are mostly negative (learners stall without improvement),
the signal raises the confidence floor so the gate is more conservative
about blocking resources.

Design principles:
- Only non-inconclusive verdicts influence the signal.
- Minimum outcome count required before any adjustment.
- Adjustments are bounded to prevent runaway drift.
- Recent outcomes carry more weight than older ones via ``recency_weight``.
- Per-signal breakdowns (support_dependent vs fragile) are tracked separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from dibble.services.protocols import AuditStore
from dibble.services.recency import recency_weight


@dataclass(frozen=True, slots=True)
class GateSignalBreakdown:
    """Per-gate-signal (support_dependent / fragile) outcome breakdown."""

    signal: str = ""
    weighted_positive: float = 0.0
    weighted_negative: float = 0.0
    raw_count: int = 0

    @property
    def weighted_total(self) -> float:
        return self.weighted_positive + self.weighted_negative

    @property
    def positive_rate(self) -> float:
        total = self.weighted_total
        return self.weighted_positive / total if total > 0 else 0.0

    @property
    def negative_rate(self) -> float:
        total = self.weighted_total
        return self.weighted_negative / total if total > 0 else 0.0


@dataclass(frozen=True, slots=True)
class MasteryQualityGateSignal:
    """Aggregated reliability signal from quality gate outcomes."""

    evaluated_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    positive_rate: float = 0.0
    negative_rate: float = 0.0

    # Recency-weighted rates.
    weighted_positive_rate: float = 0.0
    weighted_negative_rate: float = 0.0

    # Per-signal breakdowns.
    signal_breakdowns: tuple[GateSignalBreakdown, ...] = ()

    # Confidence threshold adjustment: positive means raise threshold
    # (gate less aggressively), negative means lower (gate more aggressively).
    confidence_threshold_adjustment: float = 0.0

    rationale: str | None = None


# Minimum non-inconclusive outcomes needed before any adjustment.
_MIN_OUTCOMES = 3

# Maximum confidence threshold adjustment (bounded).
_MAX_ADJUSTMENT = 0.08


@dataclass(slots=True)
class _WeightedAccumulator:
    raw_positive: int = 0
    raw_negative: int = 0
    weighted_positive: float = 0.0
    weighted_negative: float = 0.0

    @property
    def raw_total(self) -> int:
        return self.raw_positive + self.raw_negative

    @property
    def weighted_total(self) -> float:
        return self.weighted_positive + self.weighted_negative

    def add(self, *, is_positive: bool, weight: float) -> None:
        if is_positive:
            self.raw_positive += 1
            self.weighted_positive += weight
        else:
            self.raw_negative += 1
            self.weighted_negative += weight

    def weighted_positive_rate(self) -> float:
        total = self.weighted_total
        return self.weighted_positive / total if total > 0 else 0.0

    def weighted_negative_rate(self) -> float:
        total = self.weighted_total
        return self.weighted_negative / total if total > 0 else 0.0


@dataclass(slots=True)
class MasteryQualityGateSignalService:
    """Aggregates quality gate outcomes into a confidence adjustment signal."""

    audit_store: AuditStore
    max_events: int = 600

    def signal_for_student(
        self,
        *,
        student_id: UUID,
    ) -> MasteryQualityGateSignal:
        """Build a signal from recent mastery_quality_gate.outcome events."""
        events = self.audit_store.list(limit=self.max_events)
        now = datetime.now(timezone.utc)

        total_acc = _WeightedAccumulator()
        signal_accs: dict[str, _WeightedAccumulator] = {}

        for event in events:
            if event.event_type != "mastery_quality_gate.outcome":
                continue
            if event.student_id is None or str(event.student_id) != str(student_id):
                continue

            verdict = event.payload.get("outcome", "inconclusive")
            if verdict == "inconclusive":
                continue

            is_positive = verdict == "positive"
            weight = _event_recency_weight(event.created_at, now)

            total_acc.add(is_positive=is_positive, weight=weight)

            gate_signal = str(event.payload.get("gate_signal", "unknown"))
            if gate_signal not in signal_accs:
                signal_accs[gate_signal] = _WeightedAccumulator()
            signal_accs[gate_signal].add(is_positive=is_positive, weight=weight)

        adjustment = self._confidence_adjustment(total_acc)

        breakdowns = tuple(
            GateSignalBreakdown(
                signal=signal,
                weighted_positive=acc.weighted_positive,
                weighted_negative=acc.weighted_negative,
                raw_count=acc.raw_total,
            )
            for signal, acc in sorted(signal_accs.items())
        )

        rationale = self._build_rationale(
            total_acc=total_acc,
            adjustment=adjustment,
            signal_accs=signal_accs,
        )

        return MasteryQualityGateSignal(
            evaluated_count=total_acc.raw_total,
            positive_count=total_acc.raw_positive,
            negative_count=total_acc.raw_negative,
            positive_rate=round(
                total_acc.raw_positive / total_acc.raw_total
                if total_acc.raw_total
                else 0.0,
                2,
            ),
            negative_rate=round(
                total_acc.raw_negative / total_acc.raw_total
                if total_acc.raw_total
                else 0.0,
                2,
            ),
            weighted_positive_rate=round(total_acc.weighted_positive_rate(), 2),
            weighted_negative_rate=round(total_acc.weighted_negative_rate(), 2),
            signal_breakdowns=breakdowns,
            confidence_threshold_adjustment=round(adjustment, 3),
            rationale=rationale,
        )

    def _confidence_adjustment(self, acc: _WeightedAccumulator) -> float:
        """Compute confidence threshold adjustment from outcome rates.

        Positive outcomes (gate holds that led to improvement) mean the gate
        is working — lower the confidence threshold so it activates more.
        Negative outcomes (stalled holds) mean the gate is too aggressive —
        raise the threshold so it activates less.
        """
        if acc.raw_total < _MIN_OUTCOMES:
            return 0.0

        neg_rate = acc.weighted_negative_rate()
        pos_rate = acc.weighted_positive_rate()

        # When gate holds mostly fail, raise the confidence floor.
        if neg_rate >= 0.6:
            return min(_MAX_ADJUSTMENT, (neg_rate - 0.4) * 0.2)

        # When gate holds mostly succeed, lower the confidence floor.
        if pos_rate >= 0.75:
            return max(-_MAX_ADJUSTMENT, -(pos_rate - 0.6) * 0.15)

        return 0.0

    def _build_rationale(
        self,
        *,
        total_acc: _WeightedAccumulator,
        adjustment: float,
        signal_accs: dict[str, _WeightedAccumulator],
    ) -> str | None:
        if total_acc.raw_total < _MIN_OUTCOMES:
            return None

        parts: list[str] = []
        parts.append(
            f"Quality gate outcomes: {total_acc.raw_total} evaluated, "
            f"{total_acc.weighted_positive_rate():.0%} positive, "
            f"{total_acc.weighted_negative_rate():.0%} negative "
            f"(recency-weighted)"
        )

        if len(signal_accs) > 1:
            breakdown_parts = []
            for signal in sorted(signal_accs):
                acc = signal_accs[signal]
                breakdown_parts.append(
                    f"{signal}: {acc.raw_total} ({acc.weighted_positive_rate():.0%} positive)"
                )
            parts.append(f"Per-signal: {', '.join(breakdown_parts)}")

        if adjustment != 0.0:
            direction = "raising" if adjustment > 0 else "lowering"
            parts.append(
                f"{direction} quality gate confidence threshold by {abs(adjustment):.3f}"
            )

        return "; ".join(parts)


def _event_recency_weight(created_at: str | datetime, now: datetime) -> float:
    if isinstance(created_at, str):
        try:
            event_time = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            return 0.5
    else:
        event_time = created_at
    return recency_weight(event_time, now)
