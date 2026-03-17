from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(BaseModel):
    event_id: str
    event_type: str
    status: str
    student_id: UUID | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ProviderHealthEvent(BaseModel):
    event_id: str
    provider_name: str
    status: str
    detail: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ProviderStatusSnapshot(BaseModel):
    provider_name: str
    status: str
    detail: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime


class PromptTemplateUsage(BaseModel):
    template_name: str
    event_count: int = 0


class ModerationCategoryCount(BaseModel):
    category: str
    event_count: int = 0


class SocraticPromptPerformance(BaseModel):
    template_name: str
    template_variant: str | None = None
    prompt_style: str | None = None
    event_count: int = 0
    average_evidence_score: float = 0.0
    demonstrated_rate: float = 0.0
    profile_update_rate: float = 0.0


class GenerationPromptPerformance(BaseModel):
    template_name: str
    template_variant: str | None = None
    content_type: str | None = None
    event_count: int = 0
    average_quality_score: float = 0.0
    average_composite_outcome: float = 0.0
    average_run_outcome_score: float = 0.0
    average_run_signal_confidence: float = 0.0
    run_summary_rate: float = 0.0
    persisted_run_summary_rate: float = 0.0
    positive_run_signal_rate: float = 0.0
    downstream_observation_rate: float = 0.0
    downstream_assessment_rate: float = 0.0
    session_outcome_rate: float = 0.0
    average_observation_trace_count: float = 0.0
    average_assessment_trace_count: float = 0.0
    average_session_generation_depth: float = 0.0


class TelemetrySnapshot(BaseModel):
    total_events: int = 0
    decision_events: int = 0
    generation_events: int = 0
    socratic_assessment_events: int = 0
    learning_progress_profile_events: int = 0
    improving_progress_signals: int = 0
    declining_progress_signals: int = 0
    socratic_profile_updates: int = 0
    socratic_demonstrated_events: int = 0
    socratic_step_back_events: int = 0
    average_socratic_evidence_score: float = 0.0
    fallback_generations: int = 0
    moderation_events: int = 0
    moderation_stream_events: int = 0
    moderation_flagged_generations: int = 0
    moderation_request_flags: int = 0
    moderation_response_flags: int = 0
    moderation_blocked_requests: int = 0
    moderation_rewritten_responses: int = 0
    moderation_provider_bypass_events: int = 0
    moderation_buffered_stream_rewrites: int = 0
    validation_issue_events: int = 0
    cache_hit_generations: int = 0
    warm_requests: int = 0
    predictive_warm_events: int = 0
    predictive_warm_requests: int = 0
    predictive_warm_process_events: int = 0
    predictive_cache_invalidations: int = 0
    pending_predictive_warm_tasks: int = 0
    deferred_predictive_warm_tasks: int = 0
    aged_routine_predictive_warm_tasks: int = 0
    eligible_predictive_warm_tasks: int = 0
    blocked_predictive_warm_tasks: int = 0
    stale_processing_predictive_warm_tasks: int = 0
    urgent_predictive_warm_tasks: int = 0
    next_predictive_warm_task_eta_seconds: int | None = None
    completed_predictive_warm_tasks: int = 0
    failed_predictive_warm_tasks: int = 0
    canceled_predictive_warm_tasks: int = 0
    retried_predictive_warm_tasks: int = 0
    requeued_predictive_warm_tasks: int = 0
    dropped_predictive_warm_tasks: int = 0
    generated_content_entries: int = 0
    fresh_generated_content_entries: int = 0
    provider_failure_events: int = 0
    provider_circuit_open_events: int = 0
    moderation_category_counts: list[ModerationCategoryCount] = Field(default_factory=list)
    prompt_template_usages: list[PromptTemplateUsage] = Field(default_factory=list)
    generation_prompt_performances: list[GenerationPromptPerformance] = Field(default_factory=list)
    socratic_prompt_performances: list[SocraticPromptPerformance] = Field(default_factory=list)
    provider_statuses: list[ProviderStatusSnapshot] = Field(default_factory=list)
    last_event_at: datetime | None = None
