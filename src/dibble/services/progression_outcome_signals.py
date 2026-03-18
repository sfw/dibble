"""Reads progression outcome verdicts and produces reliability signals.

The :class:`ProgressionOutcomeSignalService` closes the feedback loop that
was missing from the original :class:`ProgressionOutcomeTracker`.  Instead of
recording verdicts into the audit trail and never reading them again, this
service aggregates recent positive/negative/inconclusive outcomes per action
family and exposes a :class:`ProgressionOutcomeSignal` that downstream
consumers (primarily :class:`ProgressionOwnershipService`) can use to adjust
hold and transfer thresholds.

Design principles:
- Only non-inconclusive verdicts influence the signal.
- A minimum evaluated count is required before any adjustment is applied, so
  sparse data does not distort thresholds.
- Adjustments are bounded to avoid runaway drift from a few noisy outcomes.
- Recent outcomes carry more weight than older ones via ``recency_weight``.
- Hold subtypes (hold_target, hold_repair_target, hold_bridge_target) are
  tracked separately so repair and bridge hold reliability can diverge from
  target hold reliability.
- Prerequisite rebuild outcomes now produce their own threshold adjustment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from dibble.services.protocols import AuditStore
from dibble.services.recency import recency_weight


@dataclass(frozen=True, slots=True)
class HoldSubtypeBreakdown:
    """Per-subtype hold outcome breakdown."""

    action: str = ""
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
class ProgressionOutcomeSignal:
    """Aggregated reliability signal from recent progression outcomes."""

    # Hold decisions (aggregate across all subtypes)
    hold_evaluated_count: int = 0
    hold_positive_count: int = 0
    hold_negative_count: int = 0
    hold_positive_rate: float = 0.0
    hold_negative_rate: float = 0.0

    # Hold subtype breakdowns
    hold_subtype_breakdowns: tuple[HoldSubtypeBreakdown, ...] = ()

    # Recency-weighted hold rates (recent outcomes count more)
    hold_weighted_positive_rate: float = 0.0
    hold_weighted_negative_rate: float = 0.0

    # Transfer decisions
    transfer_evaluated_count: int = 0
    transfer_positive_count: int = 0
    transfer_negative_count: int = 0
    transfer_positive_rate: float = 0.0
    transfer_negative_rate: float = 0.0

    # Recency-weighted transfer rates
    transfer_weighted_positive_rate: float = 0.0
    transfer_weighted_negative_rate: float = 0.0

    # Prerequisite rebuild decisions
    prerequisite_evaluated_count: int = 0
    prerequisite_positive_count: int = 0
    prerequisite_negative_count: int = 0
    prerequisite_positive_rate: float = 0.0
    prerequisite_negative_rate: float = 0.0

    # Threshold adjustments derived from outcome rates.
    hold_threshold_adjustment: float = 0.0
    transfer_confidence_adjustment: float = 0.0
    prerequisite_threshold_adjustment: float = 0.0

    rationale: str | None = None


_HOLD_ACTIONS = frozenset({"hold_target", "hold_repair_target", "hold_bridge_target"})

# Minimum non-inconclusive outcomes needed before an adjustment is applied.
_MIN_HOLD_OUTCOMES = 3
_MIN_TRANSFER_OUTCOMES = 2
_MIN_PREREQUISITE_OUTCOMES = 3

# Maximum threshold adjustments (bounded to prevent runaway drift).
_MAX_HOLD_ADJUSTMENT = 0.06
_MAX_TRANSFER_ADJUSTMENT = 0.05
_MAX_PREREQUISITE_ADJUSTMENT = 0.04


@dataclass(slots=True)
class _WeightedAccumulator:
    """Accumulates recency-weighted positive/negative counts."""

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

    def raw_positive_rate(self) -> float:
        return self.raw_positive / self.raw_total if self.raw_total else 0.0

    def raw_negative_rate(self) -> float:
        return self.raw_negative / self.raw_total if self.raw_total else 0.0

    def weighted_positive_rate(self) -> float:
        total = self.weighted_total
        return self.weighted_positive / total if total > 0 else 0.0

    def weighted_negative_rate(self) -> float:
        total = self.weighted_total
        return self.weighted_negative / total if total > 0 else 0.0


@dataclass(slots=True)
class ProgressionOutcomeSignalService:
    """Aggregates recent progression outcome verdicts into a reliability signal."""

    audit_store: AuditStore
    max_events: int = 600

    def signal_for_student(
        self,
        *,
        student_id: UUID,
        target_kc_ids: list[str] | None = None,
    ) -> ProgressionOutcomeSignal:
        """Build a signal from recent progression.outcome events.

        When *target_kc_ids* is provided, only outcomes whose decision
        targeted overlapping KCs are included.  Otherwise all outcomes for
        the student are aggregated.
        """
        events = self.audit_store.list(limit=self.max_events)
        target_set = set(target_kc_ids) if target_kc_ids else None
        now = datetime.now(timezone.utc)

        hold_acc = _WeightedAccumulator()
        transfer_acc = _WeightedAccumulator()
        prereq_acc = _WeightedAccumulator()

        # Per-subtype accumulators for hold actions.
        hold_subtype_accs: dict[str, _WeightedAccumulator] = {}

        for event in events:
            if event.event_type != "progression.outcome":
                continue
            if event.student_id is None or str(event.student_id) != str(student_id):
                continue

            verdict = event.payload.get("outcome", "inconclusive")
            if verdict == "inconclusive":
                continue

            if target_set is not None:
                decision_kcs = event.payload.get("decision_target_kc_ids", [])
                if isinstance(decision_kcs, list) and not target_set.intersection(
                    str(kc) for kc in decision_kcs
                ):
                    continue

            action = str(event.payload.get("decision_action", ""))
            is_positive = verdict == "positive"
            weight = _event_recency_weight(event.created_at, now)

            if action in _HOLD_ACTIONS:
                hold_acc.add(is_positive=is_positive, weight=weight)
                if action not in hold_subtype_accs:
                    hold_subtype_accs[action] = _WeightedAccumulator()
                hold_subtype_accs[action].add(is_positive=is_positive, weight=weight)
            elif action == "attempt_transfer":
                transfer_acc.add(is_positive=is_positive, weight=weight)
            elif action == "rebuild_prerequisite_first":
                prereq_acc.add(is_positive=is_positive, weight=weight)

        hold_adjustment = self._hold_threshold_adjustment(hold_acc)
        transfer_adjustment = self._transfer_confidence_adjustment(transfer_acc)
        prereq_adjustment = self._prerequisite_threshold_adjustment(prereq_acc)

        subtype_breakdowns = tuple(
            HoldSubtypeBreakdown(
                action=action,
                weighted_positive=acc.weighted_positive,
                weighted_negative=acc.weighted_negative,
                raw_count=acc.raw_total,
            )
            for action, acc in sorted(hold_subtype_accs.items())
        )

        rationale = self._build_rationale(
            hold_acc=hold_acc,
            hold_adjustment=hold_adjustment,
            transfer_acc=transfer_acc,
            transfer_adjustment=transfer_adjustment,
            prereq_acc=prereq_acc,
            prereq_adjustment=prereq_adjustment,
            hold_subtype_accs=hold_subtype_accs,
        )

        return ProgressionOutcomeSignal(
            hold_evaluated_count=hold_acc.raw_total,
            hold_positive_count=hold_acc.raw_positive,
            hold_negative_count=hold_acc.raw_negative,
            hold_positive_rate=round(hold_acc.raw_positive_rate(), 2),
            hold_negative_rate=round(hold_acc.raw_negative_rate(), 2),
            hold_subtype_breakdowns=subtype_breakdowns,
            hold_weighted_positive_rate=round(hold_acc.weighted_positive_rate(), 2),
            hold_weighted_negative_rate=round(hold_acc.weighted_negative_rate(), 2),
            transfer_evaluated_count=transfer_acc.raw_total,
            transfer_positive_count=transfer_acc.raw_positive,
            transfer_negative_count=transfer_acc.raw_negative,
            transfer_positive_rate=round(transfer_acc.raw_positive_rate(), 2),
            transfer_negative_rate=round(transfer_acc.raw_negative_rate(), 2),
            transfer_weighted_positive_rate=round(
                transfer_acc.weighted_positive_rate(), 2
            ),
            transfer_weighted_negative_rate=round(
                transfer_acc.weighted_negative_rate(), 2
            ),
            prerequisite_evaluated_count=prereq_acc.raw_total,
            prerequisite_positive_count=prereq_acc.raw_positive,
            prerequisite_negative_count=prereq_acc.raw_negative,
            prerequisite_positive_rate=round(prereq_acc.raw_positive_rate(), 2),
            prerequisite_negative_rate=round(prereq_acc.raw_negative_rate(), 2),
            hold_threshold_adjustment=round(hold_adjustment, 3),
            transfer_confidence_adjustment=round(transfer_adjustment, 3),
            prerequisite_threshold_adjustment=round(prereq_adjustment, 3),
            rationale=rationale,
        )

    def _hold_threshold_adjustment(self, acc: _WeightedAccumulator) -> float:
        """Compute how much to adjust hold confidence thresholds.

        Uses recency-weighted rates so recent failures weigh more heavily
        than older ones.  Returns a positive value to *raise* the threshold
        (making holds harder to trigger) when holds have mostly negative
        outcomes, a negative value to *lower* it when holds are reliably
        positive, and 0.0 when evidence is insufficient.
        """
        if acc.raw_total < _MIN_HOLD_OUTCOMES:
            return 0.0

        neg_rate = acc.weighted_negative_rate()
        pos_rate = acc.weighted_positive_rate()

        if neg_rate >= 0.6:
            return min(
                _MAX_HOLD_ADJUSTMENT,
                (neg_rate - 0.4) * 0.15,
            )
        if pos_rate >= 0.75:
            return max(
                -_MAX_HOLD_ADJUSTMENT,
                -(pos_rate - 0.6) * 0.12,
            )
        return 0.0

    def _transfer_confidence_adjustment(self, acc: _WeightedAccumulator) -> float:
        """Compute how much to adjust the transfer confidence threshold.

        Uses recency-weighted rates.  Returns a positive value to *raise*
        the confidence required for transfer when transfers have mostly
        negative outcomes, negative to lower it when succeeding.
        """
        if acc.raw_total < _MIN_TRANSFER_OUTCOMES:
            return 0.0

        neg_rate = acc.weighted_negative_rate()
        pos_rate = acc.weighted_positive_rate()

        if neg_rate >= 0.5:
            return min(
                _MAX_TRANSFER_ADJUSTMENT,
                (neg_rate - 0.3) * 0.12,
            )
        if pos_rate >= 0.8:
            return max(
                -_MAX_TRANSFER_ADJUSTMENT,
                -(pos_rate - 0.6) * 0.1,
            )
        return 0.0

    def _prerequisite_threshold_adjustment(self, acc: _WeightedAccumulator) -> float:
        """Compute how much to adjust prerequisite rebuild thresholds.

        When prerequisite rebuilds mostly fail (mastery does not improve),
        raise the threshold so we are more selective about when to redirect
        into prerequisite work.  When rebuilds reliably help, lower it so
        we rebuild more proactively.
        """
        if acc.raw_total < _MIN_PREREQUISITE_OUTCOMES:
            return 0.0

        neg_rate = acc.weighted_negative_rate()
        pos_rate = acc.weighted_positive_rate()

        if neg_rate >= 0.6:
            return min(
                _MAX_PREREQUISITE_ADJUSTMENT,
                (neg_rate - 0.4) * 0.10,
            )
        if pos_rate >= 0.75:
            return max(
                -_MAX_PREREQUISITE_ADJUSTMENT,
                -(pos_rate - 0.6) * 0.08,
            )
        return 0.0

    def _build_rationale(
        self,
        *,
        hold_acc: _WeightedAccumulator,
        hold_adjustment: float,
        transfer_acc: _WeightedAccumulator,
        transfer_adjustment: float,
        prereq_acc: _WeightedAccumulator,
        prereq_adjustment: float,
        hold_subtype_accs: dict[str, _WeightedAccumulator],
    ) -> str | None:
        fragments: list[str] = []

        if hold_acc.raw_total >= _MIN_HOLD_OUTCOMES:
            fragments.append(
                f"Hold outcomes: {hold_acc.raw_total} evaluated, "
                f"{hold_acc.raw_positive_rate():.0%} positive, "
                f"{hold_acc.raw_negative_rate():.0%} negative "
                f"(recency-weighted: {hold_acc.weighted_positive_rate():.0%}/{hold_acc.weighted_negative_rate():.0%})"
            )
            # Add subtype detail when more than one subtype is present.
            if len(hold_subtype_accs) > 1:
                subtype_parts = []
                for action in sorted(hold_subtype_accs):
                    sub = hold_subtype_accs[action]
                    label = action.replace("hold_", "")
                    subtype_parts.append(
                        f"{label}: {sub.raw_total} ({sub.weighted_positive_rate():.0%} positive)"
                    )
                fragments.append(f"Hold subtypes: {', '.join(subtype_parts)}")
            if hold_adjustment != 0.0:
                direction = "raising" if hold_adjustment > 0 else "lowering"
                fragments.append(
                    f"{direction} hold threshold by {abs(hold_adjustment):.3f}"
                )

        if transfer_acc.raw_total >= _MIN_TRANSFER_OUTCOMES:
            fragments.append(
                f"Transfer outcomes: {transfer_acc.raw_total} evaluated, "
                f"{transfer_acc.raw_positive_rate():.0%} positive, "
                f"{transfer_acc.raw_negative_rate():.0%} negative "
                f"(recency-weighted: {transfer_acc.weighted_positive_rate():.0%}/{transfer_acc.weighted_negative_rate():.0%})"
            )
            if transfer_adjustment != 0.0:
                direction = "raising" if transfer_adjustment > 0 else "lowering"
                fragments.append(
                    f"{direction} transfer confidence by {abs(transfer_adjustment):.3f}"
                )

        if prereq_acc.raw_total >= _MIN_PREREQUISITE_OUTCOMES:
            fragments.append(
                f"Prerequisite outcomes: {prereq_acc.raw_total} evaluated, "
                f"{prereq_acc.raw_positive_rate():.0%} positive, "
                f"{prereq_acc.raw_negative_rate():.0%} negative"
            )
            if prereq_adjustment != 0.0:
                direction = "raising" if prereq_adjustment > 0 else "lowering"
                fragments.append(
                    f"{direction} prerequisite threshold by {abs(prereq_adjustment):.3f}"
                )

        return "; ".join(fragments) if fragments else None


def _event_recency_weight(created_at: str | datetime, now: datetime) -> float:
    """Compute recency weight for an outcome event timestamp."""
    if isinstance(created_at, str):
        try:
            event_time = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            return 0.5
    else:
        event_time = created_at
    return recency_weight(event_time, now)
