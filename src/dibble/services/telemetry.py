from __future__ import annotations

from dibble.models.telemetry import TelemetrySnapshot
from dibble.services.audit_store import SQLiteAuditStore


class TelemetryService:
    def __init__(self, audit_store: SQLiteAuditStore) -> None:
        self.audit_store = audit_store

    def snapshot(self) -> TelemetrySnapshot:
        events = self.audit_store.list(limit=500)
        generation_events = [event for event in events if event.event_type.startswith("adaptive.generate")]
        decision_events = [event for event in events if event.event_type == "adaptive.decide"]

        last_event_at = events[0].created_at if events else None
        return TelemetrySnapshot(
            total_events=len(events),
            decision_events=len(decision_events),
            generation_events=len(generation_events),
            fallback_generations=sum(
                1 for event in generation_events if event.payload.get("delivery_mode") == "static_fallback"
            ),
            validation_issue_events=sum(
                1 for event in generation_events if int(event.payload.get("validation_issue_count", 0)) > 0
            ),
            last_event_at=last_event_at,
        )
