from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RolloutCapability(str, Enum):
    autonomous_session_suggestions = "autonomous_session_suggestions"
    parent_approval_enforcement = "parent_approval_enforcement"
    cloud_library_remote_read = "cloud_library_remote_read"
    cloud_library_remote_publish = "cloud_library_remote_publish"
    non_text_modalities = "non_text_modalities"
    outcome_driven_adaptation = "outcome_driven_adaptation"
    migration_execution = "migration_execution"
    autonomous_teacher_outbound_actions = "autonomous_teacher_outbound_actions"


class AssignmentUnit(str, Enum):
    learner = "learner"
    household = "household"


class AutonomousSessionSuggestionMode(str, Enum):
    disabled = "disabled"
    guided = "guided"


class ParentApprovalEnforcementMode(str, Enum):
    disabled = "disabled"
    guided = "guided"
    strict = "strict"


class CloudLibraryReadMode(str, Enum):
    local_only = "local_only"
    remote_preferred = "remote_preferred"


class CloudLibraryPublishMode(str, Enum):
    local_only = "local_only"
    remote_verified = "remote_verified"


class ModalityAvailabilityMode(str, Enum):
    text_only = "text_only"
    full_multimodal = "full_multimodal"


class AdaptationStrength(str, Enum):
    off = "off"
    conservative = "conservative"
    standard = "standard"
    aggressive = "aggressive"


class MigrationExecutionMode(str, Enum):
    manual_only = "manual_only"
    approved_low_risk_only = "approved_low_risk_only"


class AutonomousOutboundMode(str, Enum):
    disabled = "disabled"
    notifications_only = "notifications_only"


class _BaseBehaviorGate(BaseModel):
    capability: RolloutCapability
    fallback_behavior: str
    description: str | None = None

    def enabled(self) -> bool:
        raise NotImplementedError

    def mode_value(self) -> str:
        raise NotImplementedError


class AutonomousSessionSuggestionGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.autonomous_session_suggestions] = (
        RolloutCapability.autonomous_session_suggestions
    )
    mode: AutonomousSessionSuggestionMode = AutonomousSessionSuggestionMode.guided

    def enabled(self) -> bool:
        return self.mode != AutonomousSessionSuggestionMode.disabled

    def mode_value(self) -> str:
        return self.mode.value


class ParentApprovalGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.parent_approval_enforcement] = (
        RolloutCapability.parent_approval_enforcement
    )
    mode: ParentApprovalEnforcementMode = ParentApprovalEnforcementMode.guided

    def enabled(self) -> bool:
        return self.mode != ParentApprovalEnforcementMode.disabled

    def mode_value(self) -> str:
        return self.mode.value


class CloudLibraryReadGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.cloud_library_remote_read] = (
        RolloutCapability.cloud_library_remote_read
    )
    mode: CloudLibraryReadMode = CloudLibraryReadMode.local_only

    def enabled(self) -> bool:
        return self.mode == CloudLibraryReadMode.remote_preferred

    def mode_value(self) -> str:
        return self.mode.value


class CloudLibraryPublishGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.cloud_library_remote_publish] = (
        RolloutCapability.cloud_library_remote_publish
    )
    mode: CloudLibraryPublishMode = CloudLibraryPublishMode.local_only

    def enabled(self) -> bool:
        return self.mode == CloudLibraryPublishMode.remote_verified

    def mode_value(self) -> str:
        return self.mode.value


class NonTextModalityGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.non_text_modalities] = (
        RolloutCapability.non_text_modalities
    )
    mode: ModalityAvailabilityMode = ModalityAvailabilityMode.full_multimodal

    def enabled(self) -> bool:
        return self.mode == ModalityAvailabilityMode.full_multimodal

    def mode_value(self) -> str:
        return self.mode.value


class OutcomeDrivenAdaptationGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.outcome_driven_adaptation] = (
        RolloutCapability.outcome_driven_adaptation
    )
    mode: AdaptationStrength = AdaptationStrength.conservative

    def enabled(self) -> bool:
        return self.mode != AdaptationStrength.off

    def mode_value(self) -> str:
        return self.mode.value


class MigrationExecutionGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.migration_execution] = (
        RolloutCapability.migration_execution
    )
    mode: MigrationExecutionMode = MigrationExecutionMode.manual_only

    def enabled(self) -> bool:
        return self.mode == MigrationExecutionMode.approved_low_risk_only

    def mode_value(self) -> str:
        return self.mode.value


class AutonomousOutboundGate(_BaseBehaviorGate):
    capability: Literal[RolloutCapability.autonomous_teacher_outbound_actions] = (
        RolloutCapability.autonomous_teacher_outbound_actions
    )
    mode: AutonomousOutboundMode = AutonomousOutboundMode.notifications_only

    def enabled(self) -> bool:
        return self.mode != AutonomousOutboundMode.disabled

    def mode_value(self) -> str:
        return self.mode.value


BehaviorGate = Annotated[
    AutonomousSessionSuggestionGate
    | ParentApprovalGate
    | CloudLibraryReadGate
    | CloudLibraryPublishGate
    | NonTextModalityGate
    | OutcomeDrivenAdaptationGate
    | MigrationExecutionGate
    | AutonomousOutboundGate,
    Field(discriminator="capability"),
]


class RolloutCohort(BaseModel):
    cohort_id: str
    label: str
    description: str | None = None
    assignment_unit: AssignmentUnit = AssignmentUnit.learner
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    learner_ids: list[str] = Field(default_factory=list)
    household_ids: list[str] = Field(default_factory=list)
    pinned_evaluation_bucket_id: str | None = None
    behavior_overrides: list[BehaviorGate] = Field(default_factory=list)


class EvaluationBucket(BaseModel):
    bucket_id: str
    label: str
    description: str | None = None
    weight: int = Field(default=0, ge=0, le=100)
    dimensions: dict[str, str] = Field(default_factory=dict)
    behavior_overrides: list[BehaviorGate] = Field(default_factory=list)


class KillSwitchState(BaseModel):
    capability: RolloutCapability
    active: bool = False
    reason: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class RolloutPolicy(BaseModel):
    policy_id: str = "default"
    label: str = "Controlled rollout"
    description: str = (
        "Conservative rollout policy with deterministic cohorts, evaluation buckets, "
        "and operator kill switches."
    )
    assignment_salt: str = "dibble-rollout-v1"
    behavior_gates: list[BehaviorGate] = Field(default_factory=list)
    cohorts: list[RolloutCohort] = Field(default_factory=list)
    evaluation_buckets: list[EvaluationBucket] = Field(default_factory=list)
    kill_switches: list[KillSwitchState] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_shape(self) -> "RolloutPolicy":
        _ensure_unique_gate_capabilities(self.behavior_gates)
        for cohort in self.cohorts:
            _ensure_unique_gate_capabilities(cohort.behavior_overrides)
        for bucket in self.evaluation_buckets:
            _ensure_unique_gate_capabilities(bucket.behavior_overrides)
        return self


class RolloutSubject(BaseModel):
    learner_id: str | None = None
    household_id: str | None = None

    def assignment_key(
        self,
        *,
        unit: AssignmentUnit,
    ) -> str | None:
        if unit == AssignmentUnit.household:
            return self.household_id
        return self.learner_id or self.household_id


class RolloutCapabilityDecision(BaseModel):
    capability: RolloutCapability
    enabled: bool
    mode: str
    fallback_behavior: str
    effective_gate: BehaviorGate
    source: str
    source_cohort_ids: list[str] = Field(default_factory=list)
    evaluation_bucket_id: str | None = None
    kill_switch_active: bool = False
    kill_switch_reason: str | None = None
    rationale: list[str] = Field(default_factory=list)


class RolloutInspection(BaseModel):
    policy_id: str
    subject: RolloutSubject
    cohort_ids: list[str] = Field(default_factory=list)
    evaluation_bucket: EvaluationBucket | None = None
    decisions: list[RolloutCapabilityDecision] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    def decision_for(
        self, capability: RolloutCapability
    ) -> RolloutCapabilityDecision | None:
        return next(
            (decision for decision in self.decisions if decision.capability == capability),
            None,
        )


class RolloutPolicyResponse(BaseModel):
    policy: RolloutPolicy


class RolloutPolicyUpdateRequest(BaseModel):
    policy: RolloutPolicy


class EvaluationBucketSummary(BaseModel):
    bucket_id: str
    label: str
    dimensions: dict[str, str] = Field(default_factory=dict)
    sample_count: int = Field(default=0, ge=0)
    learner_count: int = Field(default=0, ge=0)
    positive_run_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_run_outcome_score: float = Field(default=0.0, ge=0.0, le=1.0)
    average_observation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    average_assessment_score: float = Field(default=0.0, ge=0.0, le=1.0)
    modality_counts: dict[str, int] = Field(default_factory=dict)


class EvaluationSummaryResponse(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    total_samples: int = Field(default=0, ge=0)
    buckets: list[EvaluationBucketSummary] = Field(default_factory=list)


def default_rollout_policy() -> RolloutPolicy:
    return RolloutPolicy(
        behavior_gates=[
            AutonomousSessionSuggestionGate(
                fallback_behavior="no_session_suggestion",
                description="Autonomous session suggestions follow guided household policy.",
                mode=AutonomousSessionSuggestionMode.guided,
            ),
            ParentApprovalGate(
                fallback_behavior="household_preferences",
                description="Parent approval remains enabled and can be forced stricter by policy.",
                mode=ParentApprovalEnforcementMode.guided,
            ),
            CloudLibraryReadGate(
                fallback_behavior="local_library_only",
                description="Remote cloud-library reads stay off until explicitly rolled out.",
                mode=CloudLibraryReadMode.local_only,
            ),
            CloudLibraryPublishGate(
                fallback_behavior="local_only_hold",
                description="Remote cloud-library publication stays off until explicitly rolled out.",
                mode=CloudLibraryPublishMode.local_only,
            ),
            NonTextModalityGate(
                fallback_behavior="text_only_fallback",
                description="Non-text modalities can be rolled out gradually.",
                mode=ModalityAvailabilityMode.full_multimodal,
            ),
            OutcomeDrivenAdaptationGate(
                fallback_behavior="observe_only",
                description="Outcome-driven adaptation starts conservative.",
                mode=AdaptationStrength.conservative,
            ),
            MigrationExecutionGate(
                fallback_behavior="manual_review_required",
                description="Automatic curriculum migration execution remains disabled by default.",
                mode=MigrationExecutionMode.manual_only,
            ),
            AutonomousOutboundGate(
                fallback_behavior="no_outbound_actions",
                description="Only in-product notifications are allowed by default.",
                mode=AutonomousOutboundMode.notifications_only,
            ),
        ],
        evaluation_buckets=[
            EvaluationBucket(
                bucket_id="baseline_controlled",
                label="Baseline Controlled",
                description="Conservative baseline with local-only library access and attenuated adaptation.",
                weight=100,
                dimensions={
                    "modality_mode": ModalityAvailabilityMode.full_multimodal.value,
                    "cloud_mode": CloudLibraryReadMode.local_only.value,
                    "adaptation_strength": AdaptationStrength.conservative.value,
                    "autonomy_mode": AutonomousSessionSuggestionMode.guided.value,
                },
            )
        ],
    )


def stable_rollout_percent(
    *,
    salt: str,
    scope: str,
    assignment_key: str,
) -> int:
    digest = sha256(f"{salt}:{scope}:{assignment_key}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _ensure_unique_gate_capabilities(gates: list[BehaviorGate]) -> None:
    seen: set[RolloutCapability] = set()
    for gate in gates:
        if gate.capability in seen:
            msg = f"Duplicate rollout gate for capability {gate.capability.value}."
            raise ValueError(msg)
        seen.add(gate.capability)
