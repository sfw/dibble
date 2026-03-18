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
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.services.protocols import AuditStore


@dataclass(frozen=True, slots=True)
class ProgressionOutcomeSignal:
    """Aggregated reliability signal from recent progression outcomes."""

    # Hold decisions
    hold_evaluated_count: int = 0
    hold_positive_count: int = 0
    hold_negative_count: int = 0
    hold_positive_rate: float = 0.0
    hold_negative_rate: float = 0.0

    # Transfer decisions
    transfer_evaluated_count: int = 0
    transfer_positive_count: int = 0
    transfer_negative_count: int = 0
    transfer_positive_rate: float = 0.0
    transfer_negative_rate: float = 0.0

    # Prerequisite rebuild decisions
    prerequisite_evaluated_count: int = 0
    prerequisite_positive_count: int = 0
    prerequisite_negative_count: int = 0
    prerequisite_positive_rate: float = 0.0
    prerequisite_negative_rate: float = 0.0

    # Threshold adjustments derived from outcome rates.
    hold_threshold_adjustment: float = 0.0
    transfer_confidence_adjustment: float = 0.0

    rationale: str | None = None


_HOLD_ACTIONS = frozenset({"hold_target", "hold_repair_target", "hold_bridge_target"})

# Minimum non-inconclusive outcomes needed before an adjustment is applied.
_MIN_HOLD_OUTCOMES = 3
_MIN_TRANSFER_OUTCOMES = 2

# Maximum threshold adjustments (bounded to prevent runaway drift).
_MAX_HOLD_ADJUSTMENT = 0.06
_MAX_TRANSFER_ADJUSTMENT = 0.05


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

        hold_pos = 0
        hold_neg = 0
        transfer_pos = 0
        transfer_neg = 0
        prereq_pos = 0
        prereq_neg = 0

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

            if action in _HOLD_ACTIONS:
                if is_positive:
                    hold_pos += 1
                else:
                    hold_neg += 1
            elif action == "attempt_transfer":
                if is_positive:
                    transfer_pos += 1
                else:
                    transfer_neg += 1
            elif action == "rebuild_prerequisite_first":
                if is_positive:
                    prereq_pos += 1
                else:
                    prereq_neg += 1

        hold_total = hold_pos + hold_neg
        transfer_total = transfer_pos + transfer_neg
        prereq_total = prereq_pos + prereq_neg

        hold_positive_rate = hold_pos / hold_total if hold_total else 0.0
        hold_negative_rate = hold_neg / hold_total if hold_total else 0.0
        transfer_positive_rate = (
            transfer_pos / transfer_total if transfer_total else 0.0
        )
        transfer_negative_rate = (
            transfer_neg / transfer_total if transfer_total else 0.0
        )
        prereq_positive_rate = prereq_pos / prereq_total if prereq_total else 0.0
        prereq_negative_rate = prereq_neg / prereq_total if prereq_total else 0.0

        hold_adjustment = self._hold_threshold_adjustment(
            hold_total=hold_total,
            hold_negative_rate=hold_negative_rate,
            hold_positive_rate=hold_positive_rate,
        )
        transfer_adjustment = self._transfer_confidence_adjustment(
            transfer_total=transfer_total,
            transfer_negative_rate=transfer_negative_rate,
            transfer_positive_rate=transfer_positive_rate,
        )

        rationale = self._build_rationale(
            hold_total=hold_total,
            hold_positive_rate=hold_positive_rate,
            hold_negative_rate=hold_negative_rate,
            hold_adjustment=hold_adjustment,
            transfer_total=transfer_total,
            transfer_positive_rate=transfer_positive_rate,
            transfer_negative_rate=transfer_negative_rate,
            transfer_adjustment=transfer_adjustment,
        )

        return ProgressionOutcomeSignal(
            hold_evaluated_count=hold_total,
            hold_positive_count=hold_pos,
            hold_negative_count=hold_neg,
            hold_positive_rate=round(hold_positive_rate, 2),
            hold_negative_rate=round(hold_negative_rate, 2),
            transfer_evaluated_count=transfer_total,
            transfer_positive_count=transfer_pos,
            transfer_negative_count=transfer_neg,
            transfer_positive_rate=round(transfer_positive_rate, 2),
            transfer_negative_rate=round(transfer_negative_rate, 2),
            prerequisite_evaluated_count=prereq_total,
            prerequisite_positive_count=prereq_pos,
            prerequisite_negative_count=prereq_neg,
            prerequisite_positive_rate=round(prereq_positive_rate, 2),
            prerequisite_negative_rate=round(prereq_negative_rate, 2),
            hold_threshold_adjustment=round(hold_adjustment, 3),
            transfer_confidence_adjustment=round(transfer_adjustment, 3),
            rationale=rationale,
        )

    def _hold_threshold_adjustment(
        self,
        *,
        hold_total: int,
        hold_negative_rate: float,
        hold_positive_rate: float,
    ) -> float:
        """Compute how much to adjust hold confidence thresholds.

        Returns a positive value to *raise* the threshold (making holds
        harder to trigger) when holds have mostly negative outcomes.
        Returns a negative value to *lower* the threshold (making holds
        easier to trigger) when holds are reliably positive.
        Returns 0.0 when there is insufficient evidence.
        """
        if hold_total < _MIN_HOLD_OUTCOMES:
            return 0.0

        if hold_negative_rate >= 0.6:
            # Holds are mostly failing — raise threshold so we hold less.
            return min(
                _MAX_HOLD_ADJUSTMENT,
                (hold_negative_rate - 0.4) * 0.15,
            )
        if hold_positive_rate >= 0.75:
            # Holds are reliably helping — lower threshold to hold more easily.
            return max(
                -_MAX_HOLD_ADJUSTMENT,
                -(hold_positive_rate - 0.6) * 0.12,
            )
        return 0.0

    def _transfer_confidence_adjustment(
        self,
        *,
        transfer_total: int,
        transfer_negative_rate: float,
        transfer_positive_rate: float,
    ) -> float:
        """Compute how much to adjust the transfer confidence threshold.

        Returns a positive value to *raise* the confidence required for
        transfer (making transfers harder) when transfers have mostly
        negative outcomes.  Returns a negative value to lower it when
        transfers are reliably succeeding.
        """
        if transfer_total < _MIN_TRANSFER_OUTCOMES:
            return 0.0

        if transfer_negative_rate >= 0.5:
            # Transfers are often premature — require more confidence.
            return min(
                _MAX_TRANSFER_ADJUSTMENT,
                (transfer_negative_rate - 0.3) * 0.12,
            )
        if transfer_positive_rate >= 0.8:
            # Transfers are reliably succeeding — relax confidence.
            return max(
                -_MAX_TRANSFER_ADJUSTMENT,
                -(transfer_positive_rate - 0.6) * 0.1,
            )
        return 0.0

    def _build_rationale(
        self,
        *,
        hold_total: int,
        hold_positive_rate: float,
        hold_negative_rate: float,
        hold_adjustment: float,
        transfer_total: int,
        transfer_positive_rate: float,
        transfer_negative_rate: float,
        transfer_adjustment: float,
    ) -> str | None:
        fragments: list[str] = []
        if hold_total >= _MIN_HOLD_OUTCOMES:
            fragments.append(
                f"Hold outcomes: {hold_total} evaluated, "
                f"{hold_positive_rate:.0%} positive, "
                f"{hold_negative_rate:.0%} negative"
            )
            if hold_adjustment != 0.0:
                direction = "raising" if hold_adjustment > 0 else "lowering"
                fragments.append(
                    f"{direction} hold threshold by {abs(hold_adjustment):.3f}"
                )
        if transfer_total >= _MIN_TRANSFER_OUTCOMES:
            fragments.append(
                f"Transfer outcomes: {transfer_total} evaluated, "
                f"{transfer_positive_rate:.0%} positive, "
                f"{transfer_negative_rate:.0%} negative"
            )
            if transfer_adjustment != 0.0:
                direction = "raising" if transfer_adjustment > 0 else "lowering"
                fragments.append(
                    f"{direction} transfer confidence by {abs(transfer_adjustment):.3f}"
                )
        return "; ".join(fragments) if fragments else None
