from __future__ import annotations

from collections import Counter

from dibble.models.telemetry import (
    GenerationPromptPerformance,
    ModerationCategoryCount,
    PromptTemplateUsage,
    SocraticPromptPerformance,
    TelemetrySnapshot,
)
from dibble.services.generation_prompt_outcomes import GenerationPromptOutcomeScorer
from dibble.services.protocols import AuditStore, GeneratedContentStore, PredictiveWarmTaskStore, ProviderHealthStore


class TelemetryService:
    def __init__(
        self,
        audit_store: AuditStore,
        generated_content_store: GeneratedContentStore | None = None,
        provider_health_store: ProviderHealthStore | None = None,
        predictive_warm_queue_store: PredictiveWarmTaskStore | None = None,
    ) -> None:
        self.audit_store = audit_store
        self.generated_content_store = generated_content_store
        self.provider_health_store = provider_health_store
        self.predictive_warm_queue_store = predictive_warm_queue_store
        self.generation_outcome_scorer = GenerationPromptOutcomeScorer()

    def snapshot(self) -> TelemetrySnapshot:
        events = self.audit_store.list(limit=500)
        generation_events = [event for event in events if event.event_type.startswith("content.generate")]
        decision_events = [event for event in events if event.event_type == "adaptive.decide"]
        socratic_events = [event for event in events if event.event_type == "assessment.socratic"]
        progress_profile_events = [event for event in events if event.event_type == "learning.progress.profile"]
        warm_events = [event for event in events if event.event_type in {"content.warm", "content.warm.predictive"}]
        moderation_events = [event for event in events if event.event_type == "content.moderation"]
        predictive_warm_events = [event for event in events if event.event_type == "content.warm.predictive"]
        predictive_warm_process_events = [
            event for event in events if event.event_type == "content.warm.predictive.process"
        ]
        cache_invalidation_events = [event for event in events if event.event_type == "content.cache.invalidate"]
        provider_events = self.provider_health_store.list(limit=500) if self.provider_health_store is not None else []
        cache_stats = self.generated_content_store.stats() if self.generated_content_store is not None else {
            "total_entries": 0,
            "fresh_entries": 0,
            "expired_entries": 0,
        }
        queue_stats = (
            self.predictive_warm_queue_store.stats()
            if self.predictive_warm_queue_store is not None
            else {"pending": 0, "deferred": 0, "completed": 0, "failed": 0, "canceled": 0}
        )
        prompt_template_counts = Counter(
            str(event.payload.get("prompt_template_name"))
            for event in generation_events
            if event.payload.get("prompt_template_name")
        )
        moderation_category_counts = Counter(
            str(category)
            for event in moderation_events
            for category in event.payload.get("categories", [])
            if category is not None
        )
        generation_prompt_groups: dict[tuple[str, str | None, str | None], list[object]] = {}
        observation_events = [event for event in events if event.event_type == "learner.observe"]
        assessment_events = [event for event in events if event.event_type == "assessment.socratic"]
        run_summary_events = [event for event in events if event.event_type == "learning.run.summary"]
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
                    candidate_run_summaries=run_summary_events,
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
            learning_progress_profile_events=len(progress_profile_events),
            improving_progress_signals=sum(
                1 for event in progress_profile_events if event.payload.get("progress_signal") == "improving"
            ),
            declining_progress_signals=sum(
                1 for event in progress_profile_events if event.payload.get("progress_signal") == "declining"
            ),
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
            moderation_events=len(moderation_events),
            moderation_stream_events=sum(1 for event in moderation_events if bool(event.payload.get("stream_emitted"))),
            moderation_flagged_generations=sum(
                1 for event in generation_events if event.payload.get("moderation_status") == "flagged"
            ),
            moderation_request_flags=sum(
                1
                for event in generation_events
                if event.payload.get("moderation_status") == "flagged"
                and event.payload.get("moderation_stage") == "request"
            ),
            moderation_response_flags=sum(
                1
                for event in generation_events
                if event.payload.get("moderation_status") == "flagged"
                and event.payload.get("moderation_stage") == "response"
            ),
            moderation_blocked_requests=sum(
                1 for event in moderation_events if event.payload.get("stage") == "request" and bool(event.payload.get("blocked"))
            ),
            moderation_rewritten_responses=sum(
                1
                for event in moderation_events
                if event.payload.get("stage") == "response" and bool(event.payload.get("response_rewritten"))
            ),
            moderation_provider_bypass_events=sum(
                1
                for event in moderation_events
                if bool(event.payload.get("request_blocked")) and not bool(event.payload.get("provider_invoked"))
            ),
            moderation_buffered_stream_rewrites=sum(
                1
                for event in moderation_events
                if bool(event.payload.get("stream_emitted"))
                and bool(event.payload.get("response_rewritten"))
                and bool(event.payload.get("stream_buffered"))
            ),
            validation_issue_events=sum(
                1 for event in generation_events if int(event.payload.get("validation_issue_count", 0)) > 0
            ),
            cache_hit_generations=sum(1 for event in generation_events if bool(event.payload.get("cache_hit"))),
            warm_requests=sum(
                int(event.payload.get("total_requests", event.payload.get("predicted_request_count", 0)))
                for event in warm_events
            ),
            predictive_warm_events=len(predictive_warm_events),
            predictive_warm_requests=sum(
                int(event.payload.get("predicted_request_count", 0)) for event in predictive_warm_events
            ),
            predictive_warm_process_events=len(predictive_warm_process_events),
            predictive_cache_invalidations=sum(
                int(event.payload.get("expired_entries", 0)) for event in cache_invalidation_events
            ),
            expired_predictive_warm_tasks=sum(
                int(event.payload.get("expired_tasks", 0))
                for event in warm_events + predictive_warm_process_events
            ),
            supplemental_inline_predictive_warm_tasks=sum(
                int(event.payload.get("supplemental_tasks", 0)) for event in predictive_warm_events
            ),
            pending_predictive_warm_tasks=queue_stats["pending"],
            deferred_predictive_warm_tasks=queue_stats.get("deferred", 0),
            aged_routine_predictive_warm_tasks=queue_stats.get("aged_routine", 0),
            eligible_predictive_warm_tasks=queue_stats.get("eligible_now", 0),
            blocked_predictive_warm_tasks=queue_stats.get("blocked_deferred", 0),
            stale_processing_predictive_warm_tasks=queue_stats.get("stale_processing", 0),
            urgent_predictive_warm_tasks=queue_stats.get("urgent_active", 0),
            next_predictive_warm_task_eta_seconds=queue_stats.get("next_eligible_in_seconds"),
            completed_predictive_warm_tasks=queue_stats["completed"],
            failed_predictive_warm_tasks=queue_stats["failed"],
            canceled_predictive_warm_tasks=queue_stats["canceled"],
            retried_predictive_warm_tasks=sum(
                int(event.payload.get("retried_tasks", 0)) for event in predictive_warm_process_events
            ),
            requeued_predictive_warm_tasks=sum(
                int(event.payload.get("requeued_tasks", 0)) for event in predictive_warm_process_events
            ),
            dropped_predictive_warm_tasks=sum(
                int(event.payload.get("dropped_tasks", 0)) for event in predictive_warm_process_events
            ),
            generated_content_entries=cache_stats["total_entries"],
            fresh_generated_content_entries=cache_stats["fresh_entries"],
            provider_failure_events=sum(1 for event in provider_events if event.status == "failure"),
            provider_circuit_open_events=sum(1 for event in provider_events if event.status == "circuit_open"),
            moderation_category_counts=[
                ModerationCategoryCount(category=category, event_count=count)
                for category, count in sorted(moderation_category_counts.items())
            ],
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
        run_scores = [sample.run_summary_score for sample in samples if sample.run_summary_score is not None]
        run_summary_matches = sum(1 for sample in samples if sample.run_summary_score is not None)
        persisted_run_summary_matches = sum(1 for sample in samples if sample.run_summary_source == "persisted")
        positive_run_signals = sum(1 for sample in samples if sample.run_calibration_signal == "positive")
        run_signal_confidence_total = sum(sample.run_calibration_confidence for sample in samples)
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
            average_run_outcome_score=round(sum(run_scores) / len(run_scores), 2) if run_scores else 0.0,
            average_run_signal_confidence=round(run_signal_confidence_total / event_count, 2) if event_count else 0.0,
            run_summary_rate=round(run_summary_matches / event_count, 2) if event_count else 0.0,
            persisted_run_summary_rate=round(persisted_run_summary_matches / event_count, 2) if event_count else 0.0,
            positive_run_signal_rate=round(positive_run_signals / event_count, 2) if event_count else 0.0,
            downstream_observation_rate=round(downstream_matches / event_count, 2) if event_count else 0.0,
            downstream_assessment_rate=round(assessment_matches / event_count, 2) if event_count else 0.0,
            session_outcome_rate=round(session_outcome_matches / event_count, 2) if event_count else 0.0,
            average_observation_trace_count=round(observation_trace_total / event_count, 2) if event_count else 0.0,
            average_assessment_trace_count=round(assessment_trace_total / event_count, 2) if event_count else 0.0,
            average_session_generation_depth=round(session_generation_depth_total / event_count, 2)
            if event_count
            else 0.0,
        )
