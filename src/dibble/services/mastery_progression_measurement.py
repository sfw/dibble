"""Audit-backed measurement for mastery and progression heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dibble.models.observability import (
    MasteryProgressionMeasurementSummary,
    MasteryProgressionMetric,
)
from dibble.models.telemetry import AuditEvent
from dibble.services.protocols import AuditStore


_HOLD_ACTIONS = frozenset(
    {
        "hold_target",
        "hold_repair_target",
        "hold_bridge_target",
    }
)
_TRANSFER_ACTION = "attempt_transfer"
_PREREQUISITE_REBUILD_ACTION = "rebuild_prerequisite_first"
_REGRESSED_OUTCOME_STATES = frozenset({"active", "ready", "blocked"})


@dataclass(slots=True)
class MasteryProgressionMeasurementService:
    """Computes bounded, inspectable metrics from durable audit evidence."""

    audit_store: AuditStore

    def summarize(
        self,
        *,
        learner_id: UUID | str | None = None,
        limit: int = 500,
        lookback_days: int | None = 90,
    ) -> MasteryProgressionMeasurementSummary:
        safe_limit = max(1, min(limit, 2000))
        safe_lookback_days = (
            max(1, min(lookback_days, 365)) if lookback_days is not None else None
        )
        learner_key = str(learner_id) if learner_id is not None else None
        events = self._filtered_events(
            learner_id=learner_key,
            limit=safe_limit,
            lookback_days=safe_lookback_days,
        )
        progression_events = [
            event for event in events if event.event_type == "progression.outcome"
        ]
        transition_events = [
            event
            for event in events
            if event.event_type == "curriculum.outcome.transition"
        ]

        hold = self._decision_metric(
            events=progression_events,
            actions=_HOLD_ACTIONS,
            positive=True,
            rationale="Positive hold outcomes divided by conclusive hold outcomes.",
        )
        transfer = self._decision_metric(
            events=progression_events,
            actions={_TRANSFER_ACTION},
            positive=True,
            rationale="Positive transfer outcomes divided by conclusive transfer outcomes.",
        )
        rebuild = self._decision_metric(
            events=progression_events,
            actions={_PREREQUISITE_REBUILD_ACTION},
            positive=True,
            rationale=(
                "Positive prerequisite-rebuild outcomes divided by conclusive "
                "prerequisite-rebuild outcomes."
            ),
        )
        release_regret = self._decision_metric(
            events=progression_events,
            actions={_TRANSFER_ACTION},
            positive=False,
            rationale="Negative transfer outcomes divided by conclusive transfer outcomes.",
        )
        over_hold = self._decision_metric(
            events=progression_events,
            actions=_HOLD_ACTIONS,
            positive=False,
            rationale="Negative hold outcomes divided by conclusive hold outcomes.",
        )
        false_positive = self._false_positive_mastery_metric(
            events=transition_events,
        )
        stability = self._outcome_mastery_stability_metric(
            false_positive=false_positive,
        )

        return MasteryProgressionMeasurementSummary(
            scope="learner" if learner_key is not None else "aggregate",
            learner_id=learner_key,
            lookback_event_limit=safe_limit,
            lookback_days=safe_lookback_days,
            source_event_count=len(events),
            progression_outcome_event_count=len(progression_events),
            outcome_transition_event_count=len(transition_events),
            hold_positive_rate=hold,
            transfer_positive_rate=transfer,
            prerequisite_rebuild_positive_rate=rebuild,
            false_positive_mastery_rate=false_positive,
            release_regret_rate=release_regret,
            over_hold_rate=over_hold,
            outcome_mastery_stability=stability,
            assumptions=[
                "Decision rates use only conclusive progression.outcome events: positive or negative.",
                "False-positive mastery uses a mastered outcome transition followed by a later transition from mastered to active, ready, or blocked.",
                "Outcome mastery stability is the complement of false-positive mastery over the same mastered-transition denominator.",
                "Raw learner.observe events are not used for false-positive mastery because they do not always carry an outcome_id.",
            ],
        )

    def _filtered_events(
        self,
        *,
        learner_id: str | None,
        limit: int,
        lookback_days: int | None,
    ) -> list[AuditEvent]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=lookback_days)
            if lookback_days is not None
            else None
        )
        events = self.audit_store.list(limit=limit)
        filtered: list[AuditEvent] = []
        for event in events:
            if learner_id is not None and str(event.student_id) != learner_id:
                continue
            if cutoff is not None and _event_time(event) < cutoff:
                continue
            filtered.append(event)
        return filtered

    def _decision_metric(
        self,
        *,
        events: list[AuditEvent],
        actions: set[str] | frozenset[str],
        positive: bool,
        rationale: str,
    ) -> MasteryProgressionMetric:
        conclusive = [
            event
            for event in events
            if str(event.payload.get("decision_action", "")) in actions
            and str(event.payload.get("outcome", event.status))
            in {"positive", "negative"}
        ]
        target_outcome = "positive" if positive else "negative"
        numerator = sum(
            1
            for event in conclusive
            if str(event.payload.get("outcome", event.status)) == target_outcome
        )
        return _metric(
            numerator=numerator,
            denominator=len(conclusive),
            rationale=rationale,
        )

    def _false_positive_mastery_metric(
        self,
        *,
        events: list[AuditEvent],
    ) -> MasteryProgressionMetric:
        ascending = sorted(events, key=_event_time)
        mastered_events = [
            event
            for event in ascending
            if str(event.payload.get("to_state", "")) == "mastered"
            and str(event.payload.get("from_state", "")) != "mastered"
            and event.payload.get("outcome_id") is not None
        ]
        regressions = 0
        for event in mastered_events:
            outcome_id = str(event.payload.get("outcome_id"))
            event_time = _event_time(event)
            if any(
                _is_mastery_regression(
                    candidate,
                    outcome_id=outcome_id,
                    after=event_time,
                )
                for candidate in ascending
            ):
                regressions += 1
        return _metric(
            numerator=regressions,
            denominator=len(mastered_events),
            rationale=(
                "New mastered outcome transitions followed by later mastered-to-active, "
                "mastered-to-ready, or mastered-to-blocked transitions."
            ),
        )

    def _outcome_mastery_stability_metric(
        self,
        *,
        false_positive: MasteryProgressionMetric,
    ) -> MasteryProgressionMetric:
        denominator = false_positive.denominator
        numerator = max(denominator - false_positive.numerator, 0)
        return _metric(
            numerator=numerator,
            denominator=denominator,
            rationale=(
                "New mastered outcome transitions that did not later regress inside "
                "the bounded audit window."
            ),
        )


def _metric(*, numerator: int, denominator: int, rationale: str) -> MasteryProgressionMetric:
    rate = round(numerator / denominator, 4) if denominator else None
    return MasteryProgressionMetric(
        numerator=numerator,
        denominator=denominator,
        rate=rate,
        rationale=rationale,
    )


def _event_time(event: AuditEvent) -> datetime:
    value = event.created_at
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_mastery_regression(
    event: AuditEvent,
    *,
    outcome_id: str,
    after: datetime,
) -> bool:
    return (
        _event_time(event) > after
        and str(event.payload.get("outcome_id")) == outcome_id
        and str(event.payload.get("from_state")) == "mastered"
        and str(event.payload.get("to_state")) in _REGRESSED_OUTCOME_STATES
    )
