from __future__ import annotations

from dataclasses import dataclass

from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class SocraticPromptSelector:
    audit_store: AuditStore
    min_samples_per_variant: int = 2
    max_events: int = 500

    def select_variant(self, *, fallback_variant: str) -> str:
        events = [
            event
            for event in self.audit_store.list(limit=self.max_events)
            if event.event_type == "assessment.socratic"
            and event.payload.get("prompt_template_name")
            and str(event.payload.get("prompt_template_name")).startswith(
                "assessment_probe."
            )
            and event.payload.get("prompt_template_variant")
        ]
        if not events:
            return fallback_variant

        grouped: dict[str, list[float]] = {}
        demonstrated_counts: dict[str, int] = {}
        profile_update_counts: dict[str, int] = {}
        for event in events:
            variant = str(event.payload.get("prompt_template_variant"))
            grouped.setdefault(variant, []).append(
                float(event.payload.get("evidence_score", 0.0))
            )
            demonstrated_counts[variant] = demonstrated_counts.get(variant, 0) + (
                1 if event.payload.get("evidence_strength") == "demonstrated" else 0
            )
            profile_update_counts[variant] = profile_update_counts.get(variant, 0) + (
                1 if bool(event.payload.get("profile_update_applied")) else 0
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
            average_evidence = sum(scores) / event_count
            demonstrated_rate = demonstrated_counts.get(variant, 0) / event_count
            profile_update_rate = profile_update_counts.get(variant, 0) / event_count
            return (
                average_evidence
                + (demonstrated_rate * 0.2)
                + (profile_update_rate * 0.1),
                average_evidence,
                event_count,
            )

        return max(eligible.items(), key=rank)[0]
