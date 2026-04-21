from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from dibble.models.course import CourseUpsert
from dibble.models.curriculum import (
    CurriculumVersionReference,
    KnowledgeComponentUpsert,
    OutcomeUpsert,
    StrandUpsert,
)
from dibble.models.curriculum_intake import (
    AlignmentDecision,
    AlignmentEdge,
    AlignmentEdgeCreate,
    AlignmentReviewDecision,
    AlignmentReviewRequest,
    AlignmentReviewStatus,
    CurriculumArtifactKind,
    CurriculumFramework,
    CurriculumImportIssue,
    CurriculumImportRequest,
    CurriculumImportVerificationReport,
    FrameworkImport,
    FrameworkImportArtifact,
    FrameworkImportStatus,
    ImportIssueSeverity,
    PublishedCurriculumSnapshot,
)
from dibble.models.observability import HarnessBoundary, OperationalTraceStatus
from dibble.services.curriculum_import_adapters import (
    CurriculumImportAdapter,
    ImportedCurriculumBundle,
)
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.protocols import (
    AlignmentEdgeStore,
    AlignmentReviewDecisionStore,
    CourseStore,
    CurriculumFrameworkStore,
    FrameworkImportArtifactStore,
    FrameworkImportStore,
    KnowledgeComponentStore,
    OutcomeStore,
    PublishedCurriculumSnapshotStore,
    StrandStore,
)


@dataclass(slots=True)
class CurriculumIntakeHarness:
    framework_store: CurriculumFrameworkStore
    framework_import_store: FrameworkImportStore
    framework_import_artifact_store: FrameworkImportArtifactStore
    published_snapshot_store: PublishedCurriculumSnapshotStore
    alignment_edge_store: AlignmentEdgeStore
    alignment_review_decision_store: AlignmentReviewDecisionStore
    course_store: CourseStore
    strand_store: StrandStore
    outcome_store: OutcomeStore
    knowledge_component_store: KnowledgeComponentStore
    adapters: tuple[CurriculumImportAdapter, ...]
    operational_observability_service: OperationalObservabilityService | None = None

    def list_frameworks(self) -> list[CurriculumFramework]:
        return self.framework_store.list()

    def list_imports(self) -> list[FrameworkImport]:
        return self.framework_import_store.list()

    def get_import(self, import_id: str) -> FrameworkImport | None:
        return self.framework_import_store.get(import_id)

    def list_import_artifacts(self, import_id: str) -> list[FrameworkImportArtifact]:
        return self.framework_import_artifact_store.list_for_import(import_id)

    def list_snapshots(self) -> list[PublishedCurriculumSnapshot]:
        return self.published_snapshot_store.list()

    def list_alignment_edges(self) -> list[AlignmentEdge]:
        return self.alignment_edge_store.list()

    def list_alignment_reviews(self, edge_id: str) -> list[AlignmentReviewDecision]:
        return self.alignment_review_decision_store.list_for_edge(edge_id)

    def import_framework(self, request: CurriculumImportRequest) -> FrameworkImport:
        adapter = self._select_adapter(request.adapter_key)
        bundle = adapter.build_bundle(request)
        source_fingerprint = self._fingerprint(bundle.fingerprint_payload())
        existing = self.framework_import_store.find_by_fingerprint(
            framework_id=bundle.framework.framework_id,
            source_fingerprint=source_fingerprint,
        )
        if existing is not None:
            return existing

        verification_report = self._verify_bundle(bundle)
        status = FrameworkImportStatus.imported
        if verification_report.error_count > 0:
            status = FrameworkImportStatus.failed
        elif verification_report.review_required:
            status = FrameworkImportStatus.review_required

        import_id = f"import-{source_fingerprint[:16]}"
        now = datetime.now(timezone.utc)
        framework = bundle.framework.model_copy(
            update={
                "latest_import_id": import_id,
                "updated_at": now,
            }
        )
        framework_import = FrameworkImport(
            import_id=import_id,
            framework_id=framework.framework_id,
            framework_version=bundle.framework_version,
            adapter_key=adapter.adapter_key,
            import_mode=adapter.import_mode,
            source_label=bundle.source_label,
            source_uri=bundle.source_uri,
            source_fingerprint=source_fingerprint,
            status=status,
            planner_summary=bundle.planner_summary,
            verification_report=verification_report,
            metadata=bundle.metadata,
            created_at=now,
            updated_at=now,
        )

        self.framework_store.upsert(framework)
        self.framework_import_store.upsert(framework_import)
        for artifact in self._artifact_rows(import_id=import_id, bundle=bundle):
            self.framework_import_artifact_store.upsert(artifact)
        self._record_trace(
            operation="import_framework",
            status=OperationalTraceStatus.success,
            summary="Imported curriculum framework artifacts for review.",
            entity_id=framework_import.import_id,
            reason_code="framework_imported",
            payload={
                "framework_id": framework_import.framework_id,
                "status": framework_import.status.value,
                "artifact_count": verification_report.artifact_count,
            },
        )
        return framework_import

    def publish_import(
        self, import_id: str, *, force: bool = False
    ) -> PublishedCurriculumSnapshot:
        framework_import = self.framework_import_store.get(import_id)
        if framework_import is None:
            raise LookupError(import_id)
        if framework_import.status == FrameworkImportStatus.failed and not force:
            raise ValueError("failed_import_requires_force")

        existing_snapshot = self.published_snapshot_store.get_for_import(import_id)
        if existing_snapshot is not None:
            return existing_snapshot

        artifacts = self.framework_import_artifact_store.list_for_import(import_id)
        if not artifacts:
            raise ValueError("no_import_artifacts")

        provenance = CurriculumVersionReference(
            framework_id=framework_import.framework_id,
            framework_version=framework_import.framework_version,
            framework_import_id=framework_import.import_id,
            published_snapshot_id=f"snapshot-{framework_import.import_id}",
            source_label=framework_import.source_label,
        )
        grouped = self._group_artifacts(artifacts)
        runtime_courses = [
            self.course_store.upsert(
                course.model_copy(
                    update={
                        "curriculum_package_id": provenance.published_snapshot_id,
                        "curriculum_provenance": provenance,
                    }
                )
            )
            for course in grouped["courses"]
        ]
        runtime_strands = [
            self.strand_store.upsert(
                strand.model_copy(update={"curriculum_provenance": provenance})
            )
            for strand in grouped["strands"]
        ]
        runtime_outcomes = [
            self.outcome_store.upsert(
                outcome.model_copy(update={"curriculum_provenance": provenance})
            )
            for outcome in grouped["outcomes"]
        ]
        runtime_components = [
            self.knowledge_component_store.upsert(
                component.model_copy(update={"curriculum_provenance": provenance})
            )
            for component in grouped["knowledge_components"]
        ]
        now = datetime.now(timezone.utc)
        snapshot = PublishedCurriculumSnapshot(
            snapshot_id=provenance.published_snapshot_id or f"snapshot-{import_id}",
            framework_id=framework_import.framework_id,
            framework_version=framework_import.framework_version,
            framework_import_id=framework_import.import_id,
            source_label=framework_import.source_label,
            source_fingerprint=framework_import.source_fingerprint,
            runtime_course_ids=[course.course_id for course in runtime_courses],
            runtime_strand_ids=[strand.strand_id for strand in runtime_strands],
            runtime_outcome_ids=[outcome.outcome_id for outcome in runtime_outcomes],
            runtime_knowledge_component_ids=[
                component.kc_id for component in runtime_components
            ],
            published_at=now,
            updated_at=now,
        )
        self.published_snapshot_store.upsert(snapshot)

        framework = self.framework_store.get(framework_import.framework_id)
        if framework is not None:
            self.framework_store.upsert(
                framework.model_copy(
                    update={
                        "latest_import_id": framework_import.import_id,
                        "latest_published_snapshot_id": snapshot.snapshot_id,
                        "updated_at": now,
                    }
                )
            )
        self.framework_import_store.upsert(
            framework_import.model_copy(
                update={
                    "status": FrameworkImportStatus.published,
                    "published_snapshot_id": snapshot.snapshot_id,
                    "updated_at": now,
                }
            )
        )
        self._record_trace(
            operation="publish_import",
            status=OperationalTraceStatus.success,
            summary="Published curriculum import into the runtime snapshot.",
            entity_id=snapshot.snapshot_id,
            reason_code="curriculum_snapshot_published",
            payload={
                "framework_import_id": framework_import.import_id,
                "framework_id": framework_import.framework_id,
                "runtime_outcome_count": len(snapshot.runtime_outcome_ids),
                "runtime_kc_count": len(snapshot.runtime_knowledge_component_ids),
            },
        )
        return snapshot

    def propose_alignment(self, request: AlignmentEdgeCreate) -> AlignmentEdge:
        edge_key = self._fingerprint(
            {
                "relation_type": request.relation_type.value,
                "source": request.source.model_dump(mode="json"),
                "target": request.target.model_dump(mode="json"),
            }
        )
        edge = AlignmentEdge(
            edge_id=f"align-{edge_key[:16]}",
            relation_type=request.relation_type,
            source=request.source,
            target=request.target,
            confidence=request.confidence,
            rationale=request.rationale,
            review_status=AlignmentReviewStatus.pending,
        )
        return self.alignment_edge_store.upsert(edge)

    def review_alignment(
        self, edge_id: str, request: AlignmentReviewRequest
    ) -> AlignmentEdge:
        edge = self.alignment_edge_store.get(edge_id)
        if edge is None:
            raise LookupError(edge_id)
        decision = AlignmentReviewDecision(
            decision_id=str(uuid4()),
            edge_id=edge_id,
            decision=request.decision,
            reviewer_id=request.reviewer_id,
            notes=request.notes,
        )
        self.alignment_review_decision_store.append(decision)
        return self.alignment_edge_store.upsert(
            edge.model_copy(
                update={
                    "review_status": (
                        AlignmentReviewStatus.approved
                        if request.decision == AlignmentDecision.approve
                        else AlignmentReviewStatus.rejected
                    ),
                    "latest_review_decision_id": decision.decision_id,
                    "updated_at": decision.decided_at,
                }
            )
        )

    def _select_adapter(self, adapter_key: str) -> CurriculumImportAdapter:
        for adapter in self.adapters:
            if adapter.adapter_key == adapter_key:
                return adapter
        raise LookupError(adapter_key)

    def _record_trace(
        self,
        *,
        operation: str,
        status: OperationalTraceStatus,
        summary: str,
        entity_id: str | None = None,
        reason_code: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.operational_observability_service is None:
            return
        self.operational_observability_service.record_trace(
            harness=HarnessBoundary.curriculum_evolution,
            operation=operation,
            status=status,
            summary=summary,
            entity_kind="curriculum_snapshot",
            entity_id=entity_id,
            reason_code=reason_code,
            payload=payload,
        )

    def _artifact_rows(
        self, *, import_id: str, bundle: ImportedCurriculumBundle
    ) -> list[FrameworkImportArtifact]:
        artifacts: list[FrameworkImportArtifact] = []
        for kind, key, payload in [
            *[
                (
                    CurriculumArtifactKind.course,
                    course.course_id,
                    course.model_dump(mode="json"),
                )
                for course in bundle.courses
            ],
            *[
                (
                    CurriculumArtifactKind.strand,
                    strand.strand_id,
                    strand.model_dump(mode="json"),
                )
                for strand in bundle.strands
            ],
            *[
                (
                    CurriculumArtifactKind.outcome,
                    outcome.outcome_id,
                    outcome.model_dump(mode="json"),
                )
                for outcome in bundle.outcomes
            ],
            *[
                (
                    CurriculumArtifactKind.knowledge_component,
                    component.kc_id,
                    component.model_dump(mode="json"),
                )
                for component in bundle.knowledge_components
            ],
        ]:
            artifacts.append(
                FrameworkImportArtifact(
                    artifact_id=f"{import_id}:{kind.value}:{key}",
                    import_id=import_id,
                    artifact_kind=kind,
                    artifact_key=key,
                    confidence=1.0,
                    review_required=False,
                    payload=payload,
                )
            )
        return artifacts

    def _verify_bundle(
        self, bundle: ImportedCurriculumBundle
    ) -> CurriculumImportVerificationReport:
        issues: list[CurriculumImportIssue] = []
        courses = {course.course_id: course for course in bundle.courses}
        strands = {strand.strand_id: strand for strand in bundle.strands}
        outcomes = {outcome.outcome_id: outcome for outcome in bundle.outcomes}
        components = {
            component.kc_id: component for component in bundle.knowledge_components
        }

        for strand in bundle.strands:
            if strand.course_id not in courses:
                issues.append(
                    CurriculumImportIssue(
                        code="strand_course_missing",
                        severity=ImportIssueSeverity.error,
                        message=(
                            f"Strand {strand.strand_id} references missing course"
                            f" {strand.course_id}."
                        ),
                        artifact_kind=CurriculumArtifactKind.strand,
                        artifact_id=strand.strand_id,
                    )
                )
        for outcome in bundle.outcomes:
            if outcome.strand_id not in strands:
                issues.append(
                    CurriculumImportIssue(
                        code="outcome_strand_missing",
                        severity=ImportIssueSeverity.error,
                        message=(
                            f"Outcome {outcome.outcome_id} references missing strand"
                            f" {outcome.strand_id}."
                        ),
                        artifact_kind=CurriculumArtifactKind.outcome,
                        artifact_id=outcome.outcome_id,
                    )
                )
            for kc_id in outcome.knowledge_component_ids:
                if kc_id not in components:
                    issues.append(
                        CurriculumImportIssue(
                            code="outcome_component_missing",
                            severity=ImportIssueSeverity.error,
                            message=(
                                f"Outcome {outcome.outcome_id} references missing"
                                f" knowledge component {kc_id}."
                            ),
                            artifact_kind=CurriculumArtifactKind.outcome,
                            artifact_id=outcome.outcome_id,
                        )
                    )
        for component in bundle.knowledge_components:
            if component.outcome_id not in outcomes:
                issues.append(
                    CurriculumImportIssue(
                        code="component_outcome_missing",
                        severity=ImportIssueSeverity.error,
                        message=(
                            f"Knowledge component {component.kc_id} references"
                            f" missing outcome {component.outcome_id}."
                        ),
                        artifact_kind=CurriculumArtifactKind.knowledge_component,
                        artifact_id=component.kc_id,
                    )
                )
            for prerequisite_id in component.prerequisite_kc_ids:
                if prerequisite_id not in components:
                    issues.append(
                        CurriculumImportIssue(
                            code="component_prerequisite_missing",
                            severity=ImportIssueSeverity.error,
                            message=(
                                f"Knowledge component {component.kc_id} references"
                                f" missing prerequisite {prerequisite_id}."
                            ),
                            artifact_kind=CurriculumArtifactKind.knowledge_component,
                            artifact_id=component.kc_id,
                        )
                    )
            if component.difficulty < 0.0 or component.difficulty > 1.0:
                issues.append(
                    CurriculumImportIssue(
                        code="component_difficulty_invalid",
                        severity=ImportIssueSeverity.error,
                        message=(
                            f"Knowledge component {component.kc_id} has invalid"
                            " difficulty."
                        ),
                        artifact_kind=CurriculumArtifactKind.knowledge_component,
                        artifact_id=component.kc_id,
                    )
                )

        cycle_path = self._find_prerequisite_cycle(bundle.knowledge_components)
        if cycle_path:
            issues.append(
                CurriculumImportIssue(
                    code="prerequisite_cycle_detected",
                    severity=ImportIssueSeverity.error,
                    message=(
                        "Knowledge component prerequisite cycle detected: "
                        + " -> ".join(cycle_path)
                    ),
                    artifact_kind=CurriculumArtifactKind.knowledge_component,
                    artifact_id=cycle_path[0],
                )
            )

        report = CurriculumImportVerificationReport(
            issue_count=len(issues),
            error_count=sum(
                1 for issue in issues if issue.severity == ImportIssueSeverity.error
            ),
            warning_count=sum(
                1 for issue in issues if issue.severity == ImportIssueSeverity.warning
            ),
            review_required=any(
                issue.severity == ImportIssueSeverity.warning for issue in issues
            ),
            artifact_count=(
                len(bundle.courses)
                + len(bundle.strands)
                + len(bundle.outcomes)
                + len(bundle.knowledge_components)
            ),
            course_count=len(bundle.courses),
            strand_count=len(bundle.strands),
            outcome_count=len(bundle.outcomes),
            knowledge_component_count=len(bundle.knowledge_components),
            issues=issues,
        )
        return report

    def _group_artifacts(
        self, artifacts: list[FrameworkImportArtifact]
    ) -> dict[
        str,
        list[CourseUpsert | StrandUpsert | OutcomeUpsert | KnowledgeComponentUpsert],
    ]:
        grouped: dict[
            str,
            list[
                CourseUpsert | StrandUpsert | OutcomeUpsert | KnowledgeComponentUpsert
            ],
        ] = {
            "courses": [],
            "strands": [],
            "outcomes": [],
            "knowledge_components": [],
        }
        for artifact in artifacts:
            if artifact.artifact_kind == CurriculumArtifactKind.course:
                grouped["courses"].append(CourseUpsert.model_validate(artifact.payload))
            elif artifact.artifact_kind == CurriculumArtifactKind.strand:
                grouped["strands"].append(StrandUpsert.model_validate(artifact.payload))
            elif artifact.artifact_kind == CurriculumArtifactKind.outcome:
                grouped["outcomes"].append(
                    OutcomeUpsert.model_validate(artifact.payload)
                )
            elif artifact.artifact_kind == CurriculumArtifactKind.knowledge_component:
                grouped["knowledge_components"].append(
                    KnowledgeComponentUpsert.model_validate(artifact.payload)
                )
        return grouped

    def _find_prerequisite_cycle(
        self, components: list[KnowledgeComponentUpsert]
    ) -> list[str]:
        graph = {
            component.kc_id: list(component.prerequisite_kc_ids)
            for component in components
        }
        visited: set[str] = set()
        visiting: list[str] = []

        def visit(node_id: str) -> list[str]:
            if node_id in visiting:
                cycle_start = visiting.index(node_id)
                return visiting[cycle_start:] + [node_id]
            if node_id in visited:
                return []
            visiting.append(node_id)
            for dependency in graph.get(node_id, []):
                cycle = visit(dependency)
                if cycle:
                    return cycle
            visiting.pop()
            visited.add(node_id)
            return []

        for node_id in graph:
            cycle = visit(node_id)
            if cycle:
                return cycle
        return []

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()
