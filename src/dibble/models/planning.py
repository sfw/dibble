from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from dibble.models.curriculum import CurriculumVersionReference


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlanningEvidenceStrength(str, Enum):
    weak = "weak"
    emerging = "emerging"
    strong = "strong"


class PlanningSignalKind(str, Enum):
    session_effectiveness = "session_effectiveness"
    concept_cluster = "concept_cluster"
    recovery_pattern = "recovery_pattern"
    content_type_effectiveness = "content_type_effectiveness"
    phase_effectiveness = "phase_effectiveness"
    modality_effectiveness = "modality_effectiveness"


class TrajectoryRiskLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class TrajectoryRevisionActionType(str, Enum):
    increase_revisit_density = "increase_revisit_density"
    slow_pacing = "slow_pacing"
    insert_recovery_scaffold = "insert_recovery_scaffold"
    strengthen_scaffolding = "strengthen_scaffolding"
    alternative_ordering = "alternative_ordering"


class PlanningAdaptationSignal(BaseModel):
    signal_id: str
    kind: PlanningSignalKind
    evidence_strength: PlanningEvidenceStrength = PlanningEvidenceStrength.weak
    direction: str = "mixed"
    sample_count: int = Field(default=0, ge=0)
    average_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    success_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    progress_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    cluster_key: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    intent: str | None = None
    content_type: str | None = None
    phase: str | None = None
    modality: str | None = None
    rationale: str | None = None
    observed_at: datetime = Field(default_factory=utc_now)


class PlanningEffectivenessProfile(BaseModel):
    dimension_type: str
    dimension_key: str
    label: str
    evidence_strength: PlanningEvidenceStrength = PlanningEvidenceStrength.weak
    sample_count: int = Field(default=0, ge=0)
    average_outcome_score: float = Field(default=0.5, ge=0.0, le=1.0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    recovery_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    intent: str | None = None
    content_type: str | None = None
    phase: str | None = None
    modality: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class PlanningRecoveryPattern(BaseModel):
    pattern_key: str
    label: str
    evidence_strength: PlanningEvidenceStrength = PlanningEvidenceStrength.weak
    sample_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_outcome_score: float = Field(default=0.5, ge=0.0, le=1.0)
    cluster_key: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    intent: str | None = None
    content_type: str | None = None
    phase: str | None = None
    modality: str | None = None
    prompt_variant: str | None = None
    rationale: str | None = None
    last_observed_at: datetime | None = None


class PlanningModalityPreferenceEntry(BaseModel):
    preference_key: str
    context_label: str
    preferred_modality: str
    evidence_strength: PlanningEvidenceStrength = PlanningEvidenceStrength.weak
    sample_count: int = Field(default=0, ge=0)
    average_outcome_score: float = Field(default=0.5, ge=0.0, le=1.0)
    positive_outcome_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    recovery_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    source_context_keys: list[str] = Field(default_factory=list)
    rationale: str | None = None
    last_observed_at: datetime | None = None


class PlanningModalityPreferenceSummary(BaseModel):
    global_preferred_modality: str | None = None
    preferred_by_content_family: list[PlanningModalityPreferenceEntry] = Field(
        default_factory=list
    )
    preferred_by_risk_bucket: list[PlanningModalityPreferenceEntry] = Field(
        default_factory=list
    )
    preferred_by_recovery_pattern: list[PlanningModalityPreferenceEntry] = Field(
        default_factory=list
    )
    rationale: str | None = None


class PlanningConceptClusterMarker(BaseModel):
    cluster_key: str
    label: str
    target_kc_ids: list[str] = Field(default_factory=list)
    evidence_strength: PlanningEvidenceStrength = PlanningEvidenceStrength.weak
    risk_level: TrajectoryRiskLevel = TrajectoryRiskLevel.low
    sample_count: int = Field(default=0, ge=0)
    stall_count: int = Field(default=0, ge=0)
    recovery_success_count: int = Field(default=0, ge=0)
    average_outcome_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recent_trend: float = Field(default=0.0, ge=-1.0, le=1.0)
    preferred_recovery_pattern: str | None = None
    preferred_modality: str | None = None
    rationale: str | None = None
    last_observed_at: datetime | None = None


class TrajectoryRevisionAdjustment(BaseModel):
    action_type: TrajectoryRevisionActionType
    evidence_strength: PlanningEvidenceStrength = PlanningEvidenceStrength.weak
    cluster_key: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    value: str
    rationale: str


class TrajectoryRevisionReason(BaseModel):
    reason_code: str
    signal_kind: PlanningSignalKind
    evidence_strength: PlanningEvidenceStrength = PlanningEvidenceStrength.weak
    cluster_key: str | None = None
    rationale: str


class TrajectoryNodeAdaptation(BaseModel):
    risk_level: TrajectoryRiskLevel = TrajectoryRiskLevel.low
    pacing_adjustment: str = "standard"
    revisit_priority: str = "normal"
    recommended_scaffolding_pattern: str | None = None
    recommended_modality: str | None = None
    signal_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class PlanningAdaptationState(BaseModel):
    revision_count: int = Field(default=0, ge=0)
    active_pacing_adjustment: str = "standard"
    active_revisit_density: int = Field(default=1, ge=1, le=3)
    preferred_scaffolding_pattern: str | None = None
    preferred_modality: str | None = None
    modality_preferences: PlanningModalityPreferenceSummary = Field(
        default_factory=PlanningModalityPreferenceSummary
    )
    recent_signals: list[PlanningAdaptationSignal] = Field(default_factory=list)
    concept_cluster_markers: list[PlanningConceptClusterMarker] = Field(
        default_factory=list
    )
    recovery_patterns: list[PlanningRecoveryPattern] = Field(default_factory=list)
    effectiveness_profiles: list[PlanningEffectivenessProfile] = Field(
        default_factory=list
    )
    active_adjustments: list[TrajectoryRevisionAdjustment] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class LearnerGoal(BaseModel):
    goal_id: str
    student_id: UUID
    title: str
    source: str = "system_inferred"
    status: str = "active"
    target_outcome_id: str | None = None
    target_outcome_ids: list[str] = Field(default_factory=list)
    target_kc_ids: list[str] = Field(default_factory=list)
    active_trajectory_id: str | None = None
    curriculum_provenance: CurriculumVersionReference | None = None
    rationale: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LearnerGoalCreateRequest(BaseModel):
    title: str | None = None
    target_outcome_id: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class TrajectoryNode(BaseModel):
    node_id: str
    node_kind: str = "instruction"
    title: str
    outcome_id: str | None = None
    status: str = "planned"
    sequence_index: int = Field(default=0, ge=0)
    target_stage: str = "target"
    sequence_action: str = "stay_on_requested_target"
    target_kc_ids: list[str] = Field(default_factory=list)
    ordered_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    bridge_kc_ids: list[str] = Field(default_factory=list)
    deferred_target_kc_ids: list[str] = Field(default_factory=list)
    transfer_target_kc_ids: list[str] = Field(default_factory=list)
    expected_session_count: int = Field(default=1, ge=1)
    checkpoint_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None
    adaptation: TrajectoryNodeAdaptation | None = None


class TrajectoryCheckpoint(BaseModel):
    checkpoint_id: str
    trajectory_id: str
    node_id: str
    label: str
    status: str = "planned"
    expected_after_session_count: int = Field(default=1, ge=1)
    mastery_focus_kc_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class TrajectoryRevision(BaseModel):
    revision_id: str
    revision_number: int = Field(default=1, ge=1)
    revision_kind: str = "created"
    rationale: str | None = None
    previous_active_node_id: str | None = None
    active_node_id: str | None = None
    node_count: int = Field(default=0, ge=0)
    reasons: list[TrajectoryRevisionReason] = Field(default_factory=list)
    adjustments: list[TrajectoryRevisionAdjustment] = Field(default_factory=list)
    observed_signals: list[PlanningAdaptationSignal] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class TrajectoryPlan(BaseModel):
    trajectory_id: str
    goal_id: str
    student_id: UUID
    status: str = "active"
    active_node_id: str | None = None
    active_checkpoint_id: str | None = None
    curriculum_provenance: CurriculumVersionReference | None = None
    nodes: list[TrajectoryNode] = Field(default_factory=list)
    checkpoints: list[TrajectoryCheckpoint] = Field(default_factory=list)
    revisions: list[TrajectoryRevision] = Field(default_factory=list)
    adaptation_state: PlanningAdaptationState | None = None
    rationale: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ActivePlanningState(BaseModel):
    goal: LearnerGoal | None = None
    trajectory: TrajectoryPlan | None = None
