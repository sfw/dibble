from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID, uuid4

from dibble.models.generation import ContentIntent, GenerationRequest
from dibble.models.planning import (
    LearnerGoal,
    PlanningAdaptationState,
    PlanningConceptClusterMarker,
    PlanningEvidenceStrength,
    PlanningModalityPreferenceEntry,
    PlanningSignalKind,
    TrajectoryCheckpoint,
    TrajectoryNode,
    TrajectoryNodeAdaptation,
    TrajectoryPlan,
    TrajectoryRevision,
    TrajectoryRevisionReason,
    TrajectoryRiskLevel,
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
        adaptation_state: PlanningAdaptationState | None = None,
    ) -> TrajectoryPlan:
        nodes, checkpoints = self._nodes_and_checkpoints(
            student_id=student_id,
            goal=goal,
            progression=progression,
            adaptation_state=adaptation_state,
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
            reasons=self._revision_reasons(adaptation_state=adaptation_state),
            adjustments=list(
                adaptation_state.active_adjustments
                if adaptation_state is not None
                else []
            ),
            observed_signals=list(
                adaptation_state.recent_signals if adaptation_state is not None else []
            ),
        )
        return TrajectoryPlan(
            trajectory_id=trajectory_id or str(uuid4()),
            goal_id=goal.goal_id,
            student_id=student_id,
            status="active" if nodes else "idle",
            active_node_id=active_node_id,
            active_checkpoint_id=active_checkpoint_id,
            curriculum_provenance=goal.curriculum_provenance
            or progression.curriculum_provenance,
            nodes=nodes,
            checkpoints=checkpoints,
            revisions=[revision],
            adaptation_state=(
                adaptation_state.model_copy(
                    update={"revision_count": created_revision_number}
                )
                if adaptation_state is not None
                else None
            ),
            rationale=combine_rationales(goal.rationale, progression.rationale),
        )

    def append_revision(
        self,
        *,
        existing: TrajectoryPlan,
        planned: TrajectoryPlan,
        rationale: str | None,
    ) -> TrajectoryPlan:
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

    def semantic_signature(
        self, trajectory: TrajectoryPlan
    ) -> list[tuple[str, str | None, str, tuple[str, ...], int, str, str | None]]:
        return [
            (
                node.node_kind,
                node.outcome_id,
                node.target_stage,
                tuple(node.target_kc_ids),
                node.expected_session_count,
                (
                    node.adaptation.risk_level.value
                    if node.adaptation is not None
                    else TrajectoryRiskLevel.low.value
                ),
                (
                    node.adaptation.recommended_scaffolding_pattern
                    if node.adaptation is not None
                    else None
                ),
            )
            for node in trajectory.nodes
        ]

    def adaptation_signature(self, trajectory: TrajectoryPlan) -> tuple[object, ...]:
        adaptation = trajectory.adaptation_state
        if adaptation is None:
            return ()
        return (
            adaptation.active_pacing_adjustment,
            adaptation.active_revisit_density,
            adaptation.preferred_scaffolding_pattern,
            adaptation.preferred_modality,
            tuple(
                (
                    marker.cluster_key,
                    marker.risk_level.value,
                    marker.sample_count,
                    marker.preferred_recovery_pattern,
                    marker.preferred_modality,
                )
                for marker in adaptation.concept_cluster_markers
            ),
            tuple(
                (
                    entry.preference_key,
                    entry.preferred_modality,
                    entry.sample_count,
                    entry.average_outcome_score,
                )
                for entry in (
                    adaptation.modality_preferences.preferred_by_content_family
                    + adaptation.modality_preferences.preferred_by_risk_bucket
                    + adaptation.modality_preferences.preferred_by_recovery_pattern
                )
            ),
            tuple(
                (
                    signal.kind.value,
                    signal.direction,
                    signal.sample_count,
                    signal.cluster_key,
                    signal.content_type,
                    signal.phase,
                    signal.modality,
                )
                for signal in adaptation.recent_signals
            ),
        )

    def _nodes_and_checkpoints(
        self,
        *,
        student_id: UUID,
        goal: LearnerGoal,
        progression: LearnerCurriculumProgressionSummary,
        adaptation_state: PlanningAdaptationState | None,
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
                adaptation_state=adaptation_state,
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
                    adaptation=self._node_adaptation(
                        target_kc_ids=list(goal.target_kc_ids),
                        content_family="practice_problem",
                        target_stage="target",
                        sequence_action="stay_on_requested_target",
                        adaptation_state=adaptation_state,
                    ),
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

        nodes, checkpoints = self._apply_recovery_scaffold(
            nodes=nodes,
            checkpoints=checkpoints,
            adaptation_state=adaptation_state,
        )
        nodes, checkpoints = self._insert_review_nodes(
            nodes=nodes,
            checkpoints=checkpoints,
            revisit_density=(
                adaptation_state.active_revisit_density
                if adaptation_state is not None
                else 1
            ),
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
        adaptation_state: PlanningAdaptationState | None,
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

        content_family = self._content_family_for_node(
            target_stage=target_stage,
            sequence_action=sequence_action,
        )
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
                adaptation_state=adaptation_state,
                target_kc_ids=list(applied_target_kc_ids or requested_kc_ids),
            ),
            checkpoint_ids=[checkpoint_id],
            rationale=combine_rationales(
                rationale,
                self._adaptation_rationale(
                    target_kc_ids=list(applied_target_kc_ids or requested_kc_ids),
                    content_family=content_family,
                    target_stage=target_stage,
                    sequence_action=sequence_action,
                    adaptation_state=adaptation_state,
                ),
            ),
            adaptation=self._node_adaptation(
                target_kc_ids=list(applied_target_kc_ids or requested_kc_ids),
                content_family=content_family,
                target_stage=target_stage,
                sequence_action=sequence_action,
                adaptation_state=adaptation_state,
            ),
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
        adaptation_state: PlanningAdaptationState | None,
        target_kc_ids: list[str],
    ) -> int:
        baseline = max(
            1,
            min(
                4,
                1
                + len(summary.blocked_prerequisite_kc_ids)
                + len(bridge_kc_ids)
                + max(0, len(applied_target_kc_ids) - 1),
            ),
        )
        if adaptation_state is None:
            return baseline
        node_adaptation = self._node_adaptation(
            target_kc_ids=target_kc_ids,
            content_family=self._content_family_for_node(
                target_stage=summary.target_stage,
                sequence_action=summary.state,
            ),
            target_stage=summary.target_stage,
            sequence_action=summary.state,
            adaptation_state=adaptation_state,
        )
        adjustment = 0
        if adaptation_state.active_pacing_adjustment == "slower":
            adjustment += 1
        if (
            node_adaptation is not None
            and node_adaptation.risk_level == TrajectoryRiskLevel.high
        ):
            adjustment += 1
        elif (
            node_adaptation is not None
            and node_adaptation.risk_level == TrajectoryRiskLevel.moderate
        ):
            adjustment += 0
        return max(1, min(5, baseline + adjustment))

    def _checkpoint_label(
        self, *, summary: OutcomeProgressSummary, target_stage: str
    ) -> str:
        if target_stage == "repair":
            return f"Stabilize the foundations for {summary.title}."
        if target_stage == "bridge":
            return f"Bridge back into {summary.title} without losing momentum."
        return f"Show independent progress on {summary.title}."

    def _apply_recovery_scaffold(
        self,
        *,
        nodes: list[TrajectoryNode],
        checkpoints: list[TrajectoryCheckpoint],
        adaptation_state: PlanningAdaptationState | None,
    ) -> tuple[list[TrajectoryNode], list[TrajectoryCheckpoint]]:
        if adaptation_state is None or not nodes:
            return nodes, checkpoints
        first_node = nodes[0]
        if (
            first_node.adaptation is None
            or first_node.adaptation.risk_level != TrajectoryRiskLevel.high
        ):
            return nodes, checkpoints
        if not first_node.target_kc_ids:
            return nodes, checkpoints
        recovery_label = (
            first_node.adaptation.recommended_scaffolding_pattern or "guided recovery"
        )
        node_id = str(uuid4())
        checkpoint_id = str(uuid4())
        scaffold = TrajectoryNode(
            node_id=node_id,
            node_kind="recovery_scaffold",
            title=f"Rebuild {first_node.title}",
            outcome_id=first_node.outcome_id,
            status="planned",
            sequence_index=0,
            target_stage="repair",
            sequence_action="rebuild_prerequisite",
            target_kc_ids=list(first_node.target_kc_ids),
            ordered_kc_ids=list(first_node.target_kc_ids),
            transfer_target_kc_ids=list(first_node.target_kc_ids),
            expected_session_count=1,
            checkpoint_ids=[checkpoint_id],
            rationale=(
                f"Recent outcomes show this cluster needs a bounded scaffold first. "
                f"Preferred pattern: {recovery_label}."
            ),
            adaptation=TrajectoryNodeAdaptation(
                risk_level=TrajectoryRiskLevel.high,
                pacing_adjustment=adaptation_state.active_pacing_adjustment,
                revisit_priority="high",
                recommended_scaffolding_pattern=recovery_label,
                recommended_modality=first_node.adaptation.recommended_modality
                or adaptation_state.preferred_modality,
                signal_ids=[
                    signal.signal_id
                    for signal in adaptation_state.recent_signals
                    if self._overlaps(signal.target_kc_ids, first_node.target_kc_ids)
                    or signal.kind == PlanningSignalKind.session_effectiveness
                ],
                rationale="Insert a recovery scaffold before the main node when repeated stalls are strong enough to justify a structural change.",
            ),
        )
        checkpoint = TrajectoryCheckpoint(
            checkpoint_id=checkpoint_id,
            trajectory_id="pending",
            node_id=node_id,
            label=f"Stabilize {first_node.title} before the trajectory resumes.",
            mastery_focus_kc_ids=list(first_node.target_kc_ids),
            rationale=scaffold.rationale,
        )
        return [scaffold, *nodes], [*checkpoints, checkpoint]

    def _insert_review_nodes(
        self,
        *,
        nodes: list[TrajectoryNode],
        checkpoints: list[TrajectoryCheckpoint],
        revisit_density: int,
    ) -> tuple[list[TrajectoryNode], list[TrajectoryCheckpoint]]:
        if len(nodes) < 2 or not nodes[0].target_kc_ids:
            return nodes, checkpoints
        updated_nodes = list(nodes)
        updated_checkpoints = list(checkpoints)
        insert_after_indices = [2]
        if revisit_density >= 2 and len(nodes) >= 3 and nodes[1].target_kc_ids:
            insert_after_indices.append(min(4, len(nodes)))
        for insert_index in insert_after_indices[: max(1, revisit_density)]:
            anchor = updated_nodes[
                min(max(insert_index - 2, 0), len(updated_nodes) - 1)
            ]
            if not anchor.target_kc_ids:
                continue
            review_node_id = str(uuid4())
            review_checkpoint_id = str(uuid4())
            review_title = f"Revisit {anchor.title}"
            updated_nodes.insert(
                min(insert_index, len(updated_nodes)),
                TrajectoryNode(
                    node_id=review_node_id,
                    node_kind="spaced_review",
                    title=review_title,
                    outcome_id=anchor.outcome_id,
                    status="planned",
                    sequence_index=0,
                    target_stage="transfer",
                    sequence_action="attempt_transfer",
                    target_kc_ids=list(anchor.target_kc_ids),
                    ordered_kc_ids=list(anchor.target_kc_ids),
                    transfer_target_kc_ids=list(anchor.target_kc_ids),
                    expected_session_count=1,
                    checkpoint_ids=[review_checkpoint_id],
                    rationale=(
                        f"Revisit {anchor.title} after adjacent work so retention is explicit, not assumed."
                    ),
                    adaptation=anchor.adaptation,
                ),
            )
            updated_checkpoints.append(
                TrajectoryCheckpoint(
                    checkpoint_id=review_checkpoint_id,
                    trajectory_id="pending",
                    node_id=review_node_id,
                    label=f"Confirm retention on {anchor.title}.",
                    mastery_focus_kc_ids=list(anchor.target_kc_ids),
                    rationale="Use a short spaced review checkpoint before the trajectory moves too far ahead.",
                )
            )
        return updated_nodes, updated_checkpoints

    def _node_adaptation(
        self,
        *,
        target_kc_ids: list[str],
        content_family: str | None,
        target_stage: str,
        sequence_action: str,
        adaptation_state: PlanningAdaptationState | None,
    ) -> TrajectoryNodeAdaptation | None:
        if adaptation_state is None:
            return None
        marker = next(
            (
                item
                for item in adaptation_state.concept_cluster_markers
                if self._overlaps(item.target_kc_ids, target_kc_ids)
            ),
            None,
        )
        signal_ids = [
            signal.signal_id
            for signal in adaptation_state.recent_signals
            if self._overlaps(signal.target_kc_ids, target_kc_ids)
            or (
                signal.kind == PlanningSignalKind.session_effectiveness
                and signal.evidence_strength != PlanningEvidenceStrength.weak
            )
        ]
        if (
            marker is None
            and not signal_ids
            and adaptation_state.preferred_scaffolding_pattern is None
        ):
            return None
        return TrajectoryNodeAdaptation(
            risk_level=marker.risk_level
            if marker is not None
            else TrajectoryRiskLevel.low,
            pacing_adjustment=adaptation_state.active_pacing_adjustment,
            revisit_priority=(
                "high"
                if marker is not None and marker.risk_level == TrajectoryRiskLevel.high
                else "elevated"
                if marker is not None
                and marker.risk_level == TrajectoryRiskLevel.moderate
                else "normal"
            ),
            recommended_scaffolding_pattern=(
                marker.preferred_recovery_pattern
                if marker is not None
                else adaptation_state.preferred_scaffolding_pattern
            ),
            recommended_modality=self._recommended_modality_for_node(
                marker=marker,
                content_family=content_family,
                target_stage=target_stage,
                sequence_action=sequence_action,
                adaptation_state=adaptation_state,
            ),
            signal_ids=signal_ids,
            rationale=marker.rationale if marker is not None else None,
        )

    def _recommended_modality_for_node(
        self,
        *,
        marker: PlanningConceptClusterMarker | None,
        content_family: str | None,
        target_stage: str,
        sequence_action: str,
        adaptation_state: PlanningAdaptationState,
    ) -> str | None:
        preferences = adaptation_state.modality_preferences
        recovery_label = (
            marker.preferred_recovery_pattern
            if marker is not None and marker.preferred_recovery_pattern is not None
            else adaptation_state.preferred_scaffolding_pattern
        )
        recovery_entry = self._best_modality_entry(
            entry
            for entry in preferences.preferred_by_recovery_pattern
            if recovery_label is not None
            and (
                entry.preference_key == recovery_label
                or entry.context_label == recovery_label
            )
        )
        if recovery_entry is not None and target_stage == "repair":
            return recovery_entry.preferred_modality
        content_entry = self._best_modality_entry(
            entry
            for entry in preferences.preferred_by_content_family
            if content_family is not None and entry.preference_key == content_family
        )
        if content_entry is not None:
            return content_entry.preferred_modality
        if recovery_entry is not None and sequence_action == "rebuild_prerequisite":
            return recovery_entry.preferred_modality
        risk_entry = self._best_modality_entry(
            entry
            for entry in preferences.preferred_by_risk_bucket
            if marker is not None and entry.preference_key == marker.risk_level.value
        )
        if risk_entry is not None:
            return risk_entry.preferred_modality
        if marker is not None and marker.preferred_modality is not None:
            return marker.preferred_modality
        return adaptation_state.preferred_modality

    def _best_modality_entry(
        self,
        entries: Iterable[PlanningModalityPreferenceEntry],
    ) -> PlanningModalityPreferenceEntry | None:
        ranked = [entry for entry in entries if entry.sample_count >= 2]
        if not ranked:
            return None
        ranked.sort(
            key=lambda entry: (
                entry.average_outcome_score,
                entry.positive_outcome_rate,
                entry.recovery_rate,
                entry.sample_count,
                entry.preferred_modality,
            ),
            reverse=True,
        )
        return ranked[0]

    def _content_family_for_node(
        self,
        *,
        target_stage: str,
        sequence_action: str,
    ) -> str:
        if target_stage == "repair" or sequence_action == "rebuild_prerequisite":
            return "remedial_micro_module"
        if target_stage == "bridge":
            return "micro_explanation"
        if target_stage == "transfer" or sequence_action == "attempt_transfer":
            return "practice_problem"
        return "practice_problem"

    def _adaptation_rationale(
        self,
        *,
        target_kc_ids: list[str],
        content_family: str | None,
        target_stage: str,
        sequence_action: str,
        adaptation_state: PlanningAdaptationState | None,
    ) -> str | None:
        node_adaptation = self._node_adaptation(
            target_kc_ids=target_kc_ids,
            content_family=content_family,
            target_stage=target_stage,
            sequence_action=sequence_action,
            adaptation_state=adaptation_state,
        )
        if node_adaptation is None:
            return None
        if node_adaptation.risk_level == TrajectoryRiskLevel.high:
            return "Recent outcome history suggests this cluster needs slower pacing and stronger scaffolding."
        if node_adaptation.risk_level == TrajectoryRiskLevel.moderate:
            return (
                "Recent outcomes suggest adding bounded support and explicit revisits."
            )
        if node_adaptation.recommended_scaffolding_pattern is not None:
            return f"Keep {node_adaptation.recommended_scaffolding_pattern} available because it has helped similar recent sessions recover."
        return None

    def _revision_reasons(
        self, *, adaptation_state: PlanningAdaptationState | None
    ) -> list[TrajectoryRevisionReason]:
        if adaptation_state is None:
            return []
        reasons: list[TrajectoryRevisionReason] = []
        for signal in adaptation_state.recent_signals[:4]:
            reasons.append(
                TrajectoryRevisionReason(
                    reason_code=f"{signal.kind.value}:{signal.direction}",
                    signal_kind=signal.kind,
                    evidence_strength=signal.evidence_strength,
                    cluster_key=signal.cluster_key,
                    rationale=signal.rationale
                    or "Outcome history contributed to this trajectory revision.",
                )
            )
        return reasons

    def _overlaps(self, left: list[str], right: list[str]) -> bool:
        return bool(set(left).intersection(right))
