from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID

from dibble.models.curriculum import CurriculumVersionReference
from dibble.models.curriculum_intake import (
    AlignmentEdge,
    AlignmentRelationType,
    AlignmentReviewStatus,
    CurriculumArtifactKind,
    CurriculumChangeKind,
    CurriculumEntityDelta,
    CurriculumEntityRef,
    CurriculumFieldChange,
    CurriculumImpactAnalysis,
    CurriculumImpactAnalysisRequest,
    CurriculumImpactRecord,
    CurriculumMigrationApprovalRequest,
    CurriculumMigrationExecutionRequest,
    CurriculumMigrationExecutionPreview,
    CurriculumMigrationPlan,
    CurriculumMigrationPlanRequest,
    CurriculumSnapshotDiff,
    CurriculumSnapshotDiffRequest,
    MigrationActionExplanationBundle,
    MigrationAction,
    MigrationDryRunAction,
    MigrationActionStatus,
    MigrationActionType,
    MigrationPlanStatus,
    MigrationReviewItem,
    MigrationRiskLevel,
    PublishedCurriculumSnapshot,
    RuntimeEntityKind,
)
from dibble.models.generation import CurriculumLibraryEntry
from dibble.models.observability import HarnessBoundary, OperationalTraceStatus
from dibble.models.planning import TrajectoryRevision
from dibble.models.rollout import MigrationExecutionMode, RolloutCapability
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.rollout_decision_service import RolloutDecisionService
from dibble.services.protocols import (
    AlignmentEdgeStore,
    AssignmentStore,
    ClassroomStore,
    CourseStore,
    CurriculumImpactAnalysisStore,
    CurriculumMigrationPlanStore,
    CurriculumSnapshotDiffStore,
    CurriculumContentLibraryStore,
    FrameworkImportArtifactStore,
    LearnerGoalStore,
    ProfileStore,
    PublishedCurriculumSnapshotStore,
    TrajectoryStore,
)

_LOW_IMPACT_FIELDS: dict[CurriculumArtifactKind, frozenset[str]] = {
    CurriculumArtifactKind.course: frozenset({"title", "subject", "grade_band", "tags"}),
    CurriculumArtifactKind.strand: frozenset(
        {"title", "description", "sort_order", "tags"}
    ),
    CurriculumArtifactKind.outcome: frozenset(
        {"title", "description", "sort_order", "tags"}
    ),
    CurriculumArtifactKind.knowledge_component: frozenset(
        {
            "name",
            "difficulty",
            "estimated_time_minutes",
            "tags",
            "common_misconceptions",
            "nearby_kc_ids",
        }
    ),
}

_TRACKED_FIELDS: dict[CurriculumArtifactKind, tuple[str, ...]] = {
    CurriculumArtifactKind.course: ("title", "subject", "grade_band", "tags"),
    CurriculumArtifactKind.strand: (
        "course_id",
        "parent_strand_id",
        "title",
        "description",
        "sort_order",
        "tags",
    ),
    CurriculumArtifactKind.outcome: (
        "strand_id",
        "title",
        "grade_level",
        "subject",
        "description",
        "knowledge_component_ids",
        "sort_order",
        "tags",
    ),
    CurriculumArtifactKind.knowledge_component: (
        "outcome_id",
        "name",
        "grade_level",
        "subject",
        "taxonomy_cluster_id",
        "concept_family",
        "prerequisite_kc_ids",
        "nearby_kc_ids",
        "difficulty",
        "estimated_time_minutes",
        "tags",
        "common_misconceptions",
    ),
}


class MigrationExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class CurriculumEvolutionHarness:
    published_snapshot_store: PublishedCurriculumSnapshotStore
    framework_import_artifact_store: FrameworkImportArtifactStore
    alignment_edge_store: AlignmentEdgeStore
    curriculum_snapshot_diff_store: CurriculumSnapshotDiffStore
    curriculum_impact_analysis_store: CurriculumImpactAnalysisStore
    curriculum_migration_plan_store: CurriculumMigrationPlanStore
    profile_store: ProfileStore
    learner_goal_store: LearnerGoalStore
    trajectory_store: TrajectoryStore
    assignment_store: AssignmentStore
    classroom_store: ClassroomStore
    course_store: CourseStore
    curriculum_content_library_store: CurriculumContentLibraryStore
    operational_observability_service: OperationalObservabilityService | None = None
    rollout_decision_service: RolloutDecisionService | None = None

    def list_snapshot_diffs(self) -> list[CurriculumSnapshotDiff]:
        return self.curriculum_snapshot_diff_store.list()

    def get_snapshot_diff(self, diff_id: str) -> CurriculumSnapshotDiff | None:
        return self.curriculum_snapshot_diff_store.get(diff_id)

    def list_impact_analyses(self) -> list[CurriculumImpactAnalysis]:
        return self.curriculum_impact_analysis_store.list()

    def list_migration_plans(self) -> list[CurriculumMigrationPlan]:
        return self.curriculum_migration_plan_store.list()

    def create_snapshot_diff(
        self, request: CurriculumSnapshotDiffRequest
    ) -> CurriculumSnapshotDiff:
        existing = self.curriculum_snapshot_diff_store.get_for_snapshots(
            source_snapshot_id=request.source_snapshot_id,
            target_snapshot_id=request.target_snapshot_id,
        )

        source_snapshot = self._require_snapshot(request.source_snapshot_id)
        target_snapshot = self._require_snapshot(request.target_snapshot_id)
        source_artifacts = self._artifacts_for_snapshot(source_snapshot)
        target_artifacts = self._artifacts_for_snapshot(target_snapshot)
        approved_remaps = self._approved_alignment_map(
            source_snapshot_id=source_snapshot.snapshot_id,
            target_snapshot_id=target_snapshot.snapshot_id,
        )
        deltas = self._build_deltas(
            source_snapshot=source_snapshot,
            target_snapshot=target_snapshot,
            source_artifacts=source_artifacts,
            target_artifacts=target_artifacts,
            approved_remaps=approved_remaps,
        )
        now = datetime.now(timezone.utc)
        diff = CurriculumSnapshotDiff(
            diff_id=self._stable_id(
                "diff", source_snapshot.snapshot_id, target_snapshot.snapshot_id
            ),
            source_snapshot_id=source_snapshot.snapshot_id,
            target_snapshot_id=target_snapshot.snapshot_id,
            framework_id=source_snapshot.framework_id,
            source_framework_version=source_snapshot.framework_version,
            target_framework_version=target_snapshot.framework_version,
            entity_deltas=deltas,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        persisted = self.curriculum_snapshot_diff_store.upsert(diff)
        self._record_trace(
            operation="create_snapshot_diff",
            status=OperationalTraceStatus.success,
            summary="Created curriculum snapshot diff for release review.",
            entity_id=persisted.diff_id,
            reason_code="snapshot_diff_created",
            payload={
                "source_snapshot_id": persisted.source_snapshot_id,
                "target_snapshot_id": persisted.target_snapshot_id,
                "delta_count": len(persisted.entity_deltas),
            },
        )
        return persisted

    def analyze_impact(
        self, request: CurriculumImpactAnalysisRequest
    ) -> CurriculumImpactAnalysis:
        existing = self.curriculum_impact_analysis_store.get_for_diff(request.diff_id)
        diff = self._require_diff(request.diff_id)
        delta_by_id = {delta.delta_id: delta for delta in diff.entity_deltas}
        changed_outcome_ids = {
            delta.before.artifact_id
            for delta in diff.entity_deltas
            if delta.before is not None
            and delta.before.artifact_kind == CurriculumArtifactKind.outcome
            and delta.change_kind != CurriculumChangeKind.added
        }
        changed_kc_ids = {
            delta.before.artifact_id
            for delta in diff.entity_deltas
            if delta.before is not None
            and delta.before.artifact_kind == CurriculumArtifactKind.knowledge_component
            and delta.change_kind != CurriculumChangeKind.added
        }
        changed_course_ids = {
            delta.before.artifact_id
            for delta in diff.entity_deltas
            if delta.before is not None
            and delta.before.artifact_kind == CurriculumArtifactKind.course
            and delta.change_kind != CurriculumChangeKind.added
        }
        source_snapshot_id = diff.source_snapshot_id
        impacts: list[CurriculumImpactRecord] = []
        for student_id in self.profile_store.list_ids():
            try:
                learner_id = UUID(student_id)
            except ValueError:
                continue
            goal = self.learner_goal_store.get_active_for_student(student_id=learner_id)
            if (
                goal is not None
                and goal.curriculum_provenance is not None
                and goal.curriculum_provenance.published_snapshot_id == source_snapshot_id
            ):
                outcome_ids = list(goal.target_outcome_ids)
                if goal.target_outcome_id is not None:
                    outcome_ids.append(goal.target_outcome_id)
                matched = self._matched_delta_ids(
                    diff=diff,
                    outcome_ids=outcome_ids,
                    kc_ids=goal.target_kc_ids,
                )
                if matched:
                    action, risk, confidence, rationale = self._suggest_action(
                        entity_kind=RuntimeEntityKind.learner_goal,
                        delta_ids=matched,
                        delta_by_id=delta_by_id,
                    )
                    impacts.append(
                        CurriculumImpactRecord(
                            impact_id=self._stable_id("impact", "goal", goal.goal_id),
                            entity_kind=RuntimeEntityKind.learner_goal,
                            entity_id=goal.goal_id,
                            student_id=student_id,
                            current_snapshot_id=source_snapshot_id,
                            referenced_outcome_ids=sorted(
                                set(outcome_ids) & changed_outcome_ids
                            ),
                            referenced_kc_ids=sorted(
                                set(goal.target_kc_ids) & changed_kc_ids
                            ),
                            matched_delta_ids=matched,
                            suggested_action=action,
                            confidence=confidence,
                            risk_level=risk,
                            rationale=rationale,
                        )
                    )
            trajectory = self.trajectory_store.get_active_for_student(student_id=learner_id)
            if (
                trajectory is not None
                and trajectory.curriculum_provenance is not None
                and trajectory.curriculum_provenance.published_snapshot_id
                == source_snapshot_id
            ):
                trajectory_outcome_ids = [
                    node.outcome_id for node in trajectory.nodes if node.outcome_id
                ]
                trajectory_kc_ids: list[str] = []
                for node in trajectory.nodes:
                    trajectory_kc_ids.extend(node.target_kc_ids)
                    trajectory_kc_ids.extend(node.ordered_kc_ids)
                    trajectory_kc_ids.extend(node.bridge_kc_ids)
                    trajectory_kc_ids.extend(node.deferred_target_kc_ids)
                    trajectory_kc_ids.extend(node.transfer_target_kc_ids)
                matched = self._matched_delta_ids(
                    diff=diff,
                    outcome_ids=trajectory_outcome_ids,
                    kc_ids=trajectory_kc_ids,
                )
                if matched:
                    action, risk, confidence, rationale = self._suggest_action(
                        entity_kind=RuntimeEntityKind.trajectory,
                        delta_ids=matched,
                        delta_by_id=delta_by_id,
                    )
                    impacts.append(
                        CurriculumImpactRecord(
                            impact_id=self._stable_id(
                                "impact", "trajectory", trajectory.trajectory_id
                            ),
                            entity_kind=RuntimeEntityKind.trajectory,
                            entity_id=trajectory.trajectory_id,
                            student_id=student_id,
                            current_snapshot_id=source_snapshot_id,
                            referenced_outcome_ids=sorted(
                                set(trajectory_outcome_ids) & changed_outcome_ids
                            ),
                            referenced_kc_ids=sorted(
                                set(trajectory_kc_ids) & changed_kc_ids
                            ),
                            matched_delta_ids=matched,
                            suggested_action=action,
                            confidence=confidence,
                            risk_level=risk,
                            rationale=rationale,
                        )
                    )

        for assignment in self.assignment_store.list():
            matched = self._matched_delta_ids(
                diff=diff,
                outcome_ids=assignment.target_lo_ids,
                kc_ids=assignment.target_kc_ids,
            )
            if not matched:
                continue
            action, risk, confidence, rationale = self._suggest_action(
                entity_kind=RuntimeEntityKind.assignment,
                delta_ids=matched,
                delta_by_id=delta_by_id,
            )
            impacts.append(
                CurriculumImpactRecord(
                    impact_id=self._stable_id(
                        "impact", "assignment", assignment.assignment_id
                    ),
                    entity_kind=RuntimeEntityKind.assignment,
                    entity_id=assignment.assignment_id,
                    student_id=assignment.student_id,
                    referenced_outcome_ids=sorted(
                        set(assignment.target_lo_ids) & changed_outcome_ids
                    ),
                    referenced_kc_ids=sorted(
                        set(assignment.target_kc_ids) & changed_kc_ids
                    ),
                    matched_delta_ids=matched,
                    suggested_action=action,
                    confidence=confidence,
                    risk_level=risk,
                    rationale=rationale,
                )
            )

        for entry in self.curriculum_content_library_store.list_entries():
            snapshot_id = (
                entry.provenance.curriculum_provenance.published_snapshot_id
                if entry.provenance is not None
                and entry.provenance.curriculum_provenance is not None
                else entry.content_key.request.curriculum_provenance.published_snapshot_id
                if entry.content_key.request.curriculum_provenance is not None
                else None
            )
            if snapshot_id != source_snapshot_id:
                continue
            matched = self._matched_delta_ids(
                diff=diff,
                outcome_ids=entry.content_key.request.target_lo_ids,
                kc_ids=entry.content_key.request.target_kc_ids,
            )
            if not matched:
                continue
            action, risk, confidence, rationale = self._suggest_action(
                entity_kind=RuntimeEntityKind.library_artifact,
                delta_ids=matched,
                delta_by_id=delta_by_id,
            )
            impacts.append(
                CurriculumImpactRecord(
                    impact_id=self._stable_id("impact", "library", entry.cache_key or ""),
                    entity_kind=RuntimeEntityKind.library_artifact,
                    entity_id=entry.cache_key or "",
                    current_snapshot_id=snapshot_id,
                    referenced_outcome_ids=sorted(
                        set(entry.content_key.request.target_lo_ids) & changed_outcome_ids
                    ),
                    referenced_kc_ids=sorted(
                        set(entry.content_key.request.target_kc_ids) & changed_kc_ids
                    ),
                    matched_delta_ids=matched,
                    suggested_action=action,
                    confidence=confidence,
                    risk_level=risk,
                    rationale=rationale,
                )
            )

        for course in self.course_store.list():
            if (
                course.curriculum_provenance is None
                or course.curriculum_provenance.published_snapshot_id != source_snapshot_id
                or course.course_id not in changed_course_ids
            ):
                continue
            matched = self._matched_delta_ids(
                diff=diff,
                course_ids=[course.course_id],
            )
            action, risk, confidence, rationale = self._suggest_action(
                entity_kind=RuntimeEntityKind.course,
                delta_ids=matched,
                delta_by_id=delta_by_id,
            )
            impacts.append(
                CurriculumImpactRecord(
                    impact_id=self._stable_id("impact", "course", course.course_id),
                    entity_kind=RuntimeEntityKind.course,
                    entity_id=course.course_id,
                    current_snapshot_id=source_snapshot_id,
                    referenced_course_ids=[course.course_id],
                    matched_delta_ids=matched,
                    suggested_action=action,
                    confidence=confidence,
                    risk_level=risk,
                    rationale=rationale,
                )
            )
            for section in self.classroom_store.list():
                if section.course_id != course.course_id:
                    continue
                impacts.append(
                    CurriculumImpactRecord(
                        impact_id=self._stable_id(
                            "impact", "section", section.classroom_id
                        ),
                        entity_kind=RuntimeEntityKind.section,
                        entity_id=section.classroom_id,
                        current_snapshot_id=source_snapshot_id,
                        referenced_course_ids=[course.course_id],
                        matched_delta_ids=matched,
                        suggested_action=MigrationActionType.keep_pinned,
                        confidence=0.35,
                        risk_level=MigrationRiskLevel.high,
                        rationale=(
                            "Section course association points at a changed course and"
                            " should stay pinned until reviewed."
                        ),
                    )
                )

        now = datetime.now(timezone.utc)
        analysis = CurriculumImpactAnalysis(
            analysis_id=self._stable_id("impact-analysis", diff.diff_id),
            diff_id=diff.diff_id,
            source_snapshot_id=diff.source_snapshot_id,
            target_snapshot_id=diff.target_snapshot_id,
            impacts=sorted(impacts, key=lambda item: (item.entity_kind.value, item.entity_id)),
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        persisted = self.curriculum_impact_analysis_store.upsert(analysis)
        self._record_trace(
            operation="analyze_impact",
            status=OperationalTraceStatus.success,
            summary="Analyzed runtime impact of curriculum changes.",
            entity_id=persisted.analysis_id,
            reason_code="impact_analysis_created",
            payload={
                "diff_id": persisted.diff_id,
                "impact_count": len(persisted.impacts),
            },
        )
        return persisted

    def create_migration_plan(
        self, request: CurriculumMigrationPlanRequest
    ) -> CurriculumMigrationPlan:
        existing = self.curriculum_migration_plan_store.get_for_diff(request.diff_id)
        if existing is not None:
            return existing

        diff = self._require_diff(request.diff_id)
        analysis = self.curriculum_impact_analysis_store.get_for_diff(diff.diff_id)
        if analysis is None:
            analysis = self.analyze_impact(CurriculumImpactAnalysisRequest(diff_id=diff.diff_id))
        delta_by_id = {delta.delta_id: delta for delta in diff.entity_deltas}
        actions: list[MigrationAction] = []
        review_items: list[MigrationReviewItem] = []
        for impact in analysis.impacts:
            outcome_targets = self._remap_targets(
                delta_ids=impact.matched_delta_ids,
                delta_by_id=delta_by_id,
                artifact_kind=CurriculumArtifactKind.outcome,
            )
            kc_targets = self._remap_targets(
                delta_ids=impact.matched_delta_ids,
                delta_by_id=delta_by_id,
                artifact_kind=CurriculumArtifactKind.knowledge_component,
            )
            status = (
                MigrationActionStatus.review_required
                if impact.risk_level != MigrationRiskLevel.low
                else MigrationActionStatus.draft
            )
            action = MigrationAction(
                action_id=self._stable_id(
                    "migration-action", impact.entity_kind.value, impact.entity_id
                ),
                action_type=impact.suggested_action,
                entity_kind=impact.entity_kind,
                entity_id=impact.entity_id,
                source_snapshot_id=analysis.source_snapshot_id,
                target_snapshot_id=analysis.target_snapshot_id,
                source_outcome_ids=list(impact.referenced_outcome_ids),
                target_outcome_ids=outcome_targets["targets"],
                source_kc_ids=list(impact.referenced_kc_ids),
                target_kc_ids=kc_targets["targets"],
                approved_alignment_edge_ids=sorted(
                    set(outcome_targets["edges"] + kc_targets["edges"])
                ),
                risk_level=impact.risk_level,
                confidence=impact.confidence,
                status=status,
                rationale=impact.rationale,
            )
            actions.append(action)
            if status == MigrationActionStatus.review_required:
                review_items.append(
                    MigrationReviewItem(
                        review_item_id=self._stable_id(
                            "migration-review",
                            impact.entity_kind.value,
                            impact.entity_id,
                        ),
                        entity_kind=impact.entity_kind,
                        entity_id=impact.entity_id,
                        risk_level=impact.risk_level,
                        blocking_delta_ids=list(impact.matched_delta_ids),
                        recommended_action=impact.suggested_action,
                        rationale=impact.rationale,
                    )
                )
        now = datetime.now(timezone.utc)
        plan = CurriculumMigrationPlan(
            plan_id=self._stable_id("migration-plan", analysis.diff_id),
            diff_id=analysis.diff_id,
            source_snapshot_id=analysis.source_snapshot_id,
            target_snapshot_id=analysis.target_snapshot_id,
            status=MigrationPlanStatus.draft,
            actions=actions,
            review_items=review_items,
            created_at=now,
            updated_at=now,
        )
        persisted = self.curriculum_migration_plan_store.upsert(plan)
        self._record_trace(
            operation="create_migration_plan",
            status=OperationalTraceStatus.success,
            summary="Created a curriculum migration plan from the latest impact analysis.",
            entity_id=persisted.plan_id,
            reason_code="migration_plan_created",
            payload={
                "diff_id": persisted.diff_id,
                "action_count": len(persisted.actions),
                "review_item_count": len(persisted.review_items),
            },
        )
        return persisted

    def approve_migration_plan(
        self, plan_id: str, request: CurriculumMigrationApprovalRequest
    ) -> CurriculumMigrationPlan:
        plan = self._require_plan(plan_id)
        selected_action_ids = set(request.action_ids)
        now = datetime.now(timezone.utc)
        updated_actions: list[MigrationAction] = []
        for action in plan.actions:
            is_selected = not selected_action_ids or action.action_id in selected_action_ids
            if (
                is_selected
                and action.status == MigrationActionStatus.draft
                and (
                    request.approve_all_low_risk
                    or action.action_id in selected_action_ids
                )
                and action.risk_level == MigrationRiskLevel.low
            ):
                updated_actions.append(
                    action.model_copy(
                        update={
                            "status": MigrationActionStatus.approved,
                            "reviewer_id": request.reviewer_id,
                            "approved_at": now,
                        }
                    )
                )
                continue
            updated_actions.append(action)
        next_status = (
            MigrationPlanStatus.ready
            if any(action.status == MigrationActionStatus.approved for action in updated_actions)
            else plan.status
        )
        updated_plan = plan.model_copy(
            update={
                "status": next_status,
                "actions": updated_actions,
                "updated_at": now,
            }
        )
        persisted = self.curriculum_migration_plan_store.upsert(updated_plan)
        self._record_trace(
            operation="approve_migration_plan",
            status=OperationalTraceStatus.success,
            summary="Approved low-risk curriculum migration actions for execution.",
            entity_id=persisted.plan_id,
            reason_code="migration_plan_approved",
            payload={
                "approved_action_count": sum(
                    1 for action in persisted.actions if action.status == MigrationActionStatus.approved
                ),
                "plan_status": (
                    persisted.status.value
                    if hasattr(persisted.status, "value")
                    else str(persisted.status)
                ),
            },
        )
        return persisted

    def execute_migration_plan(
        self, plan_id: str, request: CurriculumMigrationExecutionRequest
    ) -> CurriculumMigrationPlan:
        plan = self._require_plan(plan_id)
        decision = (
            self.rollout_decision_service.decision_for(
                capability=RolloutCapability.migration_execution
            )
            if self.rollout_decision_service is not None
            else None
        )
        if (
            decision is not None
            and decision.mode == MigrationExecutionMode.manual_only.value
        ):
            self._record_trace(
                operation="execute_migration_plan",
                status=OperationalTraceStatus.success,
                summary="Skipped curriculum migration execution because rollout policy requires manual review.",
                entity_id=plan.plan_id,
                reason_code="migration_execution_blocked_by_rollout",
                payload={
                    "plan_status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
                    "rollout_bucket_id": decision.evaluation_bucket_id,
                    "rollout_mode": decision.mode,
                },
            )
            return plan
        selected_action_ids = set(request.action_ids)
        target_snapshot = self._require_snapshot(plan.target_snapshot_id)
        target_provenance = self._snapshot_provenance(target_snapshot)
        updated_actions: list[MigrationAction] = []
        now = datetime.now(timezone.utc)
        failed_action_count = 0
        for action in plan.actions:
            is_selected = not selected_action_ids or action.action_id in selected_action_ids
            if (
                not is_selected
                or action.status != MigrationActionStatus.approved
                or action.risk_level != MigrationRiskLevel.low
            ):
                updated_actions.append(action)
                continue
            try:
                summary = self._execute_action(
                    action=action,
                    target_provenance=target_provenance,
                )
            except MigrationExecutionError as exc:
                failed_action_count += 1
                updated_actions.append(
                    action.model_copy(
                        update={
                            "status": MigrationActionStatus.execution_failed,
                            "executed_at": now,
                            "execution_summary": str(exc),
                        }
                    )
                )
                continue
            updated_actions.append(
                action.model_copy(
                    update={
                        "status": MigrationActionStatus.executed,
                        "executed_at": now,
                        "execution_summary": summary,
                    }
                )
            )
        next_status = plan.status
        if failed_action_count > 0:
            next_status = MigrationPlanStatus.partial_failure
        elif not any(
            action.status == MigrationActionStatus.approved for action in updated_actions
        ):
            next_status = MigrationPlanStatus.executed
        updated_plan = plan.model_copy(
            update={
                "status": next_status,
                "actions": updated_actions,
                "updated_at": now,
            }
        )
        persisted = self.curriculum_migration_plan_store.upsert(updated_plan)
        self._record_trace(
            operation="execute_migration_plan",
            status=(
                OperationalTraceStatus.degraded
                if failed_action_count > 0
                else OperationalTraceStatus.success
            ),
            summary=(
                "Executed curriculum migration plan with partial failures."
                if failed_action_count > 0
                else "Executed curriculum migration plan."
            ),
            entity_id=persisted.plan_id,
            degraded_mode=failed_action_count > 0,
            degraded_reason=(
                f"{failed_action_count} action(s) failed during execution."
                if failed_action_count > 0
                else None
            ),
            reason_code=(
                "migration_plan_partial_failure"
                if failed_action_count > 0
                else "migration_plan_executed"
            ),
            payload={
                "plan_status": (
                    persisted.status.value
                    if hasattr(persisted.status, "value")
                    else str(persisted.status)
                ),
                "executed_action_count": sum(
                    1 for action in persisted.actions if action.status == MigrationActionStatus.executed
                ),
                "failed_action_count": failed_action_count,
            },
        )
        return persisted

    def preview_migration_execution(
        self,
        plan_id: str,
        request: CurriculumMigrationExecutionRequest,
    ) -> CurriculumMigrationExecutionPreview:
        plan = self._require_plan(plan_id)
        decision = (
            self.rollout_decision_service.decision_for(
                capability=RolloutCapability.migration_execution
            )
            if self.rollout_decision_service is not None
            else None
        )
        if (
            decision is not None
            and decision.mode == MigrationExecutionMode.manual_only.value
        ):
            return CurriculumMigrationExecutionPreview(
                plan_id=plan.plan_id,
                diff_id=plan.diff_id,
                rollout_blocked=True,
                rollout_reason=(
                    "Rollout policy keeps migration execution in manual-only mode, "
                    "so no approved action would run."
                ),
            )
        selected_action_ids = set(request.action_ids)
        target_snapshot = self._require_snapshot(plan.target_snapshot_id)
        target_provenance = self._snapshot_provenance(target_snapshot)
        action_previews: list[MigrationDryRunAction] = []
        executed_action_count = 0
        blocked_action_count = 0
        for action in plan.actions:
            is_selected = not selected_action_ids or action.action_id in selected_action_ids
            would_execute = (
                is_selected
                and action.status == MigrationActionStatus.approved
                and action.risk_level == MigrationRiskLevel.low
            )
            if not would_execute:
                blocked_action_count += 1
                action_previews.append(
                    MigrationDryRunAction(
                        action_id=action.action_id,
                        would_execute=False,
                        status=action.status.value,
                        summary="This action would remain unchanged in dry-run mode.",
                        explanation=self._migration_action_explanation(
                            action=action,
                            decision=decision,
                            next_expected_consequence=(
                                "The action is still blocked until it is approved, "
                                "selected, and classified as low risk."
                            ),
                        ),
                    )
                )
                continue
            executed_action_count += 1
            try:
                summary = self._execute_action(
                    action=action,
                    target_provenance=target_provenance,
                    dry_run=True,
                )
            except MigrationExecutionError as exc:
                blocked_action_count += 1
                action_previews.append(
                    MigrationDryRunAction(
                        action_id=action.action_id,
                        would_execute=False,
                        status=MigrationActionStatus.execution_failed.value,
                        summary=str(exc),
                        explanation=self._migration_action_explanation(
                            action=action,
                            decision=decision,
                            next_expected_consequence="Execution would still fail until the missing runtime entity is repaired.",
                        ),
                    )
                )
                continue
            action_previews.append(
                MigrationDryRunAction(
                    action_id=action.action_id,
                    would_execute=True,
                    status="dry_run",
                    summary=summary,
                    explanation=self._migration_action_explanation(
                        action=action,
                        decision=decision,
                        next_expected_consequence=summary,
                    ),
                )
            )
        return CurriculumMigrationExecutionPreview(
            plan_id=plan.plan_id,
            diff_id=plan.diff_id,
            action_previews=action_previews,
            executed_action_count=executed_action_count,
            blocked_action_count=blocked_action_count,
        )

    def _execute_action(
        self,
        *,
        action: MigrationAction,
        target_provenance: CurriculumVersionReference,
        dry_run: bool = False,
    ) -> str:
        if action.action_type == MigrationActionType.keep_pinned:
            return (
                "would leave the entity pinned to the source snapshot"
                if dry_run
                else "left pinned to the source snapshot"
            )
        if action.entity_kind == RuntimeEntityKind.learner_goal:
            return self._execute_goal_action(
                action=action,
                target_provenance=target_provenance,
                dry_run=dry_run,
            )
        if action.entity_kind == RuntimeEntityKind.trajectory:
            return self._execute_trajectory_action(
                action=action,
                target_provenance=target_provenance,
                dry_run=dry_run,
            )
        if action.entity_kind == RuntimeEntityKind.assignment:
            return self._execute_assignment_action(action=action, dry_run=dry_run)
        if action.entity_kind == RuntimeEntityKind.library_artifact:
            return self._execute_library_action(
                action=action,
                target_provenance=target_provenance,
                dry_run=dry_run,
            )
        return (
            "would keep the action for manual review because no supported execution path exists"
            if dry_run
            else "no supported execution path; kept for review"
        )

    def _execute_goal_action(
        self,
        *,
        action: MigrationAction,
        target_provenance: CurriculumVersionReference,
        dry_run: bool = False,
    ) -> str:
        goal = self.learner_goal_store.get(action.entity_id)
        if goal is None:
            raise MigrationExecutionError("goal missing; no mutation applied")
        now = datetime.now(timezone.utc)
        outcome_map = dict(zip(action.source_outcome_ids, action.target_outcome_ids))
        kc_map = dict(zip(action.source_kc_ids, action.target_kc_ids))
        updated = goal
        if action.action_type == MigrationActionType.swap_provenance_only:
            updated = goal.model_copy(
                update={
                    "curriculum_provenance": target_provenance,
                    "updated_at": now,
                }
            )
        elif action.action_type == MigrationActionType.remap_via_alignment:
            updated = goal.model_copy(
                update={
                    "target_outcome_id": outcome_map.get(
                        goal.target_outcome_id, goal.target_outcome_id
                    ),
                    "target_outcome_ids": [
                        outcome_map.get(outcome_id, outcome_id)
                        for outcome_id in goal.target_outcome_ids
                    ],
                    "target_kc_ids": [
                        kc_map.get(kc_id, kc_id) for kc_id in goal.target_kc_ids
                    ],
                    "curriculum_provenance": target_provenance,
                    "updated_at": now,
                }
            )
        if not dry_run:
            self.learner_goal_store.upsert(updated)
        return (
            f"would update goal {goal.goal_id}"
            if dry_run
            else f"updated goal {goal.goal_id}"
        )

    def _execute_trajectory_action(
        self,
        *,
        action: MigrationAction,
        target_provenance: CurriculumVersionReference,
        dry_run: bool = False,
    ) -> str:
        trajectory = self.trajectory_store.get(action.entity_id)
        if trajectory is None:
            raise MigrationExecutionError("trajectory missing; no mutation applied")
        now = datetime.now(timezone.utc)
        outcome_map = dict(zip(action.source_outcome_ids, action.target_outcome_ids))
        kc_map = dict(zip(action.source_kc_ids, action.target_kc_ids))
        updated_nodes = []
        for node in trajectory.nodes:
            updated_nodes.append(
                node.model_copy(
                    update={
                        "outcome_id": outcome_map.get(node.outcome_id, node.outcome_id),
                        "target_kc_ids": [kc_map.get(kc_id, kc_id) for kc_id in node.target_kc_ids],
                        "ordered_kc_ids": [kc_map.get(kc_id, kc_id) for kc_id in node.ordered_kc_ids],
                        "bridge_kc_ids": [kc_map.get(kc_id, kc_id) for kc_id in node.bridge_kc_ids],
                        "deferred_target_kc_ids": [
                            kc_map.get(kc_id, kc_id) for kc_id in node.deferred_target_kc_ids
                        ],
                        "transfer_target_kc_ids": [
                            kc_map.get(kc_id, kc_id) for kc_id in node.transfer_target_kc_ids
                        ],
                        "status": (
                            "replan_required"
                            if action.action_type
                            == MigrationActionType.mark_trajectory_for_replanning
                            and (
                                node.outcome_id in action.source_outcome_ids
                                or bool(set(node.target_kc_ids) & set(action.source_kc_ids))
                            )
                            else node.status
                        ),
                    }
                )
            )
        updated_checkpoints = [
            checkpoint.model_copy(
                update={
                    "mastery_focus_kc_ids": [
                        kc_map.get(kc_id, kc_id)
                        for kc_id in checkpoint.mastery_focus_kc_ids
                    ]
                }
            )
            for checkpoint in trajectory.checkpoints
        ]
        revision = TrajectoryRevision(
            revision_id=self._stable_id(
                "trajectory-migration", trajectory.trajectory_id, now.isoformat()
            ),
            revision_number=len(trajectory.revisions) + 1,
            revision_kind=(
                "curriculum_replan_required"
                if action.action_type == MigrationActionType.mark_trajectory_for_replanning
                else "curriculum_migrated"
            ),
            rationale=action.rationale,
            previous_active_node_id=trajectory.active_node_id,
            active_node_id=trajectory.active_node_id,
            node_count=len(updated_nodes),
        )
        updated = trajectory.model_copy(
            update={
                "curriculum_provenance": (
                    target_provenance
                    if action.action_type != MigrationActionType.mark_trajectory_for_replanning
                    else trajectory.curriculum_provenance
                ),
                "nodes": updated_nodes,
                "checkpoints": updated_checkpoints,
                "revisions": [*trajectory.revisions, revision],
                "updated_at": now,
            }
        )
        if not dry_run:
            self.trajectory_store.upsert(updated)
        return (
            f"would update trajectory {trajectory.trajectory_id}"
            if dry_run
            else f"updated trajectory {trajectory.trajectory_id}"
        )

    def _execute_assignment_action(
        self,
        *,
        action: MigrationAction,
        dry_run: bool = False,
    ) -> str:
        assignment = self.assignment_store.get(action.entity_id)
        if assignment is None:
            raise MigrationExecutionError("assignment missing; no mutation applied")
        outcome_map = dict(zip(action.source_outcome_ids, action.target_outcome_ids))
        kc_map = dict(zip(action.source_kc_ids, action.target_kc_ids))
        updated = assignment.model_copy(
            update={
                "target_lo_ids": [
                    outcome_map.get(outcome_id, outcome_id)
                    for outcome_id in assignment.target_lo_ids
                ],
                "target_kc_ids": [
                    kc_map.get(kc_id, kc_id) for kc_id in assignment.target_kc_ids
                ],
                "updated_at": datetime.now(timezone.utc),
            }
        )
        if not dry_run:
            self.assignment_store.upsert(updated)
        return (
            f"would update assignment {assignment.assignment_id}"
            if dry_run
            else f"updated assignment {assignment.assignment_id}"
        )

    def _execute_library_action(
        self,
        *,
        action: MigrationAction,
        target_provenance: CurriculumVersionReference,
        dry_run: bool = False,
    ) -> str:
        entries = {
            entry.cache_key: entry
            for entry in self.curriculum_content_library_store.list_entries(
                include_expired=True
            )
        }
        entry = entries.get(action.entity_id)
        if entry is None:
            raise MigrationExecutionError("library artifact missing; no mutation applied")
        now = datetime.now(timezone.utc)
        if action.action_type == MigrationActionType.invalidate_library_artifact:
            expired = entry.model_copy(
                update={
                    "content": entry.content.model_copy(update={"expires_at": now}),
                }
            )
            if not dry_run:
                self.curriculum_content_library_store.upsert_entry(entry=expired)
            return (
                f"would expire library artifact {action.entity_id}"
                if dry_run
                else f"expired library artifact {action.entity_id}"
            )

        outcome_map = dict(zip(action.source_outcome_ids, action.target_outcome_ids))
        kc_map = dict(zip(action.source_kc_ids, action.target_kc_ids))
        request = entry.content_key.request.model_copy(
            update={
                "target_lo_ids": [
                    outcome_map.get(outcome_id, outcome_id)
                    for outcome_id in entry.content_key.request.target_lo_ids
                ],
                "target_kc_ids": [
                    kc_map.get(kc_id, kc_id)
                    for kc_id in entry.content_key.request.target_kc_ids
                ],
                "curriculum_provenance": target_provenance,
            }
        )
        grounding = [
            reference.model_copy(
                update={
                    "outcome_id": outcome_map.get(reference.outcome_id, reference.outcome_id),
                    "curriculum_provenance": target_provenance,
                }
            )
            for reference in entry.content_key.grounding
        ]
        next_provenance = (
            entry.provenance.model_copy(update={"curriculum_provenance": target_provenance})
            if entry.provenance is not None
            else None
        )
        migrated = CurriculumLibraryEntry(
            content_key=entry.content_key.model_copy(
                update={"request": request, "grounding": grounding}
            ),
            content=entry.content,
            provenance=next_provenance,
            storage_scope=entry.storage_scope,
            source_generation_id=entry.source_generation_id,
        )
        if not dry_run:
            self.curriculum_content_library_store.upsert_entry(entry=migrated)
        expired = entry.model_copy(
            update={
                "content": entry.content.model_copy(update={"expires_at": now}),
            }
        )
        if not dry_run:
            self.curriculum_content_library_store.upsert_entry(entry=expired)
        return (
            f"would migrate library artifact {action.entity_id}"
            if dry_run
            else f"migrated library artifact {action.entity_id}"
        )

    def _migration_action_explanation(
        self,
        *,
        action: MigrationAction,
        decision,
        next_expected_consequence: str,
    ) -> MigrationActionExplanationBundle:
        fallback_behavior = (
            decision.fallback_behavior if decision is not None and not decision.enabled else None
        )
        return MigrationActionExplanationBundle(
            action_id=action.action_id,
            entity_kind=action.entity_kind,
            entity_id=action.entity_id,
            action_type=action.action_type,
            risk_level=action.risk_level,
            confidence=action.confidence,
            rationale=action.rationale,
            rollout_effect=decision,
            fallback_behavior=fallback_behavior,
            next_expected_consequence=next_expected_consequence,
        )

    def _record_trace(
        self,
        *,
        operation: str,
        status: OperationalTraceStatus,
        summary: str,
        entity_id: str | None = None,
        degraded_mode: bool = False,
        degraded_reason: str | None = None,
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
            entity_kind="curriculum_migration_plan",
            entity_id=entity_id,
            degraded_mode=degraded_mode,
            degraded_reason=degraded_reason,
            reason_code=reason_code,
            payload=payload,
        )

    def _matched_delta_ids(
        self,
        *,
        diff: CurriculumSnapshotDiff,
        outcome_ids: list[str] | None = None,
        kc_ids: list[str] | None = None,
        course_ids: list[str] | None = None,
    ) -> list[str]:
        outcome_set = set(outcome_ids or [])
        kc_set = set(kc_ids or [])
        course_set = set(course_ids or [])
        matched: list[str] = []
        for delta in diff.entity_deltas:
            before = delta.before
            if before is None:
                continue
            if (
                before.artifact_kind == CurriculumArtifactKind.outcome
                and before.artifact_id in outcome_set
            ):
                matched.append(delta.delta_id)
            elif (
                before.artifact_kind == CurriculumArtifactKind.knowledge_component
                and before.artifact_id in kc_set
            ):
                matched.append(delta.delta_id)
            elif (
                before.artifact_kind == CurriculumArtifactKind.course
                and before.artifact_id in course_set
            ):
                matched.append(delta.delta_id)
        return sorted(set(matched))

    def _suggest_action(
        self,
        *,
        entity_kind: RuntimeEntityKind,
        delta_ids: list[str],
        delta_by_id: dict[str, CurriculumEntityDelta],
    ) -> tuple[MigrationActionType, MigrationRiskLevel, float, str]:
        deltas = [delta_by_id[delta_id] for delta_id in delta_ids]
        if all(delta.change_kind == CurriculumChangeKind.remapped for delta in deltas):
            return (
                MigrationActionType.remap_via_alignment,
                MigrationRiskLevel.low,
                0.95,
                "Every affected curriculum reference has an approved equivalent alignment.",
            )
        if entity_kind == RuntimeEntityKind.library_artifact and all(
            delta.suggested_action == MigrationActionType.swap_provenance_only
            for delta in deltas
        ):
            return (
                MigrationActionType.swap_provenance_only,
                MigrationRiskLevel.low,
                0.9,
                "Only low-risk metadata changed, so the artifact can keep its content and update provenance.",
            )
        if entity_kind == RuntimeEntityKind.trajectory and all(
            delta.change_kind
            in {
                CurriculumChangeKind.changed,
                CurriculumChangeKind.prerequisite_changed,
            }
            for delta in deltas
        ):
            return (
                MigrationActionType.mark_trajectory_for_replanning,
                MigrationRiskLevel.low,
                0.8,
                "The safest automatic step is to mark the active trajectory for replanning.",
            )
        if entity_kind == RuntimeEntityKind.library_artifact:
            return (
                MigrationActionType.invalidate_library_artifact,
                MigrationRiskLevel.low,
                0.8,
                "Affected curriculum content should be invalidated rather than silently reused.",
            )
        if all(
            delta.suggested_action == MigrationActionType.swap_provenance_only
            for delta in deltas
        ):
            return (
                MigrationActionType.swap_provenance_only,
                MigrationRiskLevel.low,
                0.85,
                "Affected entities can safely update provenance without changing targets.",
            )
        return (
            MigrationActionType.keep_pinned,
            MigrationRiskLevel.high,
            0.35,
            "The curriculum change is ambiguous or risky, so the runtime entity should remain pinned for review.",
        )

    def _build_deltas(
        self,
        *,
        source_snapshot: PublishedCurriculumSnapshot,
        target_snapshot: PublishedCurriculumSnapshot,
        source_artifacts: dict[tuple[CurriculumArtifactKind, str], dict[str, object]],
        target_artifacts: dict[tuple[CurriculumArtifactKind, str], dict[str, object]],
        approved_remaps: dict[tuple[CurriculumArtifactKind, str], tuple[str, str]],
    ) -> list[CurriculumEntityDelta]:
        deltas: list[CurriculumEntityDelta] = []
        keys = sorted(
            set(source_artifacts) | set(target_artifacts),
            key=lambda item: (item[0].value, item[1]),
        )
        for kind, artifact_id in keys:
            source_payload = source_artifacts.get((kind, artifact_id))
            target_payload = target_artifacts.get((kind, artifact_id))
            before = (
                CurriculumEntityRef(
                    snapshot_id=source_snapshot.snapshot_id,
                    framework_id=source_snapshot.framework_id,
                    framework_version=source_snapshot.framework_version,
                    artifact_kind=kind,
                    artifact_id=artifact_id,
                    title=self._artifact_title(kind, source_payload),
                )
                if source_payload is not None
                else None
            )
            after = (
                CurriculumEntityRef(
                    snapshot_id=target_snapshot.snapshot_id,
                    framework_id=target_snapshot.framework_id,
                    framework_version=target_snapshot.framework_version,
                    artifact_kind=kind,
                    artifact_id=artifact_id,
                    title=self._artifact_title(kind, target_payload),
                )
                if target_payload is not None
                else None
            )
            if source_payload is None and target_payload is not None:
                deltas.append(
                    CurriculumEntityDelta(
                        delta_id=self._stable_id(
                            "delta",
                            source_snapshot.snapshot_id,
                            target_snapshot.snapshot_id,
                            kind.value,
                            artifact_id,
                            "added",
                        ),
                        artifact_kind=kind,
                        artifact_id=artifact_id,
                        change_kind=CurriculumChangeKind.added,
                        risk_level=MigrationRiskLevel.low,
                        after=after,
                        rationale="Entity is new in the target snapshot.",
                    )
                )
                continue
            if source_payload is not None and target_payload is None:
                remap = approved_remaps.get((kind, artifact_id))
                if remap is not None:
                    remapped_id, edge_id = remap
                    remapped_payload = target_artifacts.get((kind, remapped_id))
                    deltas.append(
                        CurriculumEntityDelta(
                            delta_id=self._stable_id(
                                "delta",
                                source_snapshot.snapshot_id,
                                target_snapshot.snapshot_id,
                                kind.value,
                                artifact_id,
                                "remapped",
                            ),
                            artifact_kind=kind,
                            artifact_id=artifact_id,
                            change_kind=CurriculumChangeKind.remapped,
                            risk_level=MigrationRiskLevel.low,
                            before=before,
                            after=CurriculumEntityRef(
                                snapshot_id=target_snapshot.snapshot_id,
                                framework_id=target_snapshot.framework_id,
                                framework_version=target_snapshot.framework_version,
                                artifact_kind=kind,
                                artifact_id=remapped_id,
                                title=self._artifact_title(kind, remapped_payload),
                            ),
                            approved_alignment_edge_id=edge_id,
                            suggested_action=MigrationActionType.remap_via_alignment,
                            rationale="Entity was removed but has an approved equivalent alignment in the target snapshot.",
                        )
                    )
                else:
                    deltas.append(
                        CurriculumEntityDelta(
                            delta_id=self._stable_id(
                                "delta",
                                source_snapshot.snapshot_id,
                                target_snapshot.snapshot_id,
                                kind.value,
                                artifact_id,
                                "removed",
                            ),
                            artifact_kind=kind,
                            artifact_id=artifact_id,
                            change_kind=CurriculumChangeKind.removed,
                            risk_level=(
                                MigrationRiskLevel.high
                                if kind
                                in {
                                    CurriculumArtifactKind.outcome,
                                    CurriculumArtifactKind.knowledge_component,
                                }
                                else MigrationRiskLevel.medium
                            ),
                            before=before,
                            suggested_action=MigrationActionType.keep_pinned,
                            rationale="Entity was removed without an approved equivalent alignment.",
                        )
                    )
                continue
            if source_payload == target_payload:
                continue
            field_changes = self._field_changes(
                kind=kind,
                source_payload=source_payload or {},
                target_payload=target_payload or {},
            )
            field_names = {change.field_name for change in field_changes}
            change_kind = (
                CurriculumChangeKind.prerequisite_changed
                if "prerequisite_kc_ids" in field_names
                else CurriculumChangeKind.changed
            )
            risk_level = self._delta_risk(kind=kind, field_names=field_names)
            suggested_action = self._delta_suggested_action(
                kind=kind,
                field_names=field_names,
                risk_level=risk_level,
            )
            deltas.append(
                CurriculumEntityDelta(
                    delta_id=self._stable_id(
                        "delta",
                        source_snapshot.snapshot_id,
                        target_snapshot.snapshot_id,
                        kind.value,
                        artifact_id,
                        "changed",
                    ),
                    artifact_kind=kind,
                    artifact_id=artifact_id,
                    change_kind=change_kind,
                    risk_level=risk_level,
                    before=before,
                    after=after,
                    field_changes=field_changes,
                    suggested_action=suggested_action,
                    rationale=self._delta_rationale(
                        artifact_kind=kind,
                        field_names=field_names,
                    ),
                )
            )
        return deltas

    def _approved_alignment_map(
        self,
        *,
        source_snapshot_id: str,
        target_snapshot_id: str,
    ) -> dict[tuple[CurriculumArtifactKind, str], tuple[str, str]]:
        mapping: dict[tuple[CurriculumArtifactKind, str], tuple[str, str]] = {}
        for edge in self.alignment_edge_store.list():
            if not self._is_approved_equivalence(edge):
                continue
            if (
                edge.source.published_snapshot_id == source_snapshot_id
                and edge.target.published_snapshot_id == target_snapshot_id
            ):
                mapping[(edge.source.artifact_kind, edge.source.artifact_id)] = (
                    edge.target.artifact_id,
                    edge.edge_id,
                )
            elif (
                edge.target.published_snapshot_id == source_snapshot_id
                and edge.source.published_snapshot_id == target_snapshot_id
            ):
                mapping[(edge.target.artifact_kind, edge.target.artifact_id)] = (
                    edge.source.artifact_id,
                    edge.edge_id,
                )
        return mapping

    @staticmethod
    def _is_approved_equivalence(edge: AlignmentEdge) -> bool:
        return (
            edge.review_status == AlignmentReviewStatus.approved
            and edge.relation_type == AlignmentRelationType.equivalent_to
        )

    def _artifacts_for_snapshot(
        self, snapshot: PublishedCurriculumSnapshot
    ) -> dict[tuple[CurriculumArtifactKind, str], dict[str, object]]:
        artifacts = self.framework_import_artifact_store.list_for_import(
            snapshot.framework_import_id
        )
        return {
            (artifact.artifact_kind, artifact.artifact_key): artifact.payload
            for artifact in artifacts
        }

    @staticmethod
    def _artifact_title(
        kind: CurriculumArtifactKind, payload: dict[str, object] | None
    ) -> str | None:
        if payload is None:
            return None
        if kind == CurriculumArtifactKind.knowledge_component:
            return str(payload.get("name")) if payload.get("name") is not None else None
        return str(payload.get("title")) if payload.get("title") is not None else None

    def _field_changes(
        self,
        *,
        kind: CurriculumArtifactKind,
        source_payload: dict[str, object],
        target_payload: dict[str, object],
    ) -> list[CurriculumFieldChange]:
        changes: list[CurriculumFieldChange] = []
        for field_name in _TRACKED_FIELDS[kind]:
            before_value = source_payload.get(field_name)
            after_value = target_payload.get(field_name)
            if self._normalized_value(before_value) == self._normalized_value(after_value):
                continue
            changes.append(
                CurriculumFieldChange(
                    field_name=field_name,
                    before_value=before_value,
                    after_value=after_value,
                )
            )
        return changes

    @staticmethod
    def _normalized_value(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def _delta_risk(
        self,
        *,
        kind: CurriculumArtifactKind,
        field_names: set[str],
    ) -> MigrationRiskLevel:
        if field_names and field_names.issubset(_LOW_IMPACT_FIELDS[kind]):
            return MigrationRiskLevel.low
        if "prerequisite_kc_ids" in field_names:
            return MigrationRiskLevel.medium
        if field_names.intersection({"course_id", "strand_id", "outcome_id", "knowledge_component_ids"}):
            return MigrationRiskLevel.high
        return MigrationRiskLevel.medium

    def _delta_suggested_action(
        self,
        *,
        kind: CurriculumArtifactKind,
        field_names: set[str],
        risk_level: MigrationRiskLevel,
    ) -> MigrationActionType:
        if risk_level == MigrationRiskLevel.low:
            return MigrationActionType.swap_provenance_only
        if kind in {
            CurriculumArtifactKind.outcome,
            CurriculumArtifactKind.knowledge_component,
        } and "prerequisite_kc_ids" in field_names:
            return MigrationActionType.mark_trajectory_for_replanning
        return MigrationActionType.keep_pinned

    @staticmethod
    def _delta_rationale(
        *,
        artifact_kind: CurriculumArtifactKind,
        field_names: set[str],
    ) -> str:
        ordered_fields = ", ".join(sorted(field_names))
        return (
            f"{artifact_kind.value.replace('_', ' ')} changed in fields: {ordered_fields}."
        )

    def _remap_targets(
        self,
        *,
        delta_ids: list[str],
        delta_by_id: dict[str, CurriculumEntityDelta],
        artifact_kind: CurriculumArtifactKind,
    ) -> dict[str, list[str]]:
        targets: list[str] = []
        edges: list[str] = []
        for delta_id in delta_ids:
            delta = delta_by_id[delta_id]
            if (
                delta.artifact_kind == artifact_kind
                and delta.after is not None
                and delta.approved_alignment_edge_id is not None
            ):
                targets.append(delta.after.artifact_id)
                edges.append(delta.approved_alignment_edge_id)
        return {"targets": targets, "edges": edges}

    def _snapshot_provenance(
        self, snapshot: PublishedCurriculumSnapshot
    ) -> CurriculumVersionReference:
        return CurriculumVersionReference(
            framework_id=snapshot.framework_id,
            framework_version=snapshot.framework_version,
            framework_import_id=snapshot.framework_import_id,
            published_snapshot_id=snapshot.snapshot_id,
            source_label=snapshot.source_label,
        )

    def _require_snapshot(self, snapshot_id: str) -> PublishedCurriculumSnapshot:
        snapshot = self.published_snapshot_store.get(snapshot_id)
        if snapshot is None:
            raise LookupError(snapshot_id)
        return snapshot

    def _require_diff(self, diff_id: str) -> CurriculumSnapshotDiff:
        diff = self.curriculum_snapshot_diff_store.get(diff_id)
        if diff is None:
            raise LookupError(diff_id)
        return diff

    def _require_plan(self, plan_id: str) -> CurriculumMigrationPlan:
        plan = self.curriculum_migration_plan_store.get(plan_id)
        if plan is None:
            raise LookupError(plan_id)
        return plan

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        payload = "::".join(parts)
        digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}-{digest}"
