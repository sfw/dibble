from __future__ import annotations

from dataclasses import dataclass

from dibble.models.telemetry import AuditEvent
from dibble.services.generation_run_summaries import GenerationRunSummary


@dataclass(frozen=True, slots=True)
class PersistedGenerationRunSummary:
    event_id: str
    summary: GenerationRunSummary


@dataclass(slots=True)
class PersistedRunSummaryResolver:
    def resolve_for_generation(
        self,
        *,
        generation_event: AuditEvent,
        summary_events: list[AuditEvent],
    ) -> PersistedGenerationRunSummary | None:
        matched_events = [
            event
            for event in summary_events
            if event.event_type == "learning.run.summary" and self._matches_generation(event, generation_event)
        ]
        if not matched_events:
            return None
        matched_events.sort(
            key=lambda event: (
                int(event.payload.get("run_event_count", 0)),
                int(event.payload.get("run_direct_source_count", 0)),
                float(event.payload.get("run_calibration_confidence", 0.0)),
                event.created_at,
            ),
            reverse=True,
        )
        selected_event = matched_events[0]
        return PersistedGenerationRunSummary(
            event_id=selected_event.event_id,
            summary=GenerationRunSummary(
                run_outcome_score=float(selected_event.payload["run_summary_score"]),
                calibration_signal=str(selected_event.payload.get("run_calibration_signal", "insufficient")),
                calibration_confidence=float(selected_event.payload.get("run_calibration_confidence", 0.0)),
                direct_source_count=int(selected_event.payload.get("run_direct_source_count", 0)),
                event_count=int(selected_event.payload.get("run_event_count", 0)),
            ),
        )

    def _matches_generation(self, summary_event: AuditEvent, generation_event: AuditEvent) -> bool:
        if summary_event.student_id != generation_event.student_id:
            return False
        if summary_event.payload.get("source_generation_event_id") == generation_event.event_id:
            return True
        generation_id = generation_event.payload.get("generation_id")
        if generation_id and summary_event.payload.get("generation_id") == generation_id:
            return True
        return False
