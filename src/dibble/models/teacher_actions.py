from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep


class TeacherInterventionProposalStatus(str, Enum):
    unavailable = "unavailable"
    available = "available"


class TeacherInterventionDecision(str, Enum):
    approve = "approve"
    select_option = "select_option"
    defer = "defer"
    escalate_human = "escalate_human"


class TeacherInterventionDecisionStatus(str, Enum):
    approved = "approved"
    option_selected = "option_selected"
    deferred = "deferred"
    escalated_human = "escalated_human"


class TeacherInterventionDecisionRequest(BaseModel):
    decision: str
    option_id: str | None = None
    note: str | None = None


class TeacherInterventionOption(BaseModel):
    option_id: str
    label: str
    rationale: str | None = None
    is_recommended: bool = False
    continue_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)


class TeacherInterventionDecisionRecord(BaseModel):
    action_key: str
    decision_id: str
    decision: TeacherInterventionDecision
    status: TeacherInterventionDecisionStatus
    selected_option_id: str | None = None
    note: str | None = None
    decided_by: str | None = None
    decided_role: str | None = None
    decided_at: datetime
    execution_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)


class TeacherInterventionActionContract(BaseModel):
    action_key: str = "idle"
    proposal_status: TeacherInterventionProposalStatus = TeacherInterventionProposalStatus.unavailable
    flow_type: str = "idle"
    learning_session_id: str | None = None
    remediation_session_id: str | None = None
    socratic_session_id: str | None = None
    progression_action: str = "monitor"
    target_stage: str = "target"
    active_target_kc_ids: list[str] = Field(default_factory=list)
    current_phase: str = "idle"
    rationale: str | None = None
    source: str = "learner_flow"
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)
    proposed_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)
    available_options: list[TeacherInterventionOption] = Field(default_factory=list)
    allowed_decisions: list[TeacherInterventionDecision] = Field(default_factory=list)
    latest_decision: TeacherInterventionDecisionRecord | None = None
    updated_at: datetime | None = None
