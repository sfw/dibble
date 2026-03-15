from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.generation import RequestedContentType
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_prompt_outcomes import GenerationPromptOutcomeScorer


@dataclass(slots=True)
class GenerationPromptSelector:
    audit_store: SQLiteAuditStore
    min_samples_per_variant: int = 2
    max_events: int = 500
    outcome_scorer: GenerationPromptOutcomeScorer = field(default_factory=GenerationPromptOutcomeScorer)

    def select_variant(
        self,
        *,
        content_type: RequestedContentType,
        fallback_variant: str,
    ) -> str:
        prefix = f"{content_type.value}."
        events = self.audit_store.list(limit=self.max_events)
        generation_events = [
            event
            for event in events
            if event.event_type == "content.generate"
            and event.payload.get("content_type") == content_type.value
            and event.payload.get("prompt_template_name")
            and str(event.payload.get("prompt_template_name")).startswith(prefix)
            and event.payload.get("prompt_template_variant")
        ]
        if not generation_events:
            return fallback_variant
        observation_events = [event for event in events if event.event_type == "learner.observe"]
        assessment_events = [event for event in events if event.event_type == "assessment.socratic"]

        grouped: dict[str, list[float]] = {}
        validation_counts: dict[str, int] = {}
        grounded_counts: dict[str, int] = {}
        downstream_counts: dict[str, int] = {}
        assessment_counts: dict[str, int] = {}
        for event in generation_events:
            sample = self.outcome_scorer.score(
                generation_event=event,
                candidate_observations=observation_events,
                candidate_assessments=assessment_events,
            )
            grouped.setdefault(sample.variant, []).append(sample.composite_score)
            validation_counts[sample.variant] = validation_counts.get(sample.variant, 0) + (
                1 if sample.validation_passed else 0
            )
            grounded_counts[sample.variant] = grounded_counts.get(sample.variant, 0) + (
                1 if sample.grounding_count > 0 else 0
            )
            downstream_counts[sample.variant] = downstream_counts.get(sample.variant, 0) + (
                1 if sample.downstream_observation_score is not None else 0
            )
            assessment_counts[sample.variant] = assessment_counts.get(sample.variant, 0) + (
                1 if sample.downstream_assessment_score is not None else 0
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
            average_outcome = sum(scores) / event_count
            validation_rate = validation_counts.get(variant, 0) / event_count
            grounding_rate = grounded_counts.get(variant, 0) / event_count
            downstream_rate = downstream_counts.get(variant, 0) / event_count
            assessment_rate = assessment_counts.get(variant, 0) / event_count
            return (
                average_outcome
                + (validation_rate * 0.08)
                + (grounding_rate * 0.04)
                + (downstream_rate * 0.06)
                + (assessment_rate * 0.08),
                average_outcome,
                event_count,
            )

        return max(eligible.items(), key=rank)[0]
