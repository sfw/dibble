from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from dibble.models.curriculum import CurriculumVersionReference


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CourseUpsert(BaseModel):
    course_id: str
    title: str
    subject: str | None = None
    grade_band: str | None = None
    curriculum_package_id: str | None = None
    curriculum_provenance: CurriculumVersionReference | None = None
    tags: list[str] = Field(default_factory=list)


class Course(CourseUpsert):
    updated_at: datetime = Field(default_factory=utc_now)
