from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from dibble.models.generation import ContentIntent, GenerationRequest
from dibble.models.planning import (
    LearnerGoal,
    TrajectoryCheckpoint,
    TrajectoryNode,
    TrajectoryPlan,
    TrajectoryRevision,
)
from dibble.models.profile import (
    LearnerCurriculumProgressionSummary,
    OutcomeProgressSummary,
)
from dibble.services.kc_sequence_planner import KcSequencePlanner
from dibble.services.progression_ownership import ProgressionOwnershipService
from dibble.services.workflow_rationale import combine_rationales


@dataclass(slots=True)
class TrajectoryPlanner:
    kc_sequence_planner: KcSequencePlanner
    progression_ownership_service: ProgressionOwnershipService | None = None

    def build_plan(
        self,
        *,
        student_id: UUID,
        goal: LearnerGoal,
        progression: LearnerCurriculumProgressionSummary,
        trajectory_id: str | None = None,
        created_revision_number: int = 1,
    ) -> TrajectoryPlan:
        nodes, checkpoints = self._nodes_and_checkpoints(
            student_id=student_id,
            goal=goal,
            progression=progression,
        )
        active_node_id = next(
            (
                node.node_id
                for node in nodes
                if node.status in {"active", "planned", "blocked"}
            ),
            None,
        )
        active_checkpoint_id = next(
            (
                checkpoint.checkpoint_id
                for checkpoint in checkpoints
                if checkpoint.node_id == active_node_id
            ),
            None,
        )
        revision = TrajectoryRevision(
            revision_id=str(uuid4()),
            revision_number=created_revision_number,
            revision_kind="created",
            rationale=progression.rationale or goal.rationale,
            active_node_id=active_node_id,
            node_count=len(nodes),
        )
        return TrajectoryPlan(
            trajectory_id=trajectory_id or str(uuid4()),
            goal_id=goal.goal_id,
            student_id=student_id,
            status="active" if nodes else "idle",
            active_node_id=active_node_id,
            active_checkpoint_id=active_checkpoint_id,
            nodes=nodes,
            checkpoints=checkpoints,
            revisions=[revision],
            rationale=combine_rationales(goal.rationale, progression.rationale),
        )

    def revise_plan(
        self,
        *,
        existing: TrajectoryPlan,
        student_id: UUID,
        goal: LearnerGoal,
        progression: LearnerCurriculumProgressionSummary,
        rationale: str | None,
    ) -> TrajectoryPlan:
        planned = self.build_plan(
            student_id=student_id,
            goal=goal,
            progression=progression,
            trajectory_id=existing.trajectory_id,
            created_revision_number=len(existing.revisions) + 1,
        )
        revision = planned.revisions[-1].model_copy(
            update={
                "revision_kind": "revised",
                "rationale": rationale or planned.revisions[-1].rationale,
                "previous_active_node_id": existing.active_node_id,
            }
        )
        return planned.model_copy(
            update={
                "created_at": existing.created_at,
                "revisions": [*existing.revisions, revision],
            }
        )

    def semantic_signature(self, trajectory: TrajectoryPlan) -> list[tuple[str, str | None, str, tuple[str, ...]]]:
        return [
            (
                node.node_kind,
                node.outcome_id,
                node.target_stage,
                tuple(node.target_kc_ids),
            )
            for node in trajectory.nodes
        ]

    def _nodes_and_checkpoints(
        self,
        *,
        student_id: UUID,
        goal: LearnerGoal,
        progression: LearnerCurriculumProgressionSummary,
    ) -> tuple[list[TrajectoryNode], list[TrajectoryCheckpoint]]:
        candidates = self._candidate_outcomes(goal=goal, progression=progression)
        nodes: list[TrajectoryNode] = []
        checkpoints: list[TrajectoryCheckpoint] = []
        for summary in candidates:
            node, checkpoint = self._node_and_checkpoint_for_summary(
                student_id=student_id,
                summary=summary,
                goal=goal,
                progression=progression,
            )
            nodes.append(node)
            checkpoints.append(checkpoint)

        if not nodes and goal.target_kc_ids:
            node_id = str(uuid4())
            checkpoint_id = str(uuid4())
            nodes.append(
                TrajectoryNode(
                    node_id=node_id,
                    title=goal.title,
                    status="planned",
                    sequence_index=0,
                    target_kc_ids=list(goal.target_kc_ids),
                    ordered_kc_ids=list(goal.target_kc_ids),
                    checkpoint_ids=[checkpoint_id],
                    rationale=goal.rationale,
                )
            )
            checkpoints.append(
                TrajectoryCheckpoint(
                    checkpoint_id=checkpoint_id,
                    trajectory_id="pending",
                    node_id=node_id,
                    label=f"Show stable progress on {goal.title}.",
                    mastery_focus_kc_ids=list(goal.target_kc_ids),
                    rationale=goal.rationale,
                )
            )

        if len(nodes) >= 2 and nodes[0].target_kc_ids:
            review_node_id = str(uuid4())
            review_checkpoint_id = str(uuid4())
            review_title = f"Revisit {nodes[0].title}"
            nodes.insert(
                min(2, len(nodes)),
                TrajectoryNode(
                    node_id=review_node_id,
                    node_kind="spaced_review",
                    title=review_title,
                    outcome_id=nodes[0].outcome_id,
                    status="planned",
                    sequence_index=0,
                    target_stage="transfer",
                    sequence_action="attempt_transfer",
                    target_kc_ids=list(nodes[0].target_kc_ids),
                    ordered_kc_ids=list(nodes[0].target_kc_ids),
                    transfer_target_kc_ids=list(nodes[0].target_kc_ids),
                    expected_session_count=1,
                    checkpoint_ids=[review_checkpoint_id],
                    rationale=f"Revisit {nodes[0].title} after adjacent work so retention is explicit, not assumed.",
                ),
            )
            checkpoints.append(
                TrajectoryCheckpoint(
                    checkpoint_id=review_checkpoint_id,
                    trajectory_id="pending",
                    node_id=review_node_id,
                    label=f"Confirm retention on {nodes[0].title}.",
                    mastery_focus_kc_ids=list(nodes[0].target_kc_ids),
                    rationale="Use a short spaced review checkpoint before the trajectory moves too far ahead.",
                )
            )

        for index, node in enumerate(nodes):
            node.sequence_index = index
        return nodes, checkpoints

    def _candidate_outcomes(
        self,
        *,
        goal: LearnerGoal,
        progression: LearnerCurriculumProgressionSummary,
    ) -> list[OutcomeProgressSummary]:
        ordered: list[OutcomeProgressSummary] = []
        seen: set[str] = set()
        for summary in [
            progression.current_outcome,
            progression.next_outcome,
            *(progression.ready_outcomes or []),
            *(progression.blocked_outcomes or []),
        ]:
            if summary is None or summary.outcome_id in seen:
                continue
            ordered.append(summary)
            seen.add(summary.outcome_id)
        if goal.target_outcome_id is not None and goal.target_outcome_id not in seen:
            ordered.insert(
                0,
                OutcomeProgressSummary(
                    outcome_id=goal.target_outcome_id,
                    title=goal.title,
                    state="planned",
                    knowledge_component_ids=list(goal.target_kc_ids),
                    rationale=goal.rationale,
                ),
            )
        return ordered

    def _node_and_checkpoint_for_summary(
        self,
        *,
        student_id: UUID,
        summary: OutcomeProgressSummary,
        goal: LearnerGoal,
        progression: LearnerCurriculumProgressionSummary,
    ) -> tuple[TrajectoryNode, TrajectoryCheckpoint]:
        requested_kc_ids = list(summary.knowledge_component_ids or goal.target_kc_ids)
        sequence = self.kc_sequence_planner.plan(
            strategy_summary=None,
            target_kc_ids=requested_kc_ids,
            prerequisite_kc_ids=summary.blocked_prerequisite_kc_ids,
        )
        target_stage = summary.target_stage or progression.current_stage or "target"
        sequence_action = sequence.action
        applied_target_kc_ids = list(sequence.ordered_kc_ids or requested_kc_ids)
        rationale = combine_rationales(summary.rationale, goal.rationale)

        if self.progression_ownership_service is not None and requested_kc_ids:
            decision = self.progression_ownership_service.resolve_request(
                student_id=student_id,
                request=GenerationRequest(
                    student_id=student_id,
                    target_kc_ids=requested_kc_ids,
                    target_lo_ids=[],
                    intent=ContentIntent.explanation,
                ),
            )
            target_stage = decision.target_stage
            sequence_action = decision.action
            applied_target_kc_ids = list(
                decision.applied_target_kc_ids or applied_target_kc_ids
            )
            rationale = combine_rationales(decision.rationale, rationale)
            transfer_target_kc_ids = list(
                decision.transfer_target_kc_ids or requested_kc_ids
            )
            deferred_target_kc_ids = list(decision.deferred_target_kc_ids)
            bridge_kc_ids = list(decision.bridge_kc_ids)
        else:
            transfer_target_kc_ids = list(requested_kc_ids)
            deferred_target_kc_ids = list(sequence.deferred_kc_ids)
            bridge_kc_ids = list(sequence.bridge_kc_ids)

        node_id = str(uuid4())
        checkpoint_id = str(uuid4())
        node = TrajectoryNode(
            node_id=node_id,
            title=summary.title,
            outcome_id=summary.outcome_id,
            status=self._node_status(summary.state),
            target_stage=target_stage,
            sequence_action=sequence_action,
            target_kc_ids=list(applied_target_kc_ids or requested_kc_ids),
            ordered_kc_ids=list(sequence.ordered_kc_ids or requested_kc_ids),
            target_lo_ids=[],
            bridge_kc_ids=bridge_kc_ids,
            deferred_target_kc_ids=deferred_target_kc_ids,
            transfer_target_kc_ids=transfer_target_kc_ids,
            expected_session_count=self._expected_session_count(
                summary=summary,
                bridge_kc_ids=bridge_kc_ids,
                applied_target_kc_ids=applied_target_kc_ids,
            ),
            checkpoint_ids=[checkpoint_id],
            rationale=rationale,
        )
        checkpoint = TrajectoryCheckpoint(
            checkpoint_id=checkpoint_id,
            trajectory_id="pending",
            node_id=node_id,
            label=self._checkpoint_label(summary=summary, target_stage=target_stage),
            expected_after_session_count=node.expected_session_count,
            mastery_focus_kc_ids=list(node.target_kc_ids),
            rationale=node.rationale,
        )
        return node, checkpoint

    def _node_status(self, state: str) -> str:
        if state == "active":
            return "active"
        if state == "mastered":
            return "completed"
        if state == "blocked":
            return "blocked"
        return "planned"

    def _expected_session_count(
        self,
        *,
        summary: OutcomeProgressSummary,
        bridge_kc_ids: list[str],
        applied_target_kc_ids: list[str],
    ) -> int:
        return max(
            1,
            min(
                4,
                1
                + len(summary.blocked_prerequisite_kc_ids)
                + len(bridge_kc_ids)
                + max(0, len(applied_target_kc_ids) - 1),
            ),
        )

    def _checkpoint_label(self, *, summary: OutcomeProgressSummary, target_stage: str) -> str:
        if target_stage == "repair":
            return f"Stabilize the foundations for {summary.title}."
        if target_stage == "bridge":
            return f"Bridge back into {summary.title} without losing momentum."
        return f"Show independent progress on {summary.title}."
