"""Aggregates misconception remediation outcomes into per-KC reliability signals.

The :class:`MisconceptionRemediationOutcomeSignalService` closes the feedback
loop on ADAPT-003 misconception remediation.  The
:class:`MisconceptionRemediationOutcomeTracker` records ``resolved``,
``unresolved``, and ``inconclusive`` verdicts as audit events; this service
reads those verdicts back and exposes per-KC signals that downstream consumers
(primarily :class:`MisconceptionDetector`) can use to adjust confidence:

- When a KC's misconceptions have repeatedly failed remediation (``unresolved``),
  the signal boosts detection confidence because the misconception is proving
  persistent despite remediation attempts.
- When remediations consistently resolve, the signal does not suppress detection
  but flags the misconception as tractable so remediation planning can remain
  confident in its current approach.
- A ``persistent_misconception`` flag surfaces when repeated unresolve signals
  suggest the current remediation approach is not working and may need teacher
  review or a different strategy.

Design principles:
- Only non-inconclusive verdicts influence the signal.
- A minimum evaluated count is required before adjustments apply.
- Recent outcomes carry more weight via ``recency_weight``.
- Signals are per-KC, not per-misconception-id, because a KC may have multiple
  overlapping misconception descriptions that converge on the same remediation
  target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from dibble.services.protocols import AuditStore
from dibble.services.recency import recency_weight


@dataclass(frozen=True, slots=True)
class MisconceptionRemediationSignal:
    """Per-KC signal summarizing remediation outcome history."""

    kc_id: str
    evaluated_count: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    weighted_resolved: float = 0.0
    weighted_unresolved: float = 0.0
    resolution_rate: float = 0.0
    unresolution_rate: float = 0.0

    # Confidence adjustment for misconception detection: positive means
    # the misconception is proving persistent (boost detection confidence),
    # negative means remediation is working well (slightly temper confidence).
    confidence_adjustment: float = 0.0

    # True when repeated unresolved outcomes suggest the current remediation
    # approach is not working for this KC.
    persistent_misconception: bool = False

    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class MisconceptionRemediationOutcomeSignalBundle:
    """Collection of per-KC remediation outcome signals for a learner."""

    signals_by_kc: dict[str, MisconceptionRemediationSignal]

    def signal_for_kc(self, kc_id: str) -> MisconceptionRemediationSignal | None:
        return self.signals_by_kc.get(kc_id)

    def confidence_adjustment_for_kc(self, kc_id: str) -> float:
        signal = self.signals_by_kc.get(kc_id)
        return signal.confidence_adjustment if signal is not None else 0.0

    def is_persistent_for_kc(self, kc_id: str) -> bool:
        signal = self.signals_by_kc.get(kc_id)
        return signal.persistent_misconception if signal is not None else False


# Minimum non-inconclusive outcomes before adjustments apply.
_MIN_OUTCOMES = 2

# Maximum confidence adjustment (bounded).
_MAX_CONFIDENCE_BOOST = 0.12
_MAX_CONFIDENCE_TEMPER = 0.04

# Persistent misconception threshold: if at least this many outcomes are
# unresolved AND the unresolution rate is above 0.6, flag as persistent.
_PERSISTENT_MIN_UNRESOLVED = 2
_PERSISTENT_UNRESOLUTION_RATE = 0.6


@dataclass(slots=True)
class MisconceptionRemediationOutcomeSignalService:
    """Aggregates misconception.remediation.outcome events into per-KC signals."""

    audit_store: AuditStore
    max_events: int = 600

    def signal_bundle_for_student(
        self,
        *,
        student_id: UUID,
    ) -> MisconceptionRemediationOutcomeSignalBundle:
        """Build per-KC remediation outcome signals from audit events."""
        events = self.audit_store.list(limit=self.max_events)
        now = datetime.now(timezone.utc)

        # Accumulate per-KC weighted outcome counts.
        kc_resolved: dict[str, float] = {}
        kc_unresolved: dict[str, float] = {}
        kc_raw_resolved: dict[str, int] = {}
        kc_raw_unresolved: dict[str, int] = {}

        for event in events:
            if event.event_type != "misconception.remediation.outcome":
                continue
            if event.student_id is None or str(event.student_id) != str(student_id):
                continue

            verdict = event.payload.get("outcome", "inconclusive")
            if verdict == "inconclusive":
                continue

            # Each outcome event covers a set of focus KCs.
            focus_kc_ids = event.payload.get("focus_kc_ids", [])
            target_kc_id = event.payload.get("target_kc_id")
            if isinstance(focus_kc_ids, list):
                kc_ids = list({str(kc) for kc in focus_kc_ids})
            elif target_kc_id:
                kc_ids = [str(target_kc_id)]
            else:
                continue

            weight = _event_recency_weight(event.created_at, now)

            for kc_id in kc_ids:
                if verdict == "resolved":
                    kc_resolved[kc_id] = kc_resolved.get(kc_id, 0.0) + weight
                    kc_raw_resolved[kc_id] = kc_raw_resolved.get(kc_id, 0) + 1
                else:
                    kc_unresolved[kc_id] = kc_unresolved.get(kc_id, 0.0) + weight
                    kc_raw_unresolved[kc_id] = kc_raw_unresolved.get(kc_id, 0) + 1

        all_kc_ids = set(kc_resolved) | set(kc_unresolved)
        signals: dict[str, MisconceptionRemediationSignal] = {}

        for kc_id in all_kc_ids:
            raw_resolved = kc_raw_resolved.get(kc_id, 0)
            raw_unresolved = kc_raw_unresolved.get(kc_id, 0)
            weighted_resolved = kc_resolved.get(kc_id, 0.0)
            weighted_unresolved = kc_unresolved.get(kc_id, 0.0)
            raw_total = raw_resolved + raw_unresolved
            weighted_total = weighted_resolved + weighted_unresolved

            resolution_rate = (
                weighted_resolved / weighted_total if weighted_total > 0 else 0.0
            )
            unresolution_rate = (
                weighted_unresolved / weighted_total if weighted_total > 0 else 0.0
            )

            adjustment = self._confidence_adjustment(
                raw_total=raw_total,
                unresolution_rate=unresolution_rate,
                resolution_rate=resolution_rate,
            )

            persistent = (
                raw_unresolved >= _PERSISTENT_MIN_UNRESOLVED
                and unresolution_rate >= _PERSISTENT_UNRESOLUTION_RATE
            )

            rationale = self._build_rationale(
                kc_id=kc_id,
                raw_total=raw_total,
                raw_resolved=raw_resolved,
                raw_unresolved=raw_unresolved,
                resolution_rate=resolution_rate,
                unresolution_rate=unresolution_rate,
                adjustment=adjustment,
                persistent=persistent,
            )

            signals[kc_id] = MisconceptionRemediationSignal(
                kc_id=kc_id,
                evaluated_count=raw_total,
                resolved_count=raw_resolved,
                unresolved_count=raw_unresolved,
                weighted_resolved=round(weighted_resolved, 3),
                weighted_unresolved=round(weighted_unresolved, 3),
                resolution_rate=round(resolution_rate, 2),
                unresolution_rate=round(unresolution_rate, 2),
                confidence_adjustment=round(adjustment, 3),
                persistent_misconception=persistent,
                rationale=rationale,
            )

        return MisconceptionRemediationOutcomeSignalBundle(signals_by_kc=signals)

    def _confidence_adjustment(
        self,
        *,
        raw_total: int,
        unresolution_rate: float,
        resolution_rate: float,
    ) -> float:
        """Compute confidence adjustment for misconception detection.

        Positive = misconception is proving persistent, boost detection.
        Negative = remediation is working, slightly temper detection.
        """
        if raw_total < _MIN_OUTCOMES:
            return 0.0

        if unresolution_rate >= 0.6:
            # Misconception is persistent despite remediation — boost detection.
            return min(
                _MAX_CONFIDENCE_BOOST,
                (unresolution_rate - 0.3) * 0.15,
            )
        if resolution_rate >= 0.8:
            # Remediation is reliably resolving — slightly temper.
            return max(
                -_MAX_CONFIDENCE_TEMPER,
                -(resolution_rate - 0.6) * 0.06,
            )
        return 0.0

    def _build_rationale(
        self,
        *,
        kc_id: str,
        raw_total: int,
        raw_resolved: int,
        raw_unresolved: int,
        resolution_rate: float,
        unresolution_rate: float,
        adjustment: float,
        persistent: bool,
    ) -> str | None:
        if raw_total < _MIN_OUTCOMES:
            return None

        fragments = [
            f"Remediation for {kc_id}: {raw_total} evaluated, "
            f"{raw_resolved} resolved, {raw_unresolved} unresolved "
            f"(recency-weighted: {resolution_rate:.0%} resolved)"
        ]

        if adjustment > 0:
            fragments.append(
                f"boosting misconception confidence by {adjustment:.3f} "
                f"because remediation has not been resolving the misconception"
            )
        elif adjustment < 0:
            fragments.append(
                f"slightly tempering misconception confidence by {abs(adjustment):.3f} "
                f"because remediation is consistently resolving"
            )

        if persistent:
            fragments.append(
                "persistent misconception flagged — "
                "current remediation approach may need teacher review or different strategy"
            )

        return "; ".join(fragments)


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
