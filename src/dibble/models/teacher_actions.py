from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep


class TeacherInterventionDecisionRequest(BaseModel):
    decision: str
    note: str | None = None


class TeacherInterventionDecisionRecord(BaseModel):
    action_key: str
    decision_id: str
    decision: str
    status: str
    note: str | None = None
    decided_by: str | None = None
    decided_role: str | None = None
    decided_at: datetime
    execution_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)


class TeacherInterventionActionContract(BaseModel):
    action_key: str = "idle"
    proposal_status: str = "unavailable"
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
    allowed_decisions: list[str] = Field(default_factory=list)
    latest_decision: TeacherInterventionDecisionRecord | None = None
    updated_at: datetime | None = None
