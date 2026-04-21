from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.models.course import CourseUpsert
from dibble.models.curriculum import (
    KnowledgeComponentUpsert,
    OutcomeUpsert,
    StrandUpsert,
)
from dibble.models.curriculum_intake import (
    AlignmentDecision,
    AlignmentEdgeCreate,
    AlignmentRelationType,
    AlignmentReviewRequest,
    AlignmentSubjectRef,
    CurriculumArtifactKind,
    CurriculumFramework,
    CurriculumImportRequest,
    FrameworkImportMode,
    FrameworkImportStatus,
)
from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    CurriculumContentKey,
    CurriculumContentRequest,
    CurriculumLibraryEntry,
    DeliveryMode,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationResponse,
    InterventionType,
    RequestedContentType,
)
from dibble.services.alignment_edge_store import (
    SQLiteAlignmentEdgeStore,
    SQLiteAlignmentReviewDecisionStore,
)
from dibble.services.auth import hash_credential
from dibble.services.course_store import SQLiteCourseStore
from dibble.services.curriculum_framework_store import SQLiteCurriculumFrameworkStore
from dibble.services.curriculum_import_adapters import (
    AlbertaMath7CurriculumImportAdapter,
    CurriculumImportAdapter,
    ImportedCurriculumBundle,
)
from dibble.services.framework_import_artifact_store import (
    SQLiteFrameworkImportArtifactStore,
)
from dibble.services.framework_import_store import SQLiteFrameworkImportStore
from dibble.services.harness.curriculum_intake_harness import CurriculumIntakeHarness
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.published_curriculum_snapshot_store import (
    SQLitePublishedCurriculumSnapshotStore,
)
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.sqlite_connection import create_connection
from dibble.services.strand_store import SQLiteStrandStore
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database


def _build_harness(tmp_path, *adapters: CurriculumImportAdapter):
    database_path = str(tmp_path / "curriculum-intake.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    course_store = SQLiteCourseStore(conn)
    strand_store = SQLiteStrandStore(conn)
    outcome_store = SQLiteOutcomeStore(conn)
    kc_store = SQLiteKnowledgeComponentStore(conn)
    harness = CurriculumIntakeHarness(
        framework_store=SQLiteCurriculumFrameworkStore(conn),
        framework_import_store=SQLiteFrameworkImportStore(conn),
        framework_import_artifact_store=SQLiteFrameworkImportArtifactStore(conn),
        published_snapshot_store=SQLitePublishedCurriculumSnapshotStore(conn),
        alignment_edge_store=SQLiteAlignmentEdgeStore(conn),
        alignment_review_decision_store=SQLiteAlignmentReviewDecisionStore(conn),
        course_store=course_store,
        strand_store=strand_store,
        outcome_store=outcome_store,
        knowledge_component_store=kc_store,
        adapters=tuple(adapters or (AlbertaMath7CurriculumImportAdapter(),)),
    )
    return harness, course_store, strand_store, outcome_store, kc_store


@dataclass(frozen=True, slots=True)
class _BrokenCycleAdapter(CurriculumImportAdapter):
    adapter_key: str = "broken_cycle"
    import_mode: FrameworkImportMode = FrameworkImportMode.structured_payload

    def build_bundle(
        self, request: CurriculumImportRequest
    ) -> ImportedCurriculumBundle:
        framework = CurriculumFramework(
            framework_id="broken-framework",
            title="Broken Framework",
            jurisdiction="Test",
            subject="math",
            grade_band="5",
        )
        return ImportedCurriculumBundle(
            framework=framework,
            framework_version="v1",
            source_label="Broken cycle fixture",
            source_uri=None,
            planner_summary="Structured test import with a KC prerequisite cycle.",
            courses=[
                CourseUpsert(
                    course_id="BROKEN-COURSE",
                    title="Broken Course",
                    subject="math",
                    grade_band="5",
                )
            ],
            strands=[
                StrandUpsert(
                    strand_id="BROKEN-STRAND",
                    course_id="BROKEN-COURSE",
                    title="Broken Strand",
                )
            ],
            outcomes=[
                OutcomeUpsert(
                    outcome_id="BROKEN-OUTCOME",
                    title="Broken Outcome",
                    strand_id="BROKEN-STRAND",
                    grade_level="5",
                    subject="math",
                    description="Broken graph",
                    knowledge_component_ids=["BROKEN-KC-1", "BROKEN-KC-2"],
                )
            ],
            knowledge_components=[
                KnowledgeComponentUpsert(
                    kc_id="BROKEN-KC-1",
                    name="Broken KC 1",
                    outcome_id="BROKEN-OUTCOME",
                    grade_level="5",
                    subject="math",
                    prerequisite_kc_ids=["BROKEN-KC-2"],
                ),
                KnowledgeComponentUpsert(
                    kc_id="BROKEN-KC-2",
                    name="Broken KC 2",
                    outcome_id="BROKEN-OUTCOME",
                    grade_level="5",
                    subject="math",
                    prerequisite_kc_ids=["BROKEN-KC-1"],
                ),
            ],
        )


def _make_admin_app(tmp_path):
    db_path = str(tmp_path / "curriculum-admin.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    return create_app(settings), db_path


def _seed_admin(db_path: str) -> None:
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id="admin-user",
            display_name="Admin User",
            role="admin",
            api_key_hash=hash_credential("admin-key"),
            section_ids=[],
            created_at=now,
            updated_at=now,
        )
    )


def test_curriculum_import_is_idempotent_for_matching_source_fingerprint(tmp_path):
    harness, _, _, _, _ = _build_harness(tmp_path)
    request = CurriculumImportRequest(adapter_key="alberta_math_7_seed")

    first = harness.import_framework(request)
    second = harness.import_framework(request)

    assert first.import_id == second.import_id
    assert len(harness.list_imports()) == 1
    assert first.verification_report.knowledge_component_count > 0
    assert len(harness.list_import_artifacts(first.import_id)) == (
        first.verification_report.course_count
        + first.verification_report.strand_count
        + first.verification_report.outcome_count
        + first.verification_report.knowledge_component_count
    )


def test_curriculum_publish_materializes_runtime_projection_with_provenance(tmp_path):
    harness, course_store, _, outcome_store, _ = _build_harness(tmp_path)
    framework_import = harness.import_framework(
        CurriculumImportRequest(adapter_key="alberta_math_7_seed")
    )

    snapshot = harness.publish_import(framework_import.import_id)

    course = course_store.get("ab-math-7")
    outcome = outcome_store.get("ab-m7-lo-decimal-ops")
    assert course is not None
    assert outcome is not None
    assert course.curriculum_package_id == snapshot.snapshot_id
    assert outcome.curriculum_provenance is not None
    assert outcome.curriculum_provenance.published_snapshot_id == snapshot.snapshot_id
    assert (
        outcome.curriculum_provenance.framework_import_id == framework_import.import_id
    )

    request = CurriculumContentRequest(
        grade_level="7",
        intent=ContentIntent.explanation,
        content_type=RequestedContentType.micro_explanation,
        target_lo_ids=[outcome.outcome_id],
        curriculum_provenance=outcome.curriculum_provenance,
    )
    grounding = RAGRetriever(outcome_store).retrieve(request, limit=1)
    assert grounding
    assert grounding[0].curriculum_provenance is not None
    assert (
        grounding[0].curriculum_provenance.published_snapshot_id == snapshot.snapshot_id
    )

    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    entry = CurriculumLibraryEntry(
        content_key=CurriculumContentKey(
            request=request,
            route=route,
            grounding=grounding,
        ),
        content=GeneratedContent(
            generation_id="gen-provenance",
            student_id=uuid4(),
            content_type="micro_explanation",
            request_context={},
            response=GenerationResponse(
                student_id=uuid4(),
                route=route,
                blocks=[GeneratedBlock(kind="summary", title="Focus", body="Decimals")],
                curriculum_context=["Decimals"],
                grounding=grounding,
                safety_notes=[],
            ),
            quality=GenerationMetadata(validation_passed=True),
        ),
    )
    assert entry.provenance is not None
    assert entry.provenance.curriculum_provenance is not None
    assert (
        entry.provenance.curriculum_provenance.published_snapshot_id
        == snapshot.snapshot_id
    )


def test_curriculum_import_verifier_marks_prerequisite_cycles_as_failed(tmp_path):
    harness, _, _, _, _ = _build_harness(tmp_path, _BrokenCycleAdapter())

    framework_import = harness.import_framework(
        CurriculumImportRequest(adapter_key="broken_cycle")
    )

    assert framework_import.status == FrameworkImportStatus.failed
    assert any(
        issue.code == "prerequisite_cycle_detected"
        for issue in framework_import.verification_report.issues
    )


def test_alignment_edges_are_durable_and_reviewable(tmp_path):
    harness, _, _, _, _ = _build_harness(tmp_path)
    edge = harness.propose_alignment(
        AlignmentEdgeCreate(
            relation_type=AlignmentRelationType.equivalent_to,
            source=AlignmentSubjectRef(
                framework_id="framework-a",
                framework_version="v1",
                published_snapshot_id="snapshot-a",
                artifact_kind=CurriculumArtifactKind.outcome,
                artifact_id="OUTCOME-A",
                title="Equivalent Fractions",
            ),
            target=AlignmentSubjectRef(
                framework_id="framework-b",
                framework_version="v3",
                published_snapshot_id="snapshot-b",
                artifact_kind=CurriculumArtifactKind.outcome,
                artifact_id="OUTCOME-B",
                title="Fraction Equivalence",
            ),
            confidence=0.78,
            rationale="These outcomes target the same fraction-equivalence skill.",
        )
    )

    reviewed = harness.review_alignment(
        edge.edge_id,
        AlignmentReviewRequest(
            decision=AlignmentDecision.approve,
            reviewer_id="admin-user",
            notes="Reviewed and approved.",
        ),
    )

    reviews = harness.list_alignment_reviews(edge.edge_id)
    assert reviewed.review_status.value == "approved"
    assert reviewed.latest_review_decision_id == reviews[0].decision_id
    assert reviews[0].reviewer_id == "admin-user"


def test_admin_curriculum_api_can_import_and_publish(tmp_path):
    app, db_path = _make_admin_app(tmp_path)
    _seed_admin(db_path)

    with TestClient(app) as client:
        headers = {"X-API-Key": "admin-key"}
        import_response = client.post(
            "/api/admin/curriculum/imports",
            headers=headers,
            json={"adapter_key": "alberta_math_7_seed"},
        )
        assert import_response.status_code == 200

        framework_import = import_response.json()
        publish_response = client.post(
            f"/api/admin/curriculum/imports/{framework_import['import_id']}/publish",
            headers=headers,
            json={"force": False},
        )
        frameworks_response = client.get(
            "/api/admin/curriculum/frameworks",
            headers=headers,
        )

    assert publish_response.status_code == 200
    assert frameworks_response.status_code == 200
    framework_ids = {item["framework_id"] for item in frameworks_response.json()}
    assert "alberta-math-7" in framework_ids
