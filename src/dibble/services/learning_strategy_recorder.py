from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.telemetry import AuditEvent
from dibble.services.learning_strategy_builder import LearningStrategyProfileBuilder
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class LearningStrategyProfileRecorder:
    audit_store: AuditStore
    profile_builder: LearningStrategyProfileBuilder = field(
        default_factory=LearningStrategyProfileBuilder
    )
    max_events: int = 1000

    def record_from_summary_events(
        self, *, summary_events: list[AuditEvent]
    ) -> list[AuditEvent]:
        if not summary_events:
            return []
        events = self.audit_store.list(limit=self.max_events)
        progress_events = [
            event for event in events if event.event_type == "learning.progress.profile"
        ]
        recorded: list[AuditEvent] = []
        for summary_event in summary_events:
            if (
                summary_event.student_id is None
                or summary_event.event_type != "learning.run.summary"
            ):
                continue
            progress_event = self._matching_progress_event(
                summary_event=summary_event, progress_events=progress_events
            )
            snapshot = self.profile_builder.build_from_summary_event(
                summary_event=summary_event,
                progress_event=progress_event,
            )
            if snapshot is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.strategy.profile",
                    status="success",
                    student_id=str(summary_event.student_id),
                    payload={
                        "source_run_summary_event_id": summary_event.event_id,
                        "intent": summary_event.payload.get("intent"),
                        "content_type": summary_event.payload.get("content_type"),
                        "target_kc_ids": summary_event.payload.get("target_kc_ids", []),
                        "target_lo_ids": summary_event.payload.get("target_lo_ids", []),
                        "average_run_outcome_score": snapshot.average_run_outcome_score,
                        "average_run_confidence": snapshot.average_run_confidence,
                        "matched_run_count": snapshot.matched_run_count,
                        "matched_session_count": snapshot.matched_session_count,
                        "positive_run_rate": snapshot.positive_run_rate,
                        "negative_run_rate": snapshot.negative_run_rate,
                        "progress_signal": snapshot.progress_signal,
                        "progress_delta": snapshot.progress_delta,
                        "strategy_signal": snapshot.signal,
                        "strategy_support_bias": snapshot.support_bias,
                        "strategy_recovery_focus": snapshot.recovery_focus,
                        "strategy_trajectory_state": snapshot.trajectory_state,
                        "strategy_recommended_next_action": snapshot.recommended_next_action,
                        "strategy_volatility_index": snapshot.volatility_index,
                        "strategy_relapse_risk": snapshot.relapse_risk,
                        "strategy_rationale": snapshot.rationale,
                    },
                )
            )
        return recorded

    def _matching_progress_event(
        self,
        *,
        summary_event: AuditEvent,
        progress_events: list[AuditEvent],
    ) -> AuditEvent | None:
        matched = [
            event
            for event in progress_events
            if event.student_id == summary_event.student_id
            and event.payload.get("source_run_summary_event_id")
            == summary_event.event_id
        ]
        if not matched:
            return None
        matched.sort(key=lambda event: event.created_at, reverse=True)
        return matched[0]
