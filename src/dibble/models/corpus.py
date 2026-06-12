from __future__ import annotations

from pydantic import BaseModel, Field

from dibble.models.course import CourseUpsert
from dibble.models.curriculum import (
    KnowledgeComponentUpsert,
    OutcomeUpsert,
    StrandUpsert,
)

ANCHOR_TAG = "anchor"


class CorpusDocument(BaseModel):
    """One ingestible curriculum corpus file: a course with its strands,
    learning outcomes (whose descriptions are the grounding body text), and
    knowledge components (with prerequisite edges and misconception
    catalogs)."""

    course: CourseUpsert
    strands: list[StrandUpsert] = Field(default_factory=list)
    outcomes: list[OutcomeUpsert] = Field(default_factory=list)
    knowledge_components: list[KnowledgeComponentUpsert] = Field(default_factory=list)


class CorpusValidationIssue(BaseModel):
    severity: str  # "error" | "warning"
    code: str
    message: str


class CorpusValidationReport(BaseModel):
    issues: list[CorpusValidationIssue] = Field(default_factory=list)
    outcome_count: int = 0
    knowledge_component_count: int = 0
    anchor_kc_count: int = 0
    misconception_count: int = 0

    @property
    def errors(self) -> list[CorpusValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[CorpusValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


class CorpusIngestionResult(BaseModel):
    course_id: str
    strands_upserted: int = 0
    outcomes_upserted: int = 0
    knowledge_components_upserted: int = 0
