from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuardianInvite(BaseModel):
    code: str
    family_name: str | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    used_by_user_id: str | None = None
    used_at: datetime | None = None

    @property
    def used(self) -> bool:
        return self.used_by_user_id is not None


class GuardianInviteCreateRequest(BaseModel):
    family_name: str | None = None


class GuardianRegisterRequest(BaseModel):
    invite_code: str
    display_name: str
    course_id: str | None = None


class GuardianRegisterResponse(BaseModel):
    user_id: str
    credential: str
    role: str = "guardian"
    display_name: str
    family_section_id: str


class FamilyLearnerCreateRequest(BaseModel):
    display_name: str
    grade_level: str
    # Only honored when auth is disabled (local development); with auth on,
    # the family section comes from the authenticated guardian.
    section_id: str | None = None


class FamilyLearnerCreateResponse(BaseModel):
    user_id: str
    learner_id: str
    display_name: str
    grade_level: str
    pin: str
    family_section_id: str


class FamilyLearnerSummary(BaseModel):
    user_id: str
    learner_id: str | None = None
    display_name: str | None = None
    grade_level: str | None = None
