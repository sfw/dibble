from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SectionUpsert(BaseModel):
    section_id: str
    course_id: str
    title: str
    grade_level: str | None = None
    subject: str | None = None
    tags: list[str] = Field(default_factory=list)


class Section(SectionUpsert):
    updated_at: datetime = Field(default_factory=utc_now)
