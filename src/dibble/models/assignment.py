from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AssignmentStatus(str, Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    canceled = "canceled"


class Assignment(BaseModel):
    """A teacher-created learning assignment for a specific learner."""

    assignment_id: str
    student_id: str
    teacher_id: str
    section_id: str | None = None
    title: str
    description: str = ""
    status: AssignmentStatus = AssignmentStatus.assigned

    # What the learner should work on — at least one of these should be set
    target_resource_id: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)

    # Optional scheduling
    due_at: datetime | None = None

    # Lifecycle timestamps
    created_at: datetime = Field(default_factory=_utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=_utc_now)


class AssignmentCreate(BaseModel):
    """Payload for creating a new assignment."""

    student_id: str
    section_id: str | None = None
    title: str
    description: str = ""
    target_resource_id: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    due_at: datetime | None = None


class AssignmentUpdate(BaseModel):
    """Payload for updating an assignment's status."""

    status: AssignmentStatus


class AssignmentPage(BaseModel):
    """Paginated assignment list."""

    items: list[Assignment]
    offset: int
    limit: int
    has_more: bool
