from __future__ import annotations

from pydantic import BaseModel, Field

from dibble.models.generation import (
    AdaptiveRouteDecision,
    CurriculumContentRequest,
    GeneratedBlock,
    GroundingReference,
)


class ContentQualityEvalExpectations(BaseModel):
    expected_issue_substrings: list[str] = Field(default_factory=list)
    forbidden_issue_substrings: list[str] = Field(default_factory=list)
    required_prompt_substrings: list[str] = Field(default_factory=list)
    forbidden_prompt_substrings: list[str] = Field(default_factory=list)
    expected_template_name_prefix: str | None = None


class ContentQualityEvalCase(BaseModel):
    case_id: str
    title: str
    target_kc_id: str
    grade_level: str
    intervention_type: str
    modality: str
    request: CurriculumContentRequest
    route: AdaptiveRouteDecision
    grounding: list[GroundingReference] = Field(default_factory=list)
    blocks: list[GeneratedBlock] = Field(default_factory=list)
    expectations: ContentQualityEvalExpectations = Field(
        default_factory=ContentQualityEvalExpectations
    )


class ContentQualityEvalCorpus(BaseModel):
    version: str = "1.0"
    cases: list[ContentQualityEvalCase] = Field(default_factory=list)


class ContentQualityEvalCaseResult(BaseModel):
    case_id: str
    title: str
    passed: bool
    validation_issues: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    prompt_template_name: str
    prompt_template_version: str
    prompt_template_variant: str


class ContentQualityEvalReport(BaseModel):
    version: str
    case_count: int = Field(default=0, ge=0)
    passed_case_count: int = Field(default=0, ge=0)
    failed_case_count: int = Field(default=0, ge=0)
    results: list[ContentQualityEvalCaseResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.failed_case_count == 0
