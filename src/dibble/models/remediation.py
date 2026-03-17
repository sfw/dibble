from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field

from dibble.models.generation import GeneratedContent, RequestedContentType
from dibble.models.profile import LearnerFlowNextStep, LearnerStrategySummary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RemediationWorkflowStep(BaseModel):
    phase: str
    title: str
    target_kc_ids: list[str] = Field(default_factory=list)
    support_level: str
    objective: str
    guidance: str
    misconception_ids: list[str] = Field(default_factory=list)
    recommended_content_type: RequestedContentType
    status: str = "pending"
    generated_content_id: str | None = None


class RemediationWorkflowSummary(BaseModel):
    status: str = "in_progress"
    current_phase: str | None = None
    current_step_title: str | None = None
    current_step_target_kc_ids: list[str] = Field(default_factory=list)
    next_phase: str | None = None
    completed_step_count: int = Field(default=0, ge=0)
    step_count: int = Field(default=0, ge=0)
    progression_decision: str = "advance"
    progression_rationale: str | None = None
    progression_target_kc_ids: list[str] = Field(default_factory=list)
    progression_evidence_observation_count: int = Field(default=0, ge=0)
    progression_evidence_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    progression_average_observed_mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    progression_low_support_success_count: int = Field(default=0, ge=0)
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)


class KcSequenceSummary(BaseModel):
    action: str = "monitor"
    primary_kc_id: str | None = None
    ordered_kc_ids: list[str] = Field(default_factory=list)
    bridge_kc_ids: list[str] = Field(default_factory=list)
    deferred_kc_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class RemediationWorkflowSession(BaseModel):
    session_id: str
    student_id: UUID
    target_kc_id: str
    focus_kc_ids: list[str] = Field(default_factory=list)
    prerequisite_kc_ids: list[str] = Field(default_factory=list)
    misconception_description: str
    curriculum_context: list[str] = Field(default_factory=list)
    rationale: str
    blueprint: dict[str, object] = Field(default_factory=dict)
    strategy_summary: LearnerStrategySummary = Field(default_factory=LearnerStrategySummary)
    kc_sequence: KcSequenceSummary = Field(default_factory=KcSequenceSummary)
    steps: list[RemediationWorkflowStep] = Field(default_factory=list)
    current_step_index: int | None = None
    completed_generation_ids: list[str] = Field(default_factory=list)
    progression_decision: str = "advance"
    progression_rationale: str | None = None
    progression_target_kc_ids: list[str] = Field(default_factory=list)
    progression_evidence_observation_count: int = Field(default=0, ge=0)
    progression_evidence_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    progression_average_observed_mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    progression_low_support_success_count: int = Field(default=0, ge=0)
    summary: RemediationWorkflowSummary = Field(default_factory=RemediationWorkflowSummary)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RemediationWorkflowAdvanceRequest(BaseModel):
    learner_prompt: str | None = None
    curriculum_context: list[str] = Field(default_factory=list)


class RemediationWorkflowAdvanceResponse(BaseModel):
    session: RemediationWorkflowSession
    content: GeneratedContent
    executed_phase: str
