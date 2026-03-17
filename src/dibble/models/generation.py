from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContentIntent(str, Enum):
    explanation = "explanation"
    practice = "practice"
    remediation = "remediation"
    assessment = "assessment"


class RequestedContentType(str, Enum):
    micro_explanation = "micro_explanation"
    worked_example = "worked_example"
    practice_problem = "practice_problem"
    remedial_micro_module = "remedial_micro_module"
    assessment_probe = "assessment_probe"


class WorkedExampleFading(str, Enum):
    full = "full"
    completion = "completion"
    independent = "independent"


class PracticeDifficultyBand(str, Enum):
    support = "support"
    on_grade = "on_grade"
    stretch = "stretch"


class InterventionType(str, Enum):
    step_back = "step_back"
    targeted_practice = "targeted_practice"
    reteach = "reteach"
    stretch = "stretch"


class DeliveryMode(str, Enum):
    generated = "generated"
    blended = "blended"
    static_fallback = "static_fallback"


class GenerationRequest(BaseModel):
    student_id: UUID
    learning_session_id: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    intent: ContentIntent = ContentIntent.explanation
    requested_content_type: RequestedContentType | None = None
    learner_prompt: str | None = None
    curriculum_context: list[str] = Field(default_factory=list)
    predictive_warm: bool = False
    warm_reason: str | None = None
    source_generation_id: str | None = None
    target_kc_hints: list["TargetKcGenerationHint"] = Field(default_factory=list)
    mode_calibration: "GenerationModeCalibration | None" = None


class GenerationModeCalibration(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0
    support_bias: int = Field(default=0, ge=-1, le=1)
    strategy_signal: str = "insufficient"
    strategy_recovery_focus: str = "monitor"
    strategy_trajectory_state: str = "insufficient"
    strategy_recommended_next_action: str = "monitor"
    strategy_volatility_index: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_relapse_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_source: str = "insufficient"
    strategy_rationale: str | None = None
    state_profile_signal: str = "insufficient"
    state_profile_source: str = "insufficient"
    state_profile_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_total_load: float = Field(default=0.4, ge=0.0, le=1.0)
    state_profile_confidence_calibration: float = Field(default=0.5, ge=0.0, le=1.0)
    state_profile_help_seeking: str = "low"
    state_profile_affective_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_load_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_recovery_stability: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_overload_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_metacognitive_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_signal: str = "insufficient"
    trait_profile_source: str = "insufficient"
    trait_profile_trait_stability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_challenge_tolerance: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_challenge_evidence_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_processing_speed_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_working_memory_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_spatial_reasoning_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_sequence_action: str = "monitor"
    strategy_sequence_primary_kc_id: str | None = None
    strategy_sequence_kc_ids: list[str] = Field(default_factory=list)
    strategy_sequence_deferred_kc_ids: list[str] = Field(default_factory=list)
    strategy_sequence_rationale: str | None = None
    sequence_action: str = "monitor"
    sequence_primary_kc_id: str | None = None
    sequence_kc_ids: list[str] = Field(default_factory=list)
    sequence_deferred_kc_ids: list[str] = Field(default_factory=list)
    sequence_source: str = "insufficient"
    sequence_rationale: str | None = None
    session_signal: str = "insufficient"
    session_source: str = "insufficient"
    session_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    session_support_bias: int = Field(default=0, ge=-1, le=1)
    session_sequence_action: str = "monitor"
    session_primary_kc_id: str | None = None
    session_observation_count: int = Field(default=0, ge=0)
    session_assessment_count: int = Field(default=0, ge=0)
    session_phase: str = "monitor"
    session_recovery_intent: str = "monitor"
    session_support_step_budget: int = Field(default=0, ge=0)
    session_support_steps_remaining: int = Field(default=0, ge=0)
    session_stuck_loop_risk: str = "low"
    session_arc_action: str = "steady"
    session_generated_step_count: int = Field(default=0, ge=0)
    session_positive_streak: int = Field(default=0, ge=0)
    session_negative_streak: int = Field(default=0, ge=0)
    current_evidence_signal: str = "steady"
    current_evidence_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    current_evidence_rationale: str | None = None
    session_latest_prompt_style: str | None = None
    session_latest_next_action: str = "monitor"
    session_latest_evidence_strength: str = "insufficient"
    socratic_steering_action: str = "steady"
    session_rationale: str | None = None
    rationale: str | None = None


class RouteCalibrationSummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    positive_run_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    negative_run_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0


class AdaptiveRouteDecision(BaseModel):
    intervention_type: InterventionType
    delivery_mode: DeliveryMode
    scaffolding_level: str
    reasons: list[str]
    calibration: RouteCalibrationSummary | None = None


class GroundingReference(BaseModel):
    resource_id: str
    title: str
    grade_level: str
    subject: str | None = None
    source_type: str | None = None
    score: float = Field(ge=0.0)
    matched_terms: list[str] = Field(default_factory=list)
    excerpt: str | None = None


class GeneratedBlock(BaseModel):
    kind: str
    title: str
    body: str


class GeneratedBlockChunk(BaseModel):
    block_index: int
    kind: str
    title: str
    body_delta: str
    done: bool = False


class MisconceptionSignal(BaseModel):
    kc_id: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    source: str = "heuristic"
    misconception_id: str | None = None
    recommended_kc_ids: list[str] = Field(default_factory=list)
    remediation_hint: str | None = None
    evidence_terms: list[str] = Field(default_factory=list)
    recurrence_count: int = Field(default=0, ge=0)
    recurrence_session_count: int = Field(default=0, ge=0)
    recurrence_signal: str = "none"
    last_seen_at: datetime | None = None
    primary_for_kc: bool = False
    disambiguation_score: float = Field(default=0.0, ge=0.0)
    disambiguation_rationale: str | None = None


class TargetKcGenerationHint(BaseModel):
    kc_id: str
    kc_name: str
    concept_family: str | None = None
    taxonomy_cluster_id: str | None = None
    nearby_kc_names: list[str] = Field(default_factory=list)
    misconception_ids: list[str] = Field(default_factory=list)
    misconception_labels: list[str] = Field(default_factory=list)
    misconception_descriptions: list[str] = Field(default_factory=list)
    remediation_hints: list[str] = Field(default_factory=list)


class ModerationMatch(BaseModel):
    category: str
    matched_terms: list[str] = Field(default_factory=list)
    reason: str
    severity: str = "block"


class ModerationResult(BaseModel):
    status: str = "clear"
    stage: str = "none"
    severity: str = "none"
    decision: str = "allow"
    categories: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    matches: list[ModerationMatch] = Field(default_factory=list)
    blocked: bool = False
    request_blocked: bool = False
    response_rewritten: bool = False
    fallback_applied: bool = False
    fallback_kind: str | None = None
    stream_action: str = "none"
    provider_invoked: bool = False
    stream_buffered: bool = False
    original_block_count: int = Field(default=0, ge=0)
    replacement_block_count: int = Field(default=0, ge=0)
    audit_message: str | None = None


class GenerationMetadata(BaseModel):
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    validation_passed: bool = True
    validation_issue_count: int = Field(default=0, ge=0)
    grounding_count: int = Field(default=0, ge=0)
    provider_name: str | None = None
    model_used: str | None = None
    prompt_template_name: str | None = None
    prompt_template_version: str | None = None
    prompt_template_variant: str | None = None
    generation_latency_ms: int = Field(default=0, ge=0)
    cache_hit: bool = False
    moderation: ModerationResult = Field(default_factory=ModerationResult)


class GenerationResponse(BaseModel):
    student_id: UUID
    generated_at: datetime = Field(default_factory=utc_now)
    route: AdaptiveRouteDecision
    blocks: list[GeneratedBlock]
    curriculum_context: list[str]
    grounding: list[GroundingReference] = Field(default_factory=list)
    safety_notes: list[str]
    validation_issues: list[str] = Field(default_factory=list)
    generation_id: str | None = None
    generation_metadata: GenerationMetadata | None = None


class GeneratedContent(BaseModel):
    generation_id: str
    student_id: UUID
    content_type: str
    request_context: dict[str, object] = Field(default_factory=dict)
    response: GenerationResponse
    quality: GenerationMetadata
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class GenerationStreamEvent(BaseModel):
    event: str
    student_id: UUID
    route: AdaptiveRouteDecision | None = None
    grounding: list[GroundingReference] = Field(default_factory=list)
    chunk: GeneratedBlockChunk | None = None
    moderation: ModerationResult | None = None
    validation_issues: list[str] = Field(default_factory=list)
    response: GenerationResponse | None = None


class RemedialTriggerRequest(BaseModel):
    student_id: UUID
    target_kc_id: str
    misconception_description: str
    learner_prompt: str | None = None
    curriculum_context: list[str] = Field(default_factory=list)


class ContentWarmRequest(BaseModel):
    requests: list[GenerationRequest] = Field(default_factory=list)


class ContentWarmResult(BaseModel):
    total_requests: int = Field(default=0, ge=0)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    generation_ids: list[str] = Field(default_factory=list)
    warmed_at: datetime = Field(default_factory=utc_now)


class PredictiveWarmTask(BaseModel):
    task_id: str
    student_id: UUID
    request: GenerationRequest
    request_fingerprint: str
    status: str = "pending"
    priority_score: float = Field(default=0.0, ge=0.0)
    priority_class: str = "routine"
    attempt_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    claim_owner: str | None = None
    claim_mode: str | None = None
    claim_reason: str | None = None
    claimed_at: datetime | None = None
    stale_recovered: bool = False


class PredictiveWarmProcessRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class PredictiveWarmProcessResult(BaseModel):
    attempted_tasks: int = Field(default=0, ge=0)
    claimed_tasks: int = Field(default=0, ge=0)
    supplemental_tasks: int = Field(default=0, ge=0)
    worker_id: str | None = None
    execution_mode: str = "idle"
    targeted_tasks: int = Field(default=0, ge=0)
    autonomous_tasks: int = Field(default=0, ge=0)
    stale_recovered_tasks: int = Field(default=0, ge=0)
    completed_tasks: int = Field(default=0, ge=0)
    failed_tasks: int = Field(default=0, ge=0)
    retried_tasks: int = Field(default=0, ge=0)
    requeued_tasks: int = Field(default=0, ge=0)
    expired_tasks: int = Field(default=0, ge=0)
    deferred_tasks: int = Field(default=0, ge=0)
    dropped_tasks: int = Field(default=0, ge=0)
    skipped_tasks: int = Field(default=0, ge=0)
    pending_tasks: int = Field(default=0, ge=0)
    eligible_tasks: int = Field(default=0, ge=0)
    blocked_tasks: int = Field(default=0, ge=0)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    generation_ids: list[str] = Field(default_factory=list)
    claim_details: list["PredictiveWarmClaimDetail"] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=utc_now)


class PredictiveWarmSweepResult(BaseModel):
    requeued_tasks: int = Field(default=0, ge=0)
    expired_tasks: int = Field(default=0, ge=0)
    requeued_task_ids: list[str] = Field(default_factory=list)


class PredictiveWarmClaimDetail(BaseModel):
    task_id: str
    requested_content_type: str | None = None
    priority_class: str = "routine"
    claim_owner: str | None = None
    claim_mode: str | None = None
    claim_reason: str | None = None
    source_generation_id: str | None = None
    stale_recovered: bool = False
    wait_seconds: int = Field(default=0, ge=0)


PredictiveWarmProcessResult.model_rebuild()
