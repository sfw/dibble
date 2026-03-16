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
    score: float = Field(ge=0.0)
    matched_terms: list[str] = Field(default_factory=list)


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
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_error: str | None = None


class PredictiveWarmProcessRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class PredictiveWarmProcessResult(BaseModel):
    attempted_tasks: int = Field(default=0, ge=0)
    completed_tasks: int = Field(default=0, ge=0)
    failed_tasks: int = Field(default=0, ge=0)
    skipped_tasks: int = Field(default=0, ge=0)
    pending_tasks: int = Field(default=0, ge=0)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    generation_ids: list[str] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=utc_now)
