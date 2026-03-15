from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import RequestedContentType
from dibble.services.audit_store import SQLiteAuditStore


@dataclass(slots=True)
class GenerationPromptSelector:
    audit_store: SQLiteAuditStore
    min_samples_per_variant: int = 2
    max_events: int = 500

    def select_variant(
        self,
        *,
        content_type: RequestedContentType,
        fallback_variant: str,
    ) -> str:
        prefix = f"{content_type.value}."
        events = [
            event
            for event in self.audit_store.list(limit=self.max_events)
            if event.event_type == "content.generate"
            and event.payload.get("content_type") == content_type.value
            and event.payload.get("prompt_template_name")
            and str(event.payload.get("prompt_template_name")).startswith(prefix)
            and event.payload.get("prompt_template_variant")
        ]
        if not events:
            return fallback_variant

        grouped: dict[str, list[float]] = {}
        validation_counts: dict[str, int] = {}
        grounded_counts: dict[str, int] = {}
        for event in events:
            variant = str(event.payload.get("prompt_template_variant"))
            grouped.setdefault(variant, []).append(float(event.payload.get("quality_score", 0.0)))
            validation_counts[variant] = validation_counts.get(variant, 0) + (
                1 if bool(event.payload.get("validation_passed")) else 0
            )
            grounded_counts[variant] = grounded_counts.get(variant, 0) + (
                1 if int(event.payload.get("grounding_count", 0)) > 0 else 0
            )

        eligible = {
            variant: scores
            for variant, scores in grouped.items()
            if len(scores) >= self.min_samples_per_variant
        }
        if not eligible:
            return fallback_variant

        def rank(item: tuple[str, list[float]]) -> tuple[float, float, int]:
            variant, scores = item
            event_count = len(scores)
            average_quality = sum(scores) / event_count
            validation_rate = validation_counts.get(variant, 0) / event_count
            grounding_rate = grounded_counts.get(variant, 0) / event_count
            return (
                average_quality + (validation_rate * 0.1) + (grounding_rate * 0.05),
                average_quality,
                event_count,
            )

        return max(eligible.items(), key=rank)[0]
