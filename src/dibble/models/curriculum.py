from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CurriculumResourceUpsert(BaseModel):
    resource_id: str
    title: str
    grade_level: str
    subject: str
    learning_objective_ids: list[str] = Field(default_factory=list)
    knowledge_component_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    body: str
    source_type: str = "curriculum_standard"


class CurriculumResource(CurriculumResourceUpsert):
    updated_at: datetime = Field(default_factory=utc_now)
