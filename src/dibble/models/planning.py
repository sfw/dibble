from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    rationale: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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
    created_at: datetime = Field(default_factory=utc_now)


class TrajectoryPlan(BaseModel):
    trajectory_id: str
    goal_id: str
    student_id: UUID
    status: str = "active"
    active_node_id: str | None = None
    active_checkpoint_id: str | None = None
    nodes: list[TrajectoryNode] = Field(default_factory=list)
    checkpoints: list[TrajectoryCheckpoint] = Field(default_factory=list)
    revisions: list[TrajectoryRevision] = Field(default_factory=list)
    rationale: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ActivePlanningState(BaseModel):
    goal: LearnerGoal | None = None
    trajectory: TrajectoryPlan | None = None
