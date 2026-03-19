from __future__ import annotations

from pydantic import BaseModel, Field


class AdminSectionMembershipUserSummary(BaseModel):
    user_id: str
    display_name: str | None = None


class AdminSectionMembershipSummary(BaseModel):
    classroom_id: str
    teachers: list[AdminSectionMembershipUserSummary] = Field(default_factory=list)
    learners: list[AdminSectionMembershipUserSummary] = Field(default_factory=list)


class AdminSectionMembershipUpdateRequest(BaseModel):
    teacher_user_ids: list[str] = Field(default_factory=list)
    learner_user_ids: list[str] = Field(default_factory=list)
