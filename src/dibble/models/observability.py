from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from dibble.models.generation import AdaptiveScoreComponent, ModalityRoutingInspection
from dibble.models.household import AutonomousTeacherDecisionFactor
from dibble.models.rollout import KillSwitchState
from dibble.models.telemetry import ProviderStatusSnapshot


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HarnessBoundary(str, Enum):
    content_generation = "content_generation"
    content_library = "content_library"
    within_session_control = "within_session_control"
    autonomous_teacher = "autonomous_teacher"
    curriculum_evolution = "curriculum_evolution"
    rollout_control = "rollout_control"


class OperationalTraceStatus(str, Enum):
    success = "success"
    degraded = "degraded"
    failed = "failed"
    recovered = "recovered"


class OperationalTrace(BaseModel):
    trace_id: str
    harness: HarnessBoundary
    operation: str
    status: OperationalTraceStatus
    summary: str
    request_id: str | None = None
    session_id: str | None = None
    student_id: str | None = None
    household_id: str | None = None
    entity_kind: str | None = None
    entity_id: str | None = None
    degraded_mode: bool = False
    degraded_reason: str | None = None
    fallback_kind: str | None = None
    fallback_provenance: str | None = None
    reason_code: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class HarnessFallbackCount(BaseModel):
    harness: HarnessBoundary
    fallback_kind: str
    count: int = Field(default=0, ge=0)


class PendingReviewQueue(BaseModel):
    queue_key: str
    count: int = Field(default=0, ge=0)
    summary: str


class StuckMigrationPlanDiagnostic(BaseModel):
    plan_id: str
    status: str
    approved_action_count: int = Field(default=0, ge=0)
    failed_action_count: int = Field(default=0, ge=0)
    review_item_count: int = Field(default=0, ge=0)
    updated_at: datetime


class StaleAutonomousSuggestionDiagnostic(BaseModel):
    household_id: str
    learner_id: str
    status: str
    pending_approval_count: int = Field(default=0, ge=0)
    updated_at: datetime
    hours_stale: int = Field(default=0, ge=0)


class CloudLibraryReadiness(BaseModel):
    remote_enabled: bool = False
    degraded: bool = False
    recent_lookup_failures: int = Field(default=0, ge=0)
    recent_publish_failures: int = Field(default=0, ge=0)
    remote_endpoint: str | None = None
    last_degraded_at: datetime | None = None
    last_degraded_reason: str | None = None


class DecisionConfidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DecisionRisk(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class RolloutEffectExplanation(BaseModel):
    capability: str
    enabled: bool
    mode: str
    source: str
    fallback_behavior: str
    constrained: bool = False
    detail: str | None = None


class ModalityDecisionExplanationBundle(BaseModel):
    learner_id: str
    summary: str
    inspection: ModalityRoutingInspection
    selected_score_components: list[AdaptiveScoreComponent] = Field(default_factory=list)
    rollout_effect: RolloutEffectExplanation | None = None
    fallback_behavior: str | None = None
    confidence: DecisionConfidence = DecisionConfidence.medium
    risk: DecisionRisk = DecisionRisk.low
    next_expected_consequence: str
    generated_at: datetime = Field(default_factory=utc_now)


class AutonomousTeacherExplanationBundle(BaseModel):
    household_id: str
    learner_id: str
    summary: str
    cadence_decision: str
    suggested_modality: str | None = None
    blocking_approval_types: list[str] = Field(default_factory=list)
    factors: list[AutonomousTeacherDecisionFactor] = Field(default_factory=list)
    rollout_effects: list[RolloutEffectExplanation] = Field(default_factory=list)
    fallback_behavior: str | None = None
    confidence: DecisionConfidence = DecisionConfidence.medium
    risk: DecisionRisk = DecisionRisk.low
    next_expected_consequence: str
    generated_at: datetime = Field(default_factory=utc_now)


class BlockedReviewPreview(BaseModel):
    item_kind: str
    item_id: str
    summary: str
    explanation: str
    next_step: str
    risk_level: str = "medium"
    household_id: str | None = None
    learner_id: str | None = None


class ReleaseReadinessSnapshot(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    total_recent_traces: int = Field(default=0, ge=0)
    degraded_trace_count: int = Field(default=0, ge=0)
    provider_statuses: list[ProviderStatusSnapshot] = Field(default_factory=list)
    fallback_counts: list[HarnessFallbackCount] = Field(default_factory=list)
    pending_review_queues: list[PendingReviewQueue] = Field(default_factory=list)
    stuck_migration_plans: list[StuckMigrationPlanDiagnostic] = Field(
        default_factory=list
    )
    stale_autonomous_suggestions: list[StaleAutonomousSuggestionDiagnostic] = Field(
        default_factory=list
    )
    cloud_library: CloudLibraryReadiness = Field(
        default_factory=CloudLibraryReadiness
    )
    active_kill_switches: list[KillSwitchState] = Field(default_factory=list)
    recent_degraded_operations: list[OperationalTrace] = Field(default_factory=list)
    blocked_review_previews: list[BlockedReviewPreview] = Field(default_factory=list)
