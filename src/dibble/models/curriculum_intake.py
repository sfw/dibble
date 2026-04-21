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


class CurriculumChangeKind(str, Enum):
    added = "added"
    removed = "removed"
    changed = "changed"
    remapped = "remapped"
    prerequisite_changed = "prerequisite_changed"
    alignment_changed = "alignment_changed"


class MigrationRiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RuntimeEntityKind(str, Enum):
    learner_goal = "learner_goal"
    trajectory = "trajectory"
    assignment = "assignment"
    library_artifact = "library_artifact"
    section = "section"
    course = "course"


class MigrationActionType(str, Enum):
    keep_pinned = "keep_pinned"
    remap_via_alignment = "remap_via_alignment"
    swap_provenance_only = "swap_provenance_only"
    mark_trajectory_for_replanning = "mark_trajectory_for_replanning"
    invalidate_library_artifact = "invalidate_library_artifact"


class MigrationActionStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    executed = "executed"
    review_required = "review_required"


class MigrationPlanStatus(str, Enum):
    draft = "draft"
    ready = "ready"
    executed = "executed"


class CurriculumEntityRef(BaseModel):
    snapshot_id: str
    framework_id: str
    framework_version: str | None = None
    artifact_kind: CurriculumArtifactKind
    artifact_id: str
    title: str | None = None


class CurriculumFieldChange(BaseModel):
    field_name: str
    before_value: object | None = None
    after_value: object | None = None


class CurriculumEntityDelta(BaseModel):
    delta_id: str
    artifact_kind: CurriculumArtifactKind
    artifact_id: str
    change_kind: CurriculumChangeKind
    risk_level: MigrationRiskLevel = MigrationRiskLevel.medium
    before: CurriculumEntityRef | None = None
    after: CurriculumEntityRef | None = None
    field_changes: list[CurriculumFieldChange] = Field(default_factory=list)
    approved_alignment_edge_id: str | None = None
    suggested_action: MigrationActionType | None = None
    rationale: str


class CurriculumSnapshotDiff(BaseModel):
    diff_id: str
    source_snapshot_id: str
    target_snapshot_id: str
    framework_id: str | None = None
    source_framework_version: str | None = None
    target_framework_version: str | None = None
    entity_deltas: list[CurriculumEntityDelta] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CurriculumImpactRecord(BaseModel):
    impact_id: str
    entity_kind: RuntimeEntityKind
    entity_id: str
    student_id: str | None = None
    current_snapshot_id: str | None = None
    referenced_course_ids: list[str] = Field(default_factory=list)
    referenced_outcome_ids: list[str] = Field(default_factory=list)
    referenced_kc_ids: list[str] = Field(default_factory=list)
    matched_delta_ids: list[str] = Field(default_factory=list)
    suggested_action: MigrationActionType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: MigrationRiskLevel = MigrationRiskLevel.medium
    rationale: str


class CurriculumImpactAnalysis(BaseModel):
    analysis_id: str
    diff_id: str
    source_snapshot_id: str
    target_snapshot_id: str
    impacts: list[CurriculumImpactRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MigrationAction(BaseModel):
    action_id: str
    action_type: MigrationActionType
    entity_kind: RuntimeEntityKind
    entity_id: str
    source_snapshot_id: str
    target_snapshot_id: str
    source_outcome_ids: list[str] = Field(default_factory=list)
    target_outcome_ids: list[str] = Field(default_factory=list)
    source_kc_ids: list[str] = Field(default_factory=list)
    target_kc_ids: list[str] = Field(default_factory=list)
    approved_alignment_edge_ids: list[str] = Field(default_factory=list)
    risk_level: MigrationRiskLevel = MigrationRiskLevel.medium
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: MigrationActionStatus = MigrationActionStatus.draft
    rationale: str
    reviewer_id: str | None = None
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    execution_summary: str | None = None


class MigrationReviewItem(BaseModel):
    review_item_id: str
    entity_kind: RuntimeEntityKind
    entity_id: str
    risk_level: MigrationRiskLevel = MigrationRiskLevel.medium
    blocking_delta_ids: list[str] = Field(default_factory=list)
    recommended_action: MigrationActionType
    rationale: str


class CurriculumMigrationPlan(BaseModel):
    plan_id: str
    diff_id: str
    source_snapshot_id: str
    target_snapshot_id: str
    status: MigrationPlanStatus = MigrationPlanStatus.draft
    actions: list[MigrationAction] = Field(default_factory=list)
    review_items: list[MigrationReviewItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CurriculumSnapshotDiffRequest(BaseModel):
    source_snapshot_id: str
    target_snapshot_id: str


class CurriculumImpactAnalysisRequest(BaseModel):
    diff_id: str


class CurriculumMigrationPlanRequest(BaseModel):
    diff_id: str


class CurriculumMigrationApprovalRequest(BaseModel):
    reviewer_id: str | None = None
    action_ids: list[str] = Field(default_factory=list)
    approve_all_low_risk: bool = True


class CurriculumMigrationExecutionRequest(BaseModel):
    executor_id: str | None = None
    action_ids: list[str] = Field(default_factory=list)
