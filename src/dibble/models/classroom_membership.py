from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClassroomMembershipRole(str, Enum):
    teacher = "teacher"
    learner = "learner"


class ClassroomMembershipUpsert(BaseModel):
    classroom_id: str
    user_id: str
    role: ClassroomMembershipRole


class ClassroomMembership(ClassroomMembershipUpsert):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
