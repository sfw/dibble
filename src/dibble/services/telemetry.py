from __future__ import annotations

from collections import Counter

from dibble.models.telemetry import (
    GenerationPromptPerformance,
    PromptTemplateUsage,
    SocraticPromptPerformance,
    TelemetrySnapshot,
)
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_prompt_outcomes import GenerationPromptOutcomeScorer
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
        self.generation_outcome_scorer = GenerationPromptOutcomeScorer()

    def snapshot(self) -> TelemetrySnapshot:
        events = self.audit_store.list(limit=500)
        generation_events = [event for event in events if event.event_type.startswith("content.generate")]
        decision_events = [event for event in events if event.event_type == "adaptive.decide"]
        socratic_events = [event for event in events if event.event_type == "assessment.socratic"]
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
        generation_prompt_groups: dict[tuple[str, str | None, str | None], list[object]] = {}
        observation_events = [event for event in events if event.event_type == "learner.observe"]
        assessment_events = [event for event in events if event.event_type == "assessment.socratic"]
        for event in generation_events:
            template_name = event.payload.get("prompt_template_name")
            if not template_name:
                continue
            key = (
                str(template_name),
                str(event.payload.get("prompt_template_variant")) if event.payload.get("prompt_template_variant") else None,
                str(event.payload.get("content_type")) if event.payload.get("content_type") else None,
            )
            generation_prompt_groups.setdefault(key, []).append(
                self.generation_outcome_scorer.score(
                    generation_event=event,
                    candidate_generations=generation_events,
                    candidate_observations=observation_events,
                    candidate_assessments=assessment_events,
                )
            )
        socratic_evidence_scores = [
            float(event.payload.get("evidence_score", 0.0))
            for event in socratic_events
            if event.payload.get("evidence_score") is not None
        ]
        prompt_performance_groups: dict[tuple[str, str | None, str | None], list[object]] = {}
        for event in socratic_events:
            template_name = event.payload.get("prompt_template_name")
            if not template_name:
                continue
            key = (
                str(template_name),
                str(event.payload.get("prompt_template_variant")) if event.payload.get("prompt_template_variant") else None,
                str(event.payload.get("prompt_style")) if event.payload.get("prompt_style") else None,
            )
            prompt_performance_groups.setdefault(key, []).append(event)

        last_event_at = events[0].created_at if events else None
        return TelemetrySnapshot(
            total_events=len(events),
            decision_events=len(decision_events),
            generation_events=len(generation_events),
            socratic_assessment_events=len(socratic_events),
            socratic_profile_updates=sum(1 for event in socratic_events if bool(event.payload.get("profile_update_applied"))),
            socratic_demonstrated_events=sum(
                1 for event in socratic_events if event.payload.get("evidence_strength") == "demonstrated"
            ),
            socratic_step_back_events=sum(
                1 for event in socratic_events if event.payload.get("next_action") == "step_back"
            ),
            average_socratic_evidence_score=(
                round(sum(socratic_evidence_scores) / len(socratic_evidence_scores), 2) if socratic_evidence_scores else 0.0
            ),
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
            generation_prompt_performances=[
                self._build_generation_prompt_performance(key, grouped_samples)
                for key, grouped_samples in sorted(generation_prompt_groups.items())
            ],
            socratic_prompt_performances=[
                self._build_socratic_prompt_performance(key, grouped_events)
                for key, grouped_events in sorted(prompt_performance_groups.items())
            ],
            provider_statuses=(
                self.provider_health_store.latest_statuses() if self.provider_health_store is not None else []
            ),
            last_event_at=last_event_at,
        )

    def _build_socratic_prompt_performance(
        self,
        key: tuple[str, str | None, str | None],
        events,
    ) -> SocraticPromptPerformance:
        template_name, template_variant, prompt_style = key
        event_count = len(events)
        evidence_scores = [float(event.payload.get("evidence_score", 0.0)) for event in events]
        demonstrated_events = sum(1 for event in events if event.payload.get("evidence_strength") == "demonstrated")
        profile_updates = sum(1 for event in events if bool(event.payload.get("profile_update_applied")))
        return SocraticPromptPerformance(
            template_name=template_name,
            template_variant=template_variant,
            prompt_style=prompt_style,
            event_count=event_count,
            average_evidence_score=round(sum(evidence_scores) / event_count, 2) if event_count else 0.0,
            demonstrated_rate=round(demonstrated_events / event_count, 2) if event_count else 0.0,
            profile_update_rate=round(profile_updates / event_count, 2) if event_count else 0.0,
        )

    def _build_generation_prompt_performance(
        self,
        key: tuple[str, str | None, str | None],
        samples,
    ) -> GenerationPromptPerformance:
        template_name, template_variant, content_type = key
        event_count = len(samples)
        quality_scores = [sample.quality_score for sample in samples]
        composite_scores = [sample.composite_score for sample in samples]
        downstream_matches = sum(1 for sample in samples if sample.downstream_observation_score is not None)
        assessment_matches = sum(1 for sample in samples if sample.downstream_assessment_score is not None)
        session_outcome_matches = sum(1 for sample in samples if sample.session_outcome_score is not None)
        observation_trace_total = sum(sample.observation_match_count for sample in samples)
        assessment_trace_total = sum(sample.assessment_match_count for sample in samples)
        session_generation_depth_total = sum(sample.session_generation_depth for sample in samples)
        return GenerationPromptPerformance(
            template_name=template_name,
            template_variant=template_variant,
            content_type=content_type,
            event_count=event_count,
            average_quality_score=round(sum(quality_scores) / event_count, 2) if event_count else 0.0,
            average_composite_outcome=round(sum(composite_scores) / event_count, 2) if event_count else 0.0,
            downstream_observation_rate=round(downstream_matches / event_count, 2) if event_count else 0.0,
            downstream_assessment_rate=round(assessment_matches / event_count, 2) if event_count else 0.0,
            session_outcome_rate=round(session_outcome_matches / event_count, 2) if event_count else 0.0,
            average_observation_trace_count=round(observation_trace_total / event_count, 2) if event_count else 0.0,
            average_assessment_trace_count=round(assessment_trace_total / event_count, 2) if event_count else 0.0,
            average_session_generation_depth=round(session_generation_depth_total / event_count, 2)
            if event_count
            else 0.0,
        )
