from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep

MAX_HISTORY_LIMIT = 100


class LearnerGenerationHistoryEntry(BaseModel):
    generation_id: str
    learning_session_id: str | None = None
    source_generation_id: str | None = None
    content_type: str
    flow_type: str = "lesson"
    status: str = "delivered"
    delivered_phase: str = "target"
    progression_action: str = "stay_on_requested_target"
    target_stage: str = "target"
    active_target_kc_ids: list[str] = Field(default_factory=list)
    intervention_type: str | None = None
    rationale: str | None = None
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)
    continue_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)
    created_at: datetime


class LearnerSocraticSessionHistoryEntry(BaseModel):
    session_id: str
    learning_session_id: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    status: str = "idle"
    turn_count: int = Field(default=0, ge=0)
    latest_prompt_style: str | None = None
    latest_steering_action: str = "steady"
    latest_next_action: str = "monitor"
    latest_evidence_strength: str = "insufficient"
    rationale: str | None = None
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)
    continue_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)
    created_at: datetime
    updated_at: datetime


class LearnerRemediationSessionHistoryEntry(BaseModel):
    session_id: str
    target_kc_id: str
    focus_kc_ids: list[str] = Field(default_factory=list)
    prerequisite_kc_ids: list[str] = Field(default_factory=list)
    latest_generation_id: str | None = None
    status: str = "in_progress"
    current_phase: str | None = None
    completed_step_count: int = Field(default=0, ge=0)
    step_count: int = Field(default=0, ge=0)
    progression_decision: str = "advance"
    progression_rationale: str | None = None
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)
    continue_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)
    created_at: datetime
    updated_at: datetime


class LearnerGenerationHistoryPage(BaseModel):
    items: list[LearnerGenerationHistoryEntry]
    offset: int
    limit: int
    has_more: bool


class LearnerSocraticSessionHistoryPage(BaseModel):
    items: list[LearnerSocraticSessionHistoryEntry]
    offset: int
    limit: int
    has_more: bool


class LearnerRemediationSessionHistoryPage(BaseModel):
    items: list[LearnerRemediationSessionHistoryEntry]
    offset: int
    limit: int
    has_more: bool
