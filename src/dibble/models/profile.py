from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from dibble.contract_labels import continue_action_display_label, stage_display_label


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SignalLevel(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class PacePreference(str, Enum):
    slower = "slower_than_average"
    average = "average"
    faster = "faster_than_average"


class ScaffoldingLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ContinueActionKind(str, Enum):
    idle = "idle"
    generate_follow_up = "generate_follow_up"
    advance_remediation = "advance_remediation"
    continue_socratic = "continue_socratic"


class ContinueActionMethod(str, Enum):
    post = "POST"


class CognitiveTraitScore(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    assessed_at: datetime = Field(default_factory=utc_now)


class AffectiveState(BaseModel):
    engagement: SignalLevel = SignalLevel.medium
    frustration: SignalLevel = SignalLevel.none
    confusion: SignalLevel = SignalLevel.low
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    inferred_at: datetime = Field(default_factory=utc_now)


class CognitiveLoadState(BaseModel):
    intrinsic_load: float = Field(default=0.3, ge=0.0, le=1.0)
    extraneous_load: float = Field(default=0.2, ge=0.0, le=1.0)
    germane_load: float = Field(default=0.4, ge=0.0, le=1.0)
    total_load: float = Field(default=0.4, ge=0.0, le=1.0)
    capacity_utilization: float = Field(default=0.4, ge=0.0, le=1.0)
    inferred_at: datetime = Field(default_factory=utc_now)


class MetacognitiveState(BaseModel):
    confidence_calibration: float = Field(default=0.5, ge=0.0, le=1.0)
    help_seeking: SignalLevel = SignalLevel.low
    help_seeking_effectiveness: float = Field(default=0.5, ge=0.0, le=1.0)
    self_monitoring: float = Field(default=0.5, ge=0.0, le=1.0)
    inferred_at: datetime = Field(default_factory=utc_now)


class LearningPreferences(BaseModel):
    modality_affinity: dict[str, float] = Field(
        default_factory=lambda: {
            "textual": 0.8,
            "interactive": 0.7,
            "visual": 0.6,
            "video": 0.5,
        }
    )
    example_domain_preferences: list[str] = Field(default_factory=list)
    scaffolding_preference: ScaffoldingLevel = ScaffoldingLevel.medium
    pace_preference: PacePreference = PacePreference.average


class KnowledgeState(BaseModel):
    lo_mastery: dict[str, float] = Field(default_factory=dict)
    kc_mastery: dict[str, float] = Field(default_factory=dict)
    kc_last_practiced: dict[str, datetime] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=utc_now)


class LearnerProfile(BaseModel):
    student_id: UUID
    grade_level: str
    profile_version: str = "2.0"
    cognitive_traits: dict[str, CognitiveTraitScore] = Field(default_factory=dict)
    knowledge_state: KnowledgeState = Field(default_factory=KnowledgeState)
    affective_state: AffectiveState = Field(default_factory=AffectiveState)
    cognitive_load: CognitiveLoadState = Field(default_factory=CognitiveLoadState)
    metacognitive_state: MetacognitiveState = Field(default_factory=MetacognitiveState)
    learning_preferences: LearningPreferences = Field(
        default_factory=LearningPreferences
    )
    accommodations: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileMetadata(BaseModel):
    student_id: UUID
    version: str
    last_updated: datetime
    completeness_score: float = Field(ge=0.0, le=1.0)


class LearnerProfileV2(BaseModel):
    profile_metadata: ProfileMetadata
    cognitive_traits: dict[str, CognitiveTraitScore] = Field(default_factory=dict)
    knowledge_state: KnowledgeState = Field(default_factory=KnowledgeState)
    affective_state: AffectiveState = Field(default_factory=AffectiveState)
    cognitive_load: CognitiveLoadState = Field(default_factory=CognitiveLoadState)
    metacognitive_state: MetacognitiveState = Field(default_factory=MetacognitiveState)
    learning_preferences: LearningPreferences = Field(
        default_factory=LearningPreferences
    )
    accommodations: list[str] = Field(default_factory=list)

    @classmethod
    def from_profile(cls, profile: "LearnerProfile") -> "LearnerProfileV2":
        signals_present = [
            bool(profile.cognitive_traits),
            bool(profile.knowledge_state.lo_mastery),
            bool(profile.knowledge_state.kc_mastery),
            bool(profile.learning_preferences.modality_affinity),
            bool(profile.learning_preferences.example_domain_preferences),
            bool(profile.accommodations),
            profile.affective_state.confidence != 0.5,
            profile.cognitive_load.total_load != 0.4,
            profile.metacognitive_state.confidence_calibration != 0.5,
            profile.metacognitive_state.help_seeking_effectiveness != 0.5,
        ]
        completeness_score = sum(1 for item in signals_present if item) / len(
            signals_present
        )

        return cls(
            profile_metadata=ProfileMetadata(
                student_id=profile.student_id,
                version=profile.profile_version,
                last_updated=profile.updated_at,
                completeness_score=round(completeness_score, 2),
            ),
            cognitive_traits=profile.cognitive_traits,
            knowledge_state=profile.knowledge_state,
            affective_state=profile.affective_state,
            cognitive_load=profile.cognitive_load,
            metacognitive_state=profile.metacognitive_state,
            learning_preferences=profile.learning_preferences,
            accommodations=profile.accommodations,
        )


class LearnerCalibrationSummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    matched_session_count: int = Field(default=0, ge=0)
    intent: str | None = None
    content_type: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class LearnerProgressSummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    matched_session_count: int = Field(default=0, ge=0)
    positive_run_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    negative_run_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    recent_average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    prior_average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    progress_delta: float = 0.0
    updated_at: datetime | None = None


class LearnerStrategySummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    support_bias: int = Field(default=0, ge=-1, le=1)
    recovery_focus: str = "monitor"
    trajectory_state: str = "insufficient"
    recommended_next_action: str = "monitor"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    matched_session_count: int = Field(default=0, ge=0)
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0
    volatility_index: float = Field(default=0.0, ge=0.0, le=1.0)
    relapse_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None
    updated_at: datetime | None = None


class SocraticConversationSummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_turn_count: int = Field(default=0, ge=0)
    matched_session_count: int = Field(default=0, ge=0)
    dominant_steering_action: str = "steady"
    dominant_prompt_style: str | None = None
    repair_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    clarification_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    transfer_readiness: float = Field(default=0.0, ge=0.0, le=1.0)
    loop_break_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None
    updated_at: datetime | None = None


class OrdinaryMasterySummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_observation_count: int = Field(default=0, ge=0)
    matched_session_count: int = Field(default=0, ge=0)
    average_observed_mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    low_support_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    high_support_dependency_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    mastery_trend: str = "stable"
    mastery_volatility: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None
    updated_at: datetime | None = None


class LearnerStateProfileSummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    matched_session_count: int = Field(default=0, ge=0)
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0
    strategy_signal: str = "insufficient"
    strategy_trajectory_state: str = "insufficient"
    engagement: SignalLevel = SignalLevel.medium
    frustration: SignalLevel = SignalLevel.none
    total_load: float = Field(default=0.4, ge=0.0, le=1.0)
    confidence_calibration: float = Field(default=0.5, ge=0.0, le=1.0)
    help_seeking: SignalLevel = SignalLevel.low
    self_monitoring: float = Field(default=0.5, ge=0.0, le=1.0)
    affective_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    load_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    recovery_stability: float = Field(default=0.0, ge=0.0, le=1.0)
    overload_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    metacognitive_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None
    updated_at: datetime | None = None


class LearnerTraitProfileSummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    matched_observation_count: int = Field(default=0, ge=0)
    matched_session_count: int = Field(default=0, ge=0)
    processing_speed: CognitiveTraitScore | None = None
    working_memory: CognitiveTraitScore | None = None
    spatial_reasoning: CognitiveTraitScore | None = None
    processing_speed_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    working_memory_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    spatial_reasoning_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_stability: float = Field(default=0.0, ge=0.0, le=1.0)
    challenge_tolerance: float = Field(default=0.0, ge=0.0, le=1.0)
    challenge_evidence_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None
    updated_at: datetime | None = None


class RecentLearnerActivity(BaseModel):
    generation_count: int = Field(default=0, ge=0)
    observation_count: int = Field(default=0, ge=0)
    socratic_assessment_count: int = Field(default=0, ge=0)
    last_learning_session_id: str | None = None
    last_generation_id: str | None = None
    last_event_at: datetime | None = None


class LearnerFlowNextStep(BaseModel):
    action: str = "monitor"
    content_type: str | None = None
    target_stage: str = "target"
    target_kc_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class LearnerContinueAction(BaseModel):
    kind: ContinueActionKind = ContinueActionKind.idle
    display_label: str | None = None
    method: ContinueActionMethod | None = None
    endpoint: str | None = None
    resource_id: str | None = None
    generation_id: str | None = None
    learning_session_id: str | None = None
    content_type: str | None = None
    target_stage: str = "target"
    target_kc_ids: list[str] = Field(default_factory=list)
    request_payload: dict[str, object] = Field(default_factory=dict)
    rationale: str | None = None

    @classmethod
    def idle(cls, *, rationale: str | None = None) -> "LearnerContinueAction":
        return cls(rationale=rationale)

    @classmethod
    def generate_follow_up(
        cls,
        *,
        endpoint: str = "/api/content/generate",
        resource_id: str | None = None,
        generation_id: str | None = None,
        learning_session_id: str | None = None,
        content_type: str | None = None,
        target_stage: str = "target",
        target_kc_ids: list[str] | None = None,
        request_payload: dict[str, object] | None = None,
        rationale: str | None = None,
    ) -> "LearnerContinueAction":
        return cls(
            kind=ContinueActionKind.generate_follow_up,
            method=ContinueActionMethod.post,
            endpoint=endpoint,
            resource_id=resource_id,
            generation_id=generation_id,
            learning_session_id=learning_session_id,
            content_type=content_type,
            target_stage=target_stage,
            target_kc_ids=list(target_kc_ids or []),
            request_payload=dict(request_payload or {}),
            rationale=rationale,
        )

    @classmethod
    def advance_remediation(
        cls,
        *,
        endpoint: str,
        resource_id: str,
        generation_id: str | None = None,
        learning_session_id: str | None = None,
        content_type: str | None = None,
        target_stage: str = "target",
        target_kc_ids: list[str] | None = None,
        request_payload: dict[str, object] | None = None,
        rationale: str | None = None,
    ) -> "LearnerContinueAction":
        return cls(
            kind=ContinueActionKind.advance_remediation,
            method=ContinueActionMethod.post,
            endpoint=endpoint,
            resource_id=resource_id,
            generation_id=generation_id,
            learning_session_id=learning_session_id,
            content_type=content_type,
            target_stage=target_stage,
            target_kc_ids=list(target_kc_ids or []),
            request_payload=dict(request_payload or {}),
            rationale=rationale,
        )

    @classmethod
    def continue_socratic(
        cls,
        *,
        endpoint: str = "/api/assessments/socratic",
        resource_id: str,
        learning_session_id: str | None = None,
        content_type: str | None = None,
        target_stage: str = "target",
        target_kc_ids: list[str] | None = None,
        request_payload: dict[str, object] | None = None,
        rationale: str | None = None,
    ) -> "LearnerContinueAction":
        return cls(
            kind=ContinueActionKind.continue_socratic,
            method=ContinueActionMethod.post,
            endpoint=endpoint,
            resource_id=resource_id,
            learning_session_id=learning_session_id,
            content_type=content_type,
            target_stage=target_stage,
            target_kc_ids=list(target_kc_ids or []),
            request_payload=dict(request_payload or {}),
            rationale=rationale,
        )

    @model_validator(mode="after")
    def _stabilize_contract(self) -> "LearnerContinueAction":
        if self.display_label is None:
            self.display_label = continue_action_display_label(self.kind.value)
        if self.kind == ContinueActionKind.idle:
            self.method = None
            self.endpoint = None
            self.resource_id = (
                None if self.resource_id in {"", None} else self.resource_id
            )
            self.request_payload = {}
            return self
        if self.method is None:
            self.method = ContinueActionMethod.post
        self.request_payload = dict(self.request_payload)
        return self


class CurriculumResourceProgressSummary(BaseModel):
    resource_id: str
    title: str
    state: str = "unknown"
    learning_objective_ids: list[str] = Field(default_factory=list)
    knowledge_component_ids: list[str] = Field(default_factory=list)
    blocked_prerequisite_kc_ids: list[str] = Field(default_factory=list)
    mastery_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    current_flow_aligned: bool = False
    target_stage: str = "target"
    mastery_quality: str | None = None
    rationale: str | None = None


class LearnerCurriculumProgressionSummary(BaseModel):
    status: str = "no_curriculum_map"
    source: str = "knowledge_state_and_flow"
    flow_type: str = "idle"
    current_stage: str = "idle"
    stage_display_label: str | None = None
    progression_action: str = "monitor"
    active_target_kc_ids: list[str] = Field(default_factory=list)
    resource_count: int = Field(default=0, ge=0)
    mastered_resource_count: int = Field(default=0, ge=0)
    ready_resource_count: int = Field(default=0, ge=0)
    blocked_resource_count: int = Field(default=0, ge=0)
    active_resource_count: int = Field(default=0, ge=0)
    mastered_resource_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    current_resource: CurriculumResourceProgressSummary | None = None
    next_resource: CurriculumResourceProgressSummary | None = None
    blocked_resources: list[CurriculumResourceProgressSummary] = Field(
        default_factory=list
    )
    ready_resources: list[CurriculumResourceProgressSummary] = Field(
        default_factory=list
    )
    rationale: str | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def _stabilize_stage_display_label(self) -> "LearnerCurriculumProgressionSummary":
        if self.stage_display_label is None:
            self.stage_display_label = stage_display_label(self.current_stage)
        return self


class LearnerFlowSummary(BaseModel):
    status: str = "idle"
    flow_type: str = "idle"
    learning_session_id: str | None = None
    remediation_session_id: str | None = None
    socratic_session_id: str | None = None
    current_phase: str = "idle"
    current_content_type: str | None = None
    last_generation_id: str | None = None
    progression_action: str = "monitor"
    target_stage: str = "target"
    active_target_kc_ids: list[str] = Field(default_factory=list)
    deferred_target_kc_ids: list[str] = Field(default_factory=list)
    transfer_target_kc_ids: list[str] = Field(default_factory=list)
    session_phase: str = "monitor"
    session_arc_action: str = "steady"
    session_stuck_loop_risk: str = "low"
    rationale: str | None = None
    progression_source: str = "insufficient"
    next_step_source: str = "insufficient"
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)
    continue_action: LearnerContinueAction = Field(
        default_factory=LearnerContinueAction
    )
    updated_at: datetime | None = None


class ProfileSummary(BaseModel):
    student_id: UUID
    grade_level: str
    profile_version: str
    kc_count: int
    lo_count: int
    engagement: SignalLevel
    frustration: SignalLevel
    total_load: float
    confidence_calibration: float
    help_seeking: SignalLevel
    calibration: LearnerCalibrationSummary = Field(
        default_factory=LearnerCalibrationSummary
    )
    progress: LearnerProgressSummary = Field(default_factory=LearnerProgressSummary)
    strategy: LearnerStrategySummary = Field(default_factory=LearnerStrategySummary)
    state_profile: LearnerStateProfileSummary = Field(
        default_factory=LearnerStateProfileSummary
    )
    trait_profile: LearnerTraitProfileSummary = Field(
        default_factory=LearnerTraitProfileSummary
    )
    recent_activity: RecentLearnerActivity = Field(
        default_factory=RecentLearnerActivity
    )
    current_flow: LearnerFlowSummary = Field(default_factory=LearnerFlowSummary)
    curriculum_progression: LearnerCurriculumProgressionSummary = Field(
        default_factory=LearnerCurriculumProgressionSummary
    )
    updated_at: datetime

    @classmethod
    def from_profile(
        cls,
        profile: LearnerProfile,
        *,
        calibration: LearnerCalibrationSummary | None = None,
        progress: LearnerProgressSummary | None = None,
        strategy: LearnerStrategySummary | None = None,
        state_profile: LearnerStateProfileSummary | None = None,
        trait_profile: LearnerTraitProfileSummary | None = None,
        recent_activity: RecentLearnerActivity | None = None,
        current_flow: LearnerFlowSummary | None = None,
        curriculum_progression: LearnerCurriculumProgressionSummary | None = None,
    ) -> "ProfileSummary":
        return cls(
            student_id=profile.student_id,
            grade_level=profile.grade_level,
            profile_version=profile.profile_version,
            kc_count=len(profile.knowledge_state.kc_mastery),
            lo_count=len(profile.knowledge_state.lo_mastery),
            engagement=profile.affective_state.engagement,
            frustration=profile.affective_state.frustration,
            total_load=profile.cognitive_load.total_load,
            confidence_calibration=profile.metacognitive_state.confidence_calibration,
            help_seeking=profile.metacognitive_state.help_seeking,
            calibration=calibration or LearnerCalibrationSummary(),
            progress=progress or LearnerProgressSummary(),
            strategy=strategy or LearnerStrategySummary(),
            state_profile=state_profile or LearnerStateProfileSummary(),
            trait_profile=trait_profile or LearnerTraitProfileSummary(),
            recent_activity=recent_activity or RecentLearnerActivity(),
            current_flow=current_flow or LearnerFlowSummary(),
            curriculum_progression=curriculum_progression
            or LearnerCurriculumProgressionSummary(),
            updated_at=profile.updated_at,
        )
