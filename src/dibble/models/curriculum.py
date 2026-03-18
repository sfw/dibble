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


class KnowledgeComponentMisconception(BaseModel):
    misconception_id: str
    label: str
    description: str
    trigger_terms: list[str] = Field(default_factory=list)
    prerequisite_kc_ids: list[str] = Field(default_factory=list)
    remediation_hint: str | None = None


class KnowledgeComponentUpsert(BaseModel):
    kc_id: str
    name: str
    parent_lo_id: str
    grade_level: str
    subject: str
    taxonomy_cluster_id: str | None = None
    concept_family: str | None = None
    prerequisite_kc_ids: list[str] = Field(default_factory=list)
    nearby_kc_ids: list[str] = Field(default_factory=list)
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    estimated_time_minutes: int = Field(default=10, ge=1)
    tags: list[str] = Field(default_factory=list)
    common_misconceptions: list[KnowledgeComponentMisconception] = Field(
        default_factory=list
    )


class KnowledgeComponent(KnowledgeComponentUpsert):
    updated_at: datetime = Field(default_factory=utc_now)
