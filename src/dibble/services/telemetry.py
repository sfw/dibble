from __future__ import annotations

from collections import Counter

from dibble.models.telemetry import PromptTemplateUsage, TelemetrySnapshot
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.provider_health import SQLiteProviderHealthStore


class TelemetryService:
    def __init__(
        self,
        audit_store: SQLiteAuditStore,
        generated_content_store: SQLiteGeneratedContentStore | None = None,
        provider_health_store: SQLiteProviderHealthStore | None = None,
    ) -> None:
        self.audit_store = audit_store
        self.generated_content_store = generated_content_store
        self.provider_health_store = provider_health_store

    def snapshot(self) -> TelemetrySnapshot:
        events = self.audit_store.list(limit=500)
        generation_events = [event for event in events if event.event_type.startswith("content.generate")]
        decision_events = [event for event in events if event.event_type == "adaptive.decide"]
        warm_events = [event for event in events if event.event_type == "content.warm"]
        provider_events = self.provider_health_store.list(limit=500) if self.provider_health_store is not None else []
        cache_stats = self.generated_content_store.stats() if self.generated_content_store is not None else {
            "total_entries": 0,
            "fresh_entries": 0,
            "expired_entries": 0,
        }
        prompt_template_counts = Counter(
            str(event.payload.get("prompt_template_name"))
            for event in generation_events
            if event.payload.get("prompt_template_name")
        )

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
            cache_hit_generations=sum(1 for event in generation_events if bool(event.payload.get("cache_hit"))),
            warm_requests=sum(int(event.payload.get("total_requests", 0)) for event in warm_events),
            generated_content_entries=cache_stats["total_entries"],
            fresh_generated_content_entries=cache_stats["fresh_entries"],
            provider_failure_events=sum(1 for event in provider_events if event.status == "failure"),
            provider_circuit_open_events=sum(1 for event in provider_events if event.status == "circuit_open"),
            prompt_template_usages=[
                PromptTemplateUsage(template_name=name, event_count=count)
                for name, count in sorted(prompt_template_counts.items())
            ],
            provider_statuses=(
                self.provider_health_store.latest_statuses() if self.provider_health_store is not None else []
            ),
            last_event_at=last_event_at,
        )
