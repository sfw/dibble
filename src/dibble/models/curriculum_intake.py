from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CurriculumArtifactKind(str, Enum):
    course = "course"
    strand = "strand"
    outcome = "outcome"
    knowledge_component = "knowledge_component"


class FrameworkImportMode(str, Enum):
    structured_seed = "structured_seed"
    structured_payload = "structured_payload"
    unstructured_extraction = "unstructured_extraction"


class FrameworkImportStatus(str, Enum):
    imported = "imported"
    review_required = "review_required"
    failed = "failed"
    published = "published"


class ImportIssueSeverity(str, Enum):
    warning = "warning"
    error = "error"


class AlignmentRelationType(str, Enum):
    equivalent_to = "equivalent_to"
    overlaps_with = "overlaps_with"


class AlignmentReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AlignmentDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class CurriculumImportIssue(BaseModel):
    code: str
    severity: ImportIssueSeverity
    message: str
    artifact_kind: CurriculumArtifactKind | None = None
    artifact_id: str | None = None


class CurriculumImportVerificationReport(BaseModel):
    issue_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    review_required: bool = False
    artifact_count: int = Field(default=0, ge=0)
    course_count: int = Field(default=0, ge=0)
    strand_count: int = Field(default=0, ge=0)
    outcome_count: int = Field(default=0, ge=0)
    knowledge_component_count: int = Field(default=0, ge=0)
    issues: list[CurriculumImportIssue] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=utc_now)


class CurriculumFramework(BaseModel):
    framework_id: str
    title: str
    jurisdiction: str
    subject: str
    grade_band: str | None = None
    language: str = "en"
    tags: list[str] = Field(default_factory=list)
    latest_import_id: str | None = None
    latest_published_snapshot_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class FrameworkImport(BaseModel):
    import_id: str
    framework_id: str
    framework_version: str
    adapter_key: str
    import_mode: FrameworkImportMode
    source_label: str
    source_uri: str | None = None
    source_fingerprint: str
    status: FrameworkImportStatus = FrameworkImportStatus.imported
    planner_summary: str | None = None
    published_snapshot_id: str | None = None
    verification_report: CurriculumImportVerificationReport = Field(
        default_factory=CurriculumImportVerificationReport
    )
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class FrameworkImportArtifact(BaseModel):
    artifact_id: str
    import_id: str
    artifact_kind: CurriculumArtifactKind
    artifact_key: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    review_required: bool = False
    payload: dict[str, object]
    created_at: datetime = Field(default_factory=utc_now)


class PublishedCurriculumSnapshot(BaseModel):
    snapshot_id: str
    framework_id: str
    framework_version: str
    framework_import_id: str
    source_label: str
    source_fingerprint: str
    runtime_course_ids: list[str] = Field(default_factory=list)
    runtime_strand_ids: list[str] = Field(default_factory=list)
    runtime_outcome_ids: list[str] = Field(default_factory=list)
    runtime_knowledge_component_ids: list[str] = Field(default_factory=list)
    published_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AlignmentSubjectRef(BaseModel):
    framework_id: str
    framework_version: str | None = None
    published_snapshot_id: str | None = None
    artifact_kind: CurriculumArtifactKind
    artifact_id: str
    title: str | None = None


class AlignmentEdge(BaseModel):
    edge_id: str
    relation_type: AlignmentRelationType
    source: AlignmentSubjectRef
    target: AlignmentSubjectRef
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None
    review_status: AlignmentReviewStatus = AlignmentReviewStatus.pending
    latest_review_decision_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AlignmentReviewDecision(BaseModel):
    decision_id: str
    edge_id: str
    decision: AlignmentDecision
    reviewer_id: str | None = None
    notes: str | None = None
    decided_at: datetime = Field(default_factory=utc_now)


class CurriculumImportRequest(BaseModel):
    adapter_key: str
    framework_id: str | None = None
    title: str | None = None
    jurisdiction: str | None = None
    subject: str | None = None
    grade_band: str | None = None
    framework_version: str | None = None
    language: str = "en"
    source_label: str | None = None
    source_uri: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class CurriculumPublishRequest(BaseModel):
    force: bool = False


class AlignmentEdgeCreate(BaseModel):
    relation_type: AlignmentRelationType
    source: AlignmentSubjectRef
    target: AlignmentSubjectRef
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None


class AlignmentReviewRequest(BaseModel):
    decision: AlignmentDecision
    reviewer_id: str | None = None
    notes: str | None = None
