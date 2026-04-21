from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.models.assignment import Assignment
from dibble.models.course import CourseUpsert
from dibble.models.curriculum import (
    CurriculumVersionReference,
    KnowledgeComponentUpsert,
    OutcomeUpsert,
    StrandUpsert,
)
from dibble.models.curriculum_intake import (
    AlignmentEdgeCreate,
    AlignmentRelationType,
    AlignmentReviewRequest,
    AlignmentSubjectRef,
    CurriculumArtifactKind,
    CurriculumChangeKind,
    CurriculumFramework,
    CurriculumImpactAnalysisRequest,
    CurriculumImportRequest,
    CurriculumMigrationApprovalRequest,
    CurriculumMigrationExecutionRequest,
    CurriculumMigrationPlan,
    CurriculumMigrationPlanRequest,
    CurriculumSnapshotDiffRequest,
    FrameworkImportMode,
    MigrationAction,
    MigrationActionStatus,
    MigrationActionType,
    MigrationPlanStatus,
    MigrationRiskLevel,
    RuntimeEntityKind,
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
from dibble.models.planning import LearnerGoal, TrajectoryNode, TrajectoryPlan, TrajectoryRevision
from dibble.models.profile import LearnerProfile
from dibble.services.alignment_edge_store import (
    SQLiteAlignmentEdgeStore,
    SQLiteAlignmentReviewDecisionStore,
)
from dibble.services.assignment_store import SQLiteAssignmentStore
from dibble.services.classroom_store import SQLiteClassroomStore
from dibble.services.course_store import SQLiteCourseStore
from dibble.services.curriculum_content_library_store import (
    SQLiteCurriculumContentLibraryStore,
)
from dibble.services.curriculum_framework_store import SQLiteCurriculumFrameworkStore
from dibble.services.curriculum_impact_analysis_store import (
    SQLiteCurriculumImpactAnalysisStore,
)
from dibble.services.curriculum_import_adapters import (
    CurriculumImportAdapter,
    ImportedCurriculumBundle,
)
from dibble.services.curriculum_migration_plan_store import (
    SQLiteCurriculumMigrationPlanStore,
)
from dibble.services.curriculum_snapshot_diff_store import (
    SQLiteCurriculumSnapshotDiffStore,
)
from dibble.services.framework_import_artifact_store import (
    SQLiteFrameworkImportArtifactStore,
)
from dibble.services.framework_import_store import SQLiteFrameworkImportStore
from dibble.services.harness.curriculum_evolution import CurriculumEvolutionHarness
from dibble.services.harness.curriculum_intake_harness import CurriculumIntakeHarness
from dibble.services.learner_goal_store import SQLiteLearnerGoalStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.published_curriculum_snapshot_store import (
    SQLitePublishedCurriculumSnapshotStore,
)
from dibble.services.sqlite_connection import create_connection
from dibble.services.strand_store import SQLiteStrandStore
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.trajectory_store import SQLiteTrajectoryStore
from dibble.services.auth import hash_credential
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database


@dataclass(frozen=True, slots=True)
class _StaticAdapter(CurriculumImportAdapter):
    adapter_key: str
    framework_version: str
    courses: list[CourseUpsert]
    strands: list[StrandUpsert]
    outcomes: list[OutcomeUpsert]
    knowledge_components: list[KnowledgeComponentUpsert]
    import_mode: FrameworkImportMode = FrameworkImportMode.structured_payload

    def build_bundle(
        self, request: CurriculumImportRequest
    ) -> ImportedCurriculumBundle:
        framework = CurriculumFramework(
            framework_id="math-framework",
            title="Math Framework",
            jurisdiction="Test",
            subject="math",
            grade_band="7",
        )
        return ImportedCurriculumBundle(
            framework=framework,
            framework_version=self.framework_version,
            source_label=f"Framework {self.framework_version}",
            source_uri=None,
            planner_summary=f"Static import {self.framework_version}",
            courses=self.courses,
            strands=self.strands,
            outcomes=self.outcomes,
            knowledge_components=self.knowledge_components,
        )


def _build_harnesses(tmp_path, *adapters: CurriculumImportAdapter):
    database_path = str(tmp_path / "curriculum-evolution.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    course_store = SQLiteCourseStore(conn)
    classroom_store = SQLiteClassroomStore(conn)
    harness = CurriculumIntakeHarness(
        framework_store=SQLiteCurriculumFrameworkStore(conn),
        framework_import_store=SQLiteFrameworkImportStore(conn),
        framework_import_artifact_store=SQLiteFrameworkImportArtifactStore(conn),
        published_snapshot_store=SQLitePublishedCurriculumSnapshotStore(conn),
        alignment_edge_store=SQLiteAlignmentEdgeStore(conn),
        alignment_review_decision_store=SQLiteAlignmentReviewDecisionStore(conn),
        course_store=course_store,
        strand_store=SQLiteStrandStore(conn),
        outcome_store=SQLiteOutcomeStore(conn),
        knowledge_component_store=SQLiteKnowledgeComponentStore(conn),
        adapters=adapters,
    )
    evolution = CurriculumEvolutionHarness(
        published_snapshot_store=SQLitePublishedCurriculumSnapshotStore(conn),
        framework_import_artifact_store=SQLiteFrameworkImportArtifactStore(conn),
        alignment_edge_store=SQLiteAlignmentEdgeStore(conn),
        curriculum_snapshot_diff_store=SQLiteCurriculumSnapshotDiffStore(conn),
        curriculum_impact_analysis_store=SQLiteCurriculumImpactAnalysisStore(conn),
        curriculum_migration_plan_store=SQLiteCurriculumMigrationPlanStore(conn),
        profile_store=SQLiteProfileStore(conn),
        learner_goal_store=SQLiteLearnerGoalStore(conn),
        trajectory_store=SQLiteTrajectoryStore(conn),
        assignment_store=SQLiteAssignmentStore(conn),
        classroom_store=classroom_store,
        course_store=course_store,
        curriculum_content_library_store=SQLiteCurriculumContentLibraryStore(conn),
    )
    return harness, evolution


def _publish(harness: CurriculumIntakeHarness, adapter_key: str):
    framework_import = harness.import_framework(
        CurriculumImportRequest(adapter_key=adapter_key)
    )
    return harness.publish_import(framework_import.import_id)


def _base_curriculum(adapter_key: str, version: str) -> _StaticAdapter:
    return _StaticAdapter(
        adapter_key=adapter_key,
        framework_version=version,
        courses=[
            CourseUpsert(
                course_id="COURSE-1",
                title="Math 7",
                subject="math",
                grade_band="7",
            )
        ],
        strands=[
            StrandUpsert(
                strand_id="STRAND-1",
                course_id="COURSE-1",
                title="Number Sense",
            )
        ],
        outcomes=[
            OutcomeUpsert(
                outcome_id="OUTCOME-1",
                title="Operate on rational numbers",
                strand_id="STRAND-1",
                grade_level="7",
                subject="math",
                description="Work with rational numbers.",
                knowledge_component_ids=["KC-1", "KC-2"],
            )
        ],
        knowledge_components=[
            KnowledgeComponentUpsert(
                kc_id="KC-1",
                name="Understand signed numbers",
                outcome_id="OUTCOME-1",
                grade_level="7",
                subject="math",
            ),
            KnowledgeComponentUpsert(
                kc_id="KC-2",
                name="Add integers",
                outcome_id="OUTCOME-1",
                grade_level="7",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
            ),
        ],
    )


def test_snapshot_diff_detects_prerequisite_and_added_entities(tmp_path):
    adapter_v1 = _base_curriculum("curriculum_v1", "v1")
    adapter_v2 = _StaticAdapter(
        adapter_key="curriculum_v2",
        framework_version="v2",
        courses=adapter_v1.courses,
        strands=adapter_v1.strands,
        outcomes=[
            OutcomeUpsert(
                outcome_id="OUTCOME-1",
                title="Operate on rational numbers",
                strand_id="STRAND-1",
                grade_level="7",
                subject="math",
                description="Work with rational numbers and justify the strategy.",
                knowledge_component_ids=["KC-1", "KC-2", "KC-3"],
            )
        ],
        knowledge_components=[
            adapter_v1.knowledge_components[0],
            KnowledgeComponentUpsert(
                kc_id="KC-2",
                name="Add integers",
                outcome_id="OUTCOME-1",
                grade_level="7",
                subject="math",
                prerequisite_kc_ids=["KC-1", "KC-3"],
            ),
            KnowledgeComponentUpsert(
                kc_id="KC-3",
                name="Compare integer strategies",
                outcome_id="OUTCOME-1",
                grade_level="7",
                subject="math",
            ),
        ],
    )
    intake, evolution = _build_harnesses(tmp_path, adapter_v1, adapter_v2)

    source_snapshot = _publish(intake, "curriculum_v1")
    target_snapshot = _publish(intake, "curriculum_v2")
    diff = evolution.create_snapshot_diff(
        CurriculumSnapshotDiffRequest(
            source_snapshot_id=source_snapshot.snapshot_id,
            target_snapshot_id=target_snapshot.snapshot_id,
        )
    )

    change_kinds = {
        (delta.artifact_kind, delta.artifact_id): delta.change_kind
        for delta in diff.entity_deltas
    }
    assert (
        change_kinds[(CurriculumArtifactKind.knowledge_component, "KC-2")]
        == CurriculumChangeKind.prerequisite_changed
    )
    assert (
        change_kinds[(CurriculumArtifactKind.knowledge_component, "KC-3")]
        == CurriculumChangeKind.added
    )
    outcome_delta = next(
        delta
        for delta in diff.entity_deltas
        if delta.artifact_kind == CurriculumArtifactKind.outcome
        and delta.artifact_id == "OUTCOME-1"
    )
    assert {change.field_name for change in outcome_delta.field_changes} == {
        "description",
        "knowledge_component_ids",
    }


def test_safe_remap_via_alignment_updates_runtime_entities_and_library(tmp_path):
    adapter_v1 = _base_curriculum("curriculum_v1", "v1")
    adapter_v2 = _StaticAdapter(
        adapter_key="curriculum_v2",
        framework_version="v2",
        courses=adapter_v1.courses,
        strands=adapter_v1.strands,
        outcomes=[
            OutcomeUpsert(
                outcome_id="OUTCOME-1",
                title="Operate on rational numbers",
                strand_id="STRAND-1",
                grade_level="7",
                subject="math",
                description="Work with rational numbers.",
                knowledge_component_ids=["KC-1", "KC-2B"],
            )
        ],
        knowledge_components=[
            adapter_v1.knowledge_components[0],
            KnowledgeComponentUpsert(
                kc_id="KC-2B",
                name="Add integers equivalently",
                outcome_id="OUTCOME-1",
                grade_level="7",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
            ),
        ],
    )
    intake, evolution = _build_harnesses(tmp_path, adapter_v1, adapter_v2)

    source_snapshot = _publish(intake, "curriculum_v1")
    target_snapshot = _publish(intake, "curriculum_v2")
    intake.review_alignment(
        intake.propose_alignment(
            AlignmentEdgeCreate(
                relation_type=AlignmentRelationType.equivalent_to,
                source=AlignmentSubjectRef(
                    framework_id="math-framework",
                    framework_version="v1",
                    published_snapshot_id=source_snapshot.snapshot_id,
                    artifact_kind=CurriculumArtifactKind.knowledge_component,
                    artifact_id="KC-2",
                    title="Add integers",
                ),
                target=AlignmentSubjectRef(
                    framework_id="math-framework",
                    framework_version="v2",
                    published_snapshot_id=target_snapshot.snapshot_id,
                    artifact_kind=CurriculumArtifactKind.knowledge_component,
                    artifact_id="KC-2B",
                    title="Add integers equivalently",
                ),
                confidence=0.99,
                rationale="The KC split only changed the stable identifier.",
            )
        ).edge_id,
        request=AlignmentReviewRequest(
            decision="approve",
            reviewer_id="admin-user",
        ),
    )

    source_provenance = CurriculumVersionReference(
        framework_id="math-framework",
        framework_version="v1",
        framework_import_id=source_snapshot.framework_import_id,
        published_snapshot_id=source_snapshot.snapshot_id,
        source_label=source_snapshot.source_label,
    )
    student_id = uuid4()
    evolution.profile_store.upsert(LearnerProfile(student_id=student_id, grade_level="7"))
    goal = LearnerGoal(
        goal_id="goal-1",
        student_id=student_id,
        title="Integer fluency",
        target_kc_ids=["KC-2"],
        curriculum_provenance=source_provenance,
        active_trajectory_id="trajectory-1",
    )
    trajectory = TrajectoryPlan(
        trajectory_id="trajectory-1",
        goal_id=goal.goal_id,
        student_id=student_id,
        curriculum_provenance=source_provenance,
        nodes=[
            TrajectoryNode(
                node_id="node-1",
                title="Practice integer addition",
                target_kc_ids=["KC-2"],
                ordered_kc_ids=["KC-2"],
            )
        ],
        revisions=[TrajectoryRevision(revision_id="rev-1", node_count=1)],
    )
    evolution.learner_goal_store.upsert(goal)
    evolution.trajectory_store.upsert(trajectory)
    evolution.assignment_store.upsert(
        Assignment(
            assignment_id="assignment-1",
            student_id=str(student_id),
            teacher_id="teacher-1",
            title="Integer practice",
            target_kc_ids=["KC-2"],
        )
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    entry = CurriculumLibraryEntry(
        content_key=CurriculumContentKey(
            request=CurriculumContentRequest(
                grade_level="7",
                intent=ContentIntent.practice,
                content_type=RequestedContentType.practice_problem,
                target_kc_ids=["KC-2"],
                curriculum_provenance=source_provenance,
            ),
            route=route,
        ),
        content=GeneratedContent(
            generation_id="gen-1",
            student_id=student_id,
            content_type="practice_problem",
            request_context={},
            response=GenerationResponse(
                student_id=student_id,
                route=route,
                blocks=[GeneratedBlock(kind="practice", title="Practice", body="Add -3 + 7")],
                curriculum_context=["Integer addition"],
                safety_notes=[],
            ),
            quality=GenerationMetadata(),
        ),
    )
    evolution.curriculum_content_library_store.upsert_entry(entry=entry)

    diff = evolution.create_snapshot_diff(
        CurriculumSnapshotDiffRequest(
            source_snapshot_id=source_snapshot.snapshot_id,
            target_snapshot_id=target_snapshot.snapshot_id,
        )
    )
    analysis = evolution.analyze_impact(
        CurriculumImpactAnalysisRequest(diff_id=diff.diff_id)
    )
    by_kind = {impact.entity_kind: impact for impact in analysis.impacts}
    assert by_kind[RuntimeEntityKind.learner_goal].suggested_action == MigrationActionType.remap_via_alignment
    assert by_kind[RuntimeEntityKind.trajectory].suggested_action == MigrationActionType.remap_via_alignment
    assert by_kind[RuntimeEntityKind.assignment].suggested_action == MigrationActionType.remap_via_alignment
    assert by_kind[RuntimeEntityKind.library_artifact].suggested_action == MigrationActionType.remap_via_alignment

    plan = evolution.create_migration_plan(
        CurriculumMigrationPlanRequest(diff_id=diff.diff_id)
    )
    approved = evolution.approve_migration_plan(
        plan.plan_id,
        CurriculumMigrationApprovalRequest(reviewer_id="admin-user"),
    )
    assert all(
        action.status == MigrationActionStatus.approved for action in approved.actions
    )

    executed = evolution.execute_migration_plan(
        approved.plan_id,
        CurriculumMigrationExecutionRequest(executor_id="admin-user"),
    )
    assert all(
        action.status == MigrationActionStatus.executed for action in executed.actions
    )

    migrated_goal = evolution.learner_goal_store.get("goal-1")
    assert migrated_goal is not None
    assert migrated_goal.target_kc_ids == ["KC-2B"]
    assert migrated_goal.curriculum_provenance is not None
    assert migrated_goal.curriculum_provenance.published_snapshot_id == target_snapshot.snapshot_id

    migrated_trajectory = evolution.trajectory_store.get("trajectory-1")
    assert migrated_trajectory is not None
    assert migrated_trajectory.nodes[0].target_kc_ids == ["KC-2B"]
    assert migrated_trajectory.curriculum_provenance is not None
    assert migrated_trajectory.curriculum_provenance.published_snapshot_id == target_snapshot.snapshot_id

    migrated_assignment = evolution.assignment_store.get("assignment-1")
    assert migrated_assignment is not None
    assert migrated_assignment.target_kc_ids == ["KC-2B"]

    entries = evolution.curriculum_content_library_store.list_entries(include_expired=True)
    active_entries = [item for item in entries if item.content.expires_at is None]
    assert any(
        item.content_key.request.target_kc_ids == ["KC-2B"]
        and item.provenance is not None
        and item.provenance.curriculum_provenance is not None
        and item.provenance.curriculum_provenance.published_snapshot_id
        == target_snapshot.snapshot_id
        for item in active_entries
    )
    assert any(
        item.content.expires_at is not None and item.content_key.request.target_kc_ids == ["KC-2"]
        for item in entries
    )


def test_ambiguous_removed_outcome_stays_review_required(tmp_path):
    adapter_v1 = _base_curriculum("curriculum_v1", "v1")
    adapter_v2 = _StaticAdapter(
        adapter_key="curriculum_v2",
        framework_version="v2",
        courses=adapter_v1.courses,
        strands=adapter_v1.strands,
        outcomes=[],
        knowledge_components=[],
    )
    intake, evolution = _build_harnesses(tmp_path, adapter_v1, adapter_v2)

    source_snapshot = _publish(intake, "curriculum_v1")
    target_snapshot = _publish(intake, "curriculum_v2")
    student_id = uuid4()
    evolution.profile_store.upsert(LearnerProfile(student_id=student_id, grade_level="7"))
    evolution.learner_goal_store.upsert(
        LearnerGoal(
            goal_id="goal-ambiguous",
            student_id=student_id,
            title="Rational numbers",
            target_outcome_id="OUTCOME-1",
            target_outcome_ids=["OUTCOME-1"],
            curriculum_provenance=CurriculumVersionReference(
                framework_id="math-framework",
                framework_version="v1",
                framework_import_id=source_snapshot.framework_import_id,
                published_snapshot_id=source_snapshot.snapshot_id,
                source_label=source_snapshot.source_label,
            ),
        )
    )

    diff = evolution.create_snapshot_diff(
        CurriculumSnapshotDiffRequest(
            source_snapshot_id=source_snapshot.snapshot_id,
            target_snapshot_id=target_snapshot.snapshot_id,
        )
    )
    analysis = evolution.analyze_impact(
        CurriculumImpactAnalysisRequest(diff_id=diff.diff_id)
    )
    goal_impact = next(
        impact
        for impact in analysis.impacts
        if impact.entity_kind == RuntimeEntityKind.learner_goal
    )
    assert goal_impact.suggested_action == MigrationActionType.keep_pinned
    assert goal_impact.risk_level == MigrationRiskLevel.high

    plan = evolution.create_migration_plan(
        CurriculumMigrationPlanRequest(diff_id=diff.diff_id)
    )
    goal_action = next(
        action for action in plan.actions if action.entity_kind == RuntimeEntityKind.learner_goal
    )
    assert goal_action.status == MigrationActionStatus.review_required
    assert plan.review_items


def test_admin_curriculum_evolution_api_flow(tmp_path, monkeypatch):
    adapter_v1 = _base_curriculum("curriculum_v1", "v1")
    adapter_v2 = _StaticAdapter(
        adapter_key="curriculum_v2",
        framework_version="v2",
        courses=adapter_v1.courses,
        strands=adapter_v1.strands,
        outcomes=adapter_v1.outcomes,
        knowledge_components=[
            adapter_v1.knowledge_components[0],
            KnowledgeComponentUpsert(
                kc_id="KC-2",
                name="Add integers with updated wording",
                outcome_id="OUTCOME-1",
                grade_level="7",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
            ),
        ],
    )
    monkeypatch.setattr(
        "dibble.bootstrap.default_curriculum_import_adapters",
        lambda: [adapter_v1, adapter_v2],
    )
    database_path = str(tmp_path / "curriculum-evolution-api.db")
    ensure_database(database_path)
    app = create_app(Settings(database_path=database_path, auth_enabled=True))
    conn = create_connection(database_path)
    now = datetime.now(timezone.utc).isoformat()
    SQLiteUserStore(conn).create(
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

    with TestClient(app) as client:
        headers = {"X-API-Key": "admin-key"}
        source_import = client.post(
            "/api/admin/curriculum/imports",
            headers=headers,
            json={"adapter_key": "curriculum_v1"},
        ).json()
        target_import = client.post(
            "/api/admin/curriculum/imports",
            headers=headers,
            json={"adapter_key": "curriculum_v2"},
        ).json()
        source_snapshot = client.post(
            f"/api/admin/curriculum/imports/{source_import['import_id']}/publish",
            headers=headers,
            json={"force": False},
        ).json()
        target_snapshot = client.post(
            f"/api/admin/curriculum/imports/{target_import['import_id']}/publish",
            headers=headers,
            json={"force": False},
        ).json()

        student_id = uuid4()
        SQLiteProfileStore(conn).upsert(LearnerProfile(student_id=student_id, grade_level="7"))
        SQLiteLearnerGoalStore(conn).upsert(
            LearnerGoal(
                goal_id="goal-api",
                student_id=student_id,
                title="Integer fluency",
                target_kc_ids=["KC-2"],
                curriculum_provenance=CurriculumVersionReference(
                    framework_id="math-framework",
                    framework_version="v1",
                    framework_import_id=source_snapshot["framework_import_id"],
                    published_snapshot_id=source_snapshot["snapshot_id"],
                    source_label=source_snapshot["source_label"],
                ),
            )
        )

        diff_response = client.post(
            "/api/admin/curriculum/diffs",
            headers=headers,
            json={
                "source_snapshot_id": source_snapshot["snapshot_id"],
                "target_snapshot_id": target_snapshot["snapshot_id"],
            },
        )
        assert diff_response.status_code == 200
        diff = diff_response.json()

        impact_response = client.post(
            "/api/admin/curriculum/impacts",
            headers=headers,
            json={"diff_id": diff["diff_id"]},
        )
        assert impact_response.status_code == 200
        impacts = impact_response.json()["impacts"]
        assert len(impacts) == 1
        assert impacts[0]["suggested_action"] == "swap_provenance_only"

        plan_response = client.post(
            "/api/admin/curriculum/migration-plans",
            headers=headers,
            json={"diff_id": diff["diff_id"]},
        )
        assert plan_response.status_code == 200
        plan = plan_response.json()
        assert len(plan["actions"]) == 1

        approve_response = client.post(
            f"/api/admin/curriculum/migration-plans/{plan['plan_id']}/approve",
            headers=headers,
            json={"reviewer_id": "admin-user"},
        )
        assert approve_response.status_code == 200
        rollout_policy = client.get(
            "/api/admin/rollout/policy",
            headers=headers,
        ).json()["policy"]
        for gate in rollout_policy["behavior_gates"]:
            if gate["capability"] == "migration_execution":
                gate["mode"] = "approved_low_risk_only"
                break
        rollout_update = client.put(
            "/api/admin/rollout/policy",
            headers=headers,
            json={"policy": rollout_policy},
        )
        assert rollout_update.status_code == 200
        execute_response = client.post(
            f"/api/admin/curriculum/migration-plans/{plan['plan_id']}/execute",
            headers=headers,
            json={"executor_id": "admin-user"},
        )
        assert execute_response.status_code == 200

    migrated_goal = SQLiteLearnerGoalStore(conn).get("goal-api")
    assert migrated_goal is not None
    assert migrated_goal.curriculum_provenance is not None
    assert migrated_goal.curriculum_provenance.published_snapshot_id == target_snapshot["snapshot_id"]


def test_migration_execution_marks_partial_failure_when_runtime_entity_is_missing(tmp_path):
    adapter_v1 = _base_curriculum("curriculum_v1", "v1")
    intake, evolution = _build_harnesses(tmp_path, adapter_v1)
    snapshot = _publish(intake, "curriculum_v1")
    plan = CurriculumMigrationPlan(
        plan_id="plan-missing-goal",
        diff_id="diff-missing-goal",
        source_snapshot_id=snapshot.snapshot_id,
        target_snapshot_id=snapshot.snapshot_id,
        status=MigrationPlanStatus.ready,
        actions=[
            MigrationAction(
                action_id="action-missing-goal",
                action_type=MigrationActionType.swap_provenance_only,
                entity_kind=RuntimeEntityKind.learner_goal,
                entity_id="goal-does-not-exist",
                source_snapshot_id=snapshot.snapshot_id,
                target_snapshot_id=snapshot.snapshot_id,
                risk_level=MigrationRiskLevel.low,
                confidence=0.9,
                status=MigrationActionStatus.approved,
                rationale="Exercise missing-entity recovery.",
            )
        ],
    )
    evolution.curriculum_migration_plan_store.upsert(plan)

    executed = evolution.execute_migration_plan(
        plan.plan_id,
        CurriculumMigrationExecutionRequest(action_ids=["action-missing-goal"]),
    )

    assert executed.status == MigrationPlanStatus.partial_failure
    assert executed.actions[0].status == MigrationActionStatus.execution_failed
    assert "goal missing" in str(executed.actions[0].execution_summary)
