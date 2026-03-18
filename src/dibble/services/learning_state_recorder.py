from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.telemetry import AuditEvent
from dibble.services.learning_state_builder import LearningStateProfileBuilder
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class LearningStateProfileRecorder:
    audit_store: AuditStore
    profile_builder: LearningStateProfileBuilder = field(
        default_factory=LearningStateProfileBuilder
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
        strategy_events = [
            event for event in events if event.event_type == "learning.strategy.profile"
        ]
        recorded: list[AuditEvent] = []
        for summary_event in summary_events:
            if (
                summary_event.student_id is None
                or summary_event.event_type != "learning.run.summary"
            ):
                continue
            progress_event = self._matching_event(
                summary_event=summary_event,
                profile_events=progress_events,
            )
            strategy_event = self._matching_event(
                summary_event=summary_event,
                profile_events=strategy_events,
            )
            snapshot = self.profile_builder.build_from_summary_event(
                summary_event=summary_event,
                progress_event=progress_event,
                strategy_event=strategy_event,
            )
            if snapshot is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.state.profile",
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
                        "progress_signal": snapshot.progress_signal,
                        "progress_delta": snapshot.progress_delta,
                        "strategy_signal": snapshot.strategy_signal,
                        "strategy_trajectory_state": snapshot.strategy_trajectory_state,
                        "state_profile_signal": snapshot.signal,
                        "engagement": snapshot.engagement.value,
                        "frustration": snapshot.frustration.value,
                        "confusion": snapshot.confusion.value,
                        "confidence": snapshot.confidence,
                        "intrinsic_load": snapshot.intrinsic_load,
                        "extraneous_load": snapshot.extraneous_load,
                        "germane_load": snapshot.germane_load,
                        "total_load": snapshot.total_load,
                        "capacity_utilization": snapshot.capacity_utilization,
                        "confidence_calibration": snapshot.confidence_calibration,
                        "help_seeking": snapshot.help_seeking.value,
                        "help_seeking_effectiveness": snapshot.help_seeking_effectiveness,
                        "self_monitoring": snapshot.self_monitoring,
                        "affective_reliability": snapshot.affective_reliability,
                        "load_reliability": snapshot.load_reliability,
                        "recovery_stability": snapshot.recovery_stability,
                        "overload_risk": snapshot.overload_risk,
                        "metacognitive_reliability": snapshot.metacognitive_reliability,
                        "state_profile_rationale": snapshot.rationale,
                    },
                )
            )
        return recorded

    def _matching_event(
        self,
        *,
        summary_event: AuditEvent,
        profile_events: list[AuditEvent],
    ) -> AuditEvent | None:
        matched = [
            event
            for event in profile_events
            if event.student_id == summary_event.student_id
            and event.payload.get("source_run_summary_event_id")
            == summary_event.event_id
        ]
        if not matched:
            return None
        matched.sort(key=lambda event: event.created_at, reverse=True)
        return matched[0]
