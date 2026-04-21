from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field

from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionControlState(BaseModel):
    learning_session_id: str
    student_id: UUID
    goal_id: str | None = None
    trajectory_id: str | None = None
    trajectory_node_id: str | None = None
    trajectory_checkpoint_id: str | None = None
    flow_type: str = "lesson"
    status: str = "idle"
    phase: str = "target"
    current_content_type: str | None = None
    current_generation_id: str | None = None
    progression_action: str = "stay_on_requested_target"
    progression_source: str = "trajectory"
    target_stage: str = "target"
    active_target_kc_ids: list[str] = Field(default_factory=list)
    deferred_target_kc_ids: list[str] = Field(default_factory=list)
    transfer_target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    session_phase: str = "monitor"
    session_arc_action: str = "steady"
    session_stuck_loop_risk: str = "low"
    artifact_kind: str = "idle"
    resource_id: str | None = None
    remediation_session_id: str | None = None
    socratic_session_id: str | None = None
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)
    continue_action: LearnerContinueAction = Field(
        default_factory=LearnerContinueAction
    )
    rationale: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
