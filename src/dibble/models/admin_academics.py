from __future__ import annotations

from pydantic import Field

from dibble.models.course import Course
from dibble.models.section import Section


class AdminCourseSummary(Course):
    section_count: int = Field(default=0, ge=0)


class AdminSectionSummary(Section):
    course_title: str | None = None
    teacher_count: int = Field(default=0, ge=0)
    learner_count: int = Field(default=0, ge=0)
