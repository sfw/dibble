from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

from dibble.models.generation import (
    GeneratedContent,
    GenerationRequest,
    GenerationWorkflowSummary,
    RequestedContentType,
)
from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep
from dibble.models.session_control import SessionControlState
from dibble.services.harness.curriculum_planning import (
    CurriculumPlanningHarness,
    EnsureActiveTrajectoryCommand,
)
from dibble.services.predictive_next_step_planner import PredictiveNextStepPlanner
from dibble.services.protocols import SessionControlStore
from dibble.services.workflow_rationale import decision_grade_rationale

_CONTENT_TYPE_TO_INTENT: dict[str | None, str] = {
    RequestedContentType.micro_explanation.value: "explanation",
    RequestedContentType.worked_example.value: "explanation",
    RequestedContentType.practice_problem.value: "practice",
    RequestedContentType.remedial_micro_module.value: "remediation",
    RequestedContentType.assessment_probe.value: "assessment",
}


def _intent_for_content_type(content_type: str | None) -> str:
    return _CONTENT_TYPE_TO_INTENT.get(content_type, "explanation")


@dataclass(frozen=True, slots=True)
class BindGenerationRequestCommand:
    request: GenerationRequest


@dataclass(frozen=True, slots=True)
class BindGenerationRequestResult:
    request: GenerationRequest
    session: SessionControlState | None
    planning_revised: bool = False


@dataclass(frozen=True, slots=True)
class EnsureSessionControlCommand:
    student_id: UUID


@dataclass(frozen=True, slots=True)
class SummarizeGeneratedContentCommand:
    generated_content: GeneratedContent
    persist_session_state: bool = True


@dataclass(frozen=True, slots=True)
class SummarizeGeneratedContentResult:
    content: GeneratedContent
    session: SessionControlState | None


@dataclass(slots=True)
class WithinSessionControlHarness:
    curriculum_planning_harness: CurriculumPlanningHarness
    session_control_store: SessionControlStore
    next_step_planner: PredictiveNextStepPlanner = field(
        default_factory=PredictiveNextStepPlanner
    )

    def bind_generation_request(
        self, command: BindGenerationRequestCommand
    ) -> BindGenerationRequestResult:
        request = command.request
        if request.predictive_warm:
            return BindGenerationRequestResult(request=request, session=None)

        planning = self.curriculum_planning_harness.ensure_active_trajectory(
            EnsureActiveTrajectoryCommand(
                student_id=request.student_id,
                requested_target_kc_ids=list(request.target_kc_ids or []),
            )
        )
        session = self._session_for_request(request=request, planning=planning)
        if session is None:
            return BindGenerationRequestResult(
                request=request,
                session=None,
                planning_revised=planning.trajectory_revised,
            )

        bound_request = request.model_copy(
            update={
                "learning_session_id": request.learning_session_id
                or session.learning_session_id,
                "target_kc_ids": list(request.target_kc_ids or session.active_target_kc_ids),
                "target_lo_ids": list(request.target_lo_ids or session.target_lo_ids),
            }
        )
        return BindGenerationRequestResult(
            request=bound_request,
            session=session,
            planning_revised=planning.trajectory_revised,
        )

    def ensure_session(
        self, command: EnsureSessionControlCommand
    ) -> SessionControlState | None:
        student_id = command.student_id
        existing = self.session_control_store.get_active_for_student(student_id=student_id)
        if existing is not None:
            return existing
        planning = self.curriculum_planning_harness.ensure_active_trajectory(
            EnsureActiveTrajectoryCommand(student_id=student_id)
        )
        if planning.goal is None and planning.trajectory is None:
            return None
        return self._create_session_from_plan(
            student_id=student_id,
            learning_session_id=None,
            planning=planning,
        )

    def get_active_session(self, *, student_id) -> SessionControlState | None:
        return self.session_control_store.get_active_for_student(student_id=student_id)

    def summarize_generated_content(
        self, command: SummarizeGeneratedContentCommand
    ) -> SummarizeGeneratedContentResult:
        generated_content = command.generated_content
        request_context = generated_content.request_context
        remediation_data = self._dict_value(request_context.get("remediation_workflow"))
        session = None
        learning_session_id = self._maybe_str(request_context.get("learning_session_id"))
        if learning_session_id is not None:
            session = self.session_control_store.get(learning_session_id)

        if remediation_data:
            workflow_summary = self._remediation_workflow_summary(
                generated_content=generated_content,
                request_context=request_context,
                remediation_data=remediation_data,
            )
        else:
            workflow_summary = self._lesson_workflow_summary(
                generated_content=generated_content,
                request_context=request_context,
            )
        if session is not None:
            workflow_summary = workflow_summary.model_copy(
                update={
                    "goal_id": session.goal_id,
                    "trajectory_id": session.trajectory_id,
                    "trajectory_node_id": session.trajectory_node_id,
                    "trajectory_checkpoint_id": session.trajectory_checkpoint_id,
                }
            )

        updated_content = generated_content.model_copy(
            update={"workflow_summary": workflow_summary}
        )
        if not command.persist_session_state or bool(request_context.get("is_predictive_warm")):
            return SummarizeGeneratedContentResult(content=updated_content, session=session)

        updated_session = self._upsert_session_from_summary(
            existing=session,
            generated_content=updated_content,
            summary=workflow_summary,
            remediation_data=remediation_data,
        )
        return SummarizeGeneratedContentResult(
            content=updated_content,
            session=updated_session,
        )

    def _session_for_request(self, *, request: GenerationRequest, planning) -> SessionControlState | None:
        existing = (
            self.session_control_store.get(request.learning_session_id)
            if request.learning_session_id is not None
            else self.session_control_store.get_active_for_student(student_id=request.student_id)
        )
        if existing is not None:
            if request.target_kc_ids or request.target_lo_ids:
                existing = existing.model_copy(
                    update={
                        "active_target_kc_ids": list(
                            request.target_kc_ids or existing.active_target_kc_ids
                        ),
                        "target_lo_ids": list(
                            request.target_lo_ids or existing.target_lo_ids
                        ),
                        "continue_action": self._continue_action_from_session(
                            existing.model_copy(
                                update={
                                    "active_target_kc_ids": list(
                                        request.target_kc_ids
                                        or existing.active_target_kc_ids
                                    ),
                                    "target_lo_ids": list(
                                        request.target_lo_ids or existing.target_lo_ids
                                    ),
                                }
                            )
                        ),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                self.session_control_store.upsert(existing)
            return existing
        if planning.goal is None and planning.trajectory is None and not request.target_kc_ids:
            return None
        return self._create_session_from_plan(
            student_id=request.student_id,
            learning_session_id=request.learning_session_id,
            planning=planning,
            explicit_target_kc_ids=list(request.target_kc_ids or []),
            explicit_target_lo_ids=list(request.target_lo_ids or []),
        )

    def _create_session_from_plan(
        self,
        *,
        student_id,
        learning_session_id: str | None,
        planning,
        explicit_target_kc_ids: list[str] | None = None,
        explicit_target_lo_ids: list[str] | None = None,
    ) -> SessionControlState:
        trajectory = planning.trajectory
        node = self._active_node(trajectory)
        target_kc_ids = list(
            explicit_target_kc_ids
            or (node.target_kc_ids if node is not None else [])
            or (planning.goal.target_kc_ids if planning.goal is not None else [])
        )
        target_lo_ids = list(explicit_target_lo_ids or [])
        target_stage = node.target_stage if node is not None else "target"
        initial_content_type = self._initial_content_type_for_stage(target_stage)
        learning_session_id = learning_session_id or str(uuid4())
        next_step = LearnerFlowNextStep(
            action=node.sequence_action if node is not None else "stay_on_requested_target",
            content_type=initial_content_type,
            target_stage=target_stage,
            target_kc_ids=list(target_kc_ids),
            rationale=(node.rationale if node is not None else None)
            or (
                planning.trajectory.rationale
                if planning.trajectory is not None
                else planning.goal.rationale
                if planning.goal is not None
                else None
            ),
        )
        session = SessionControlState(
            learning_session_id=learning_session_id,
            student_id=student_id,
            goal_id=planning.goal.goal_id if planning.goal is not None else None,
            trajectory_id=trajectory.trajectory_id if trajectory is not None else None,
            trajectory_node_id=node.node_id if node is not None else None,
            trajectory_checkpoint_id=(
                trajectory.active_checkpoint_id if trajectory is not None else None
            ),
            flow_type="lesson",
            status="ready_for_next_step" if initial_content_type is not None else "idle",
            phase=target_stage,
            progression_action=next_step.action,
            progression_source="workflow_summary",
            target_stage=target_stage,
            active_target_kc_ids=list(target_kc_ids),
            deferred_target_kc_ids=list(
                node.deferred_target_kc_ids if node is not None else []
            ),
            transfer_target_kc_ids=list(
                node.transfer_target_kc_ids if node is not None else target_kc_ids
            ),
            target_lo_ids=list(target_lo_ids),
            artifact_kind="idle",
            next_step=next_step,
            continue_action=LearnerContinueAction.generate_follow_up(
                learning_session_id=learning_session_id,
                content_type=next_step.content_type,
                target_stage=next_step.target_stage,
                target_kc_ids=list(next_step.target_kc_ids),
                request_payload={
                    "student_id": str(student_id),
                    "learning_session_id": learning_session_id,
                    "target_kc_ids": list(target_kc_ids),
                    "target_lo_ids": list(target_lo_ids),
                    "intent": _intent_for_content_type(next_step.content_type),
                    "requested_content_type": next_step.content_type,
                },
                rationale=next_step.rationale,
            )
            if next_step.content_type is not None
            else LearnerContinueAction.idle(rationale=next_step.rationale),
            rationale=next_step.rationale,
        )
        self.session_control_store.upsert(session)
        return session

    def _active_node(self, trajectory) -> object | None:
        if trajectory is None:
            return None
        if trajectory.active_node_id is not None:
            for node in trajectory.nodes:
                if node.node_id == trajectory.active_node_id:
                    return node
        for node in trajectory.nodes:
            if node.status in {"active", "planned", "blocked"}:
                return node
        return trajectory.nodes[0] if trajectory.nodes else None

    def _lesson_workflow_summary(
        self,
        *,
        generated_content: GeneratedContent,
        request_context: dict[str, object],
    ) -> GenerationWorkflowSummary:
        progression = self._dict_value(request_context.get("progression"))
        next_step = self._predictive_next_step(generated_content=generated_content)
        return GenerationWorkflowSummary(
            status="delivered",
            flow_type="lesson",
            learning_session_id=self._maybe_str(request_context.get("learning_session_id")),
            delivered_phase=str(
                progression.get("target_stage")
                or self._dict_value(request_context.get("session_adaptation")).get("phase")
                or "target"
            ),
            delivered_content_type=generated_content.content_type,
            progression_action=str(
                progression.get("action", "stay_on_requested_target")
            ),
            target_stage=str(progression.get("target_stage", "target")),
            active_target_kc_ids=self._string_list(
                progression.get("applied_target_kc_ids")
                or request_context.get("target_kc_ids")
            ),
            rationale=next_step.rationale,
            next_step=next_step,
            continue_action=self._continue_action_for_lesson_content(
                generated_content=generated_content,
                next_step=next_step,
            ),
        )

    def _remediation_workflow_summary(
        self,
        *,
        generated_content: GeneratedContent,
        request_context: dict[str, object],
        remediation_data: dict[str, object],
    ) -> GenerationWorkflowSummary:
        progression_data = self._dict_value(request_context.get("progression"))
        executed_phase = str(remediation_data.get("executed_phase", "repair"))
        next_phase = remediation_data.get("next_phase")
        progression_decision = str(
            remediation_data.get("progression_decision", "advance")
        )
        next_target_kc_ids = self._remediation_next_step_target_kc_ids(
            remediation_data=remediation_data
        )
        explicit_next_step_rationale = self._maybe_str(
            remediation_data.get("next_step_rationale")
        )
        next_step = LearnerFlowNextStep(
            action=(
                str(remediation_data.get("progression_decision"))
                if progression_decision.startswith("hold_")
                else str(next_phase or "complete")
            ),
            content_type=self._content_type_for_remediation_phase(
                phase=next_phase,
                progression_decision=progression_decision,
            ),
            target_stage=self._target_stage_for_remediation_next_step(
                phase=next_phase or executed_phase,
                progression_decision=progression_decision,
            ),
            target_kc_ids=next_target_kc_ids,
            rationale=self._workflow_step_rationale(
                primary=explicit_next_step_rationale
                or self._maybe_str(remediation_data.get("progression_rationale")),
                action=(
                    progression_decision
                    if progression_decision.startswith("hold_")
                    else str(next_phase or "complete")
                ),
                target_stage=self._target_stage_for_remediation_next_step(
                    phase=next_phase or executed_phase,
                    progression_decision=progression_decision,
                ),
                fallback=(
                    None
                    if explicit_next_step_rationale is not None
                    else self._first_text(
                        progression_data.get("mastery_gate_reason"),
                        progression_data.get("rationale"),
                        request_context.get("remediation_rationale"),
                    )
                ),
            ),
        )
        return GenerationWorkflowSummary(
            status="delivered",
            flow_type="remediation",
            learning_session_id=self._maybe_str(request_context.get("learning_session_id")),
            delivered_phase=executed_phase,
            delivered_content_type=generated_content.content_type,
            progression_action=progression_decision,
            target_stage=self._target_stage_for_phase(executed_phase),
            active_target_kc_ids=self._string_list(
                progression_data.get("applied_target_kc_ids")
                or request_context.get("target_kc_ids")
            ),
            rationale=next_step.rationale,
            next_step=next_step,
            continue_action=self._continue_action_for_remediation_content(
                generated_content=generated_content,
                request_context=request_context,
                remediation_data=remediation_data,
                next_step=next_step,
            ),
        )

    def _upsert_session_from_summary(
        self,
        *,
        existing: SessionControlState | None,
        generated_content: GeneratedContent,
        summary: GenerationWorkflowSummary,
        remediation_data: dict[str, object],
    ) -> SessionControlState:
        request_context = generated_content.request_context
        session_adaptation = self._dict_value(request_context.get("session_adaptation"))
        base = existing or SessionControlState(
            learning_session_id=summary.learning_session_id or str(uuid4()),
            student_id=generated_content.student_id,
        )
        updated = base.model_copy(
            update={
                "goal_id": summary.goal_id or base.goal_id,
                "trajectory_id": summary.trajectory_id or base.trajectory_id,
                "trajectory_node_id": summary.trajectory_node_id
                or base.trajectory_node_id,
                "trajectory_checkpoint_id": summary.trajectory_checkpoint_id
                or base.trajectory_checkpoint_id,
                "flow_type": summary.flow_type,
                "status": "ready_for_next_step"
                if summary.next_step.content_type is not None
                else "idle",
                "phase": summary.delivered_phase,
                "current_content_type": summary.delivered_content_type,
                "current_generation_id": generated_content.generation_id,
                "progression_action": summary.progression_action,
                "progression_source": "workflow_summary",
                "target_stage": summary.target_stage,
                "active_target_kc_ids": list(summary.active_target_kc_ids),
                "deferred_target_kc_ids": self._string_list(
                    self._dict_value(request_context.get("progression")).get(
                        "deferred_target_kc_ids"
                    )
                ),
                "transfer_target_kc_ids": self._string_list(
                    self._dict_value(request_context.get("progression")).get(
                        "transfer_target_kc_ids"
                    )
                ),
                "target_lo_ids": self._string_list(request_context.get("target_lo_ids")),
                "session_phase": str(
                    session_adaptation.get("phase", summary.delivered_phase)
                ),
                "session_arc_action": str(
                    session_adaptation.get("arc_action", "steady")
                ),
                "session_stuck_loop_risk": str(
                    session_adaptation.get("stuck_loop_risk", "low")
                ),
                "artifact_kind": (
                    "remediation_session"
                    if summary.flow_type == "remediation"
                    else "generated_content"
                ),
                "resource_id": (
                    self._maybe_str(request_context.get("remediation_session_id"))
                    if summary.flow_type == "remediation"
                    else generated_content.generation_id
                ),
                "remediation_session_id": self._maybe_str(
                    request_context.get("remediation_session_id")
                )
                if summary.flow_type == "remediation"
                else base.remediation_session_id,
                "next_step": summary.next_step,
                "continue_action": summary.continue_action,
                "rationale": summary.rationale,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        if remediation_data and str(remediation_data.get("status", "in_progress")) == "complete":
            updated = updated.model_copy(update={"status": "ready_for_next_step"})
        self.session_control_store.upsert(updated)
        return updated

    def _predictive_next_step(
        self,
        *,
        generated_content: GeneratedContent,
    ) -> LearnerFlowNextStep:
        request_context = generated_content.request_context
        progression = self._dict_value(request_context.get("progression"))
        forced_content_type = self._forced_next_step_content_type(progression)
        if forced_content_type is not None:
            return LearnerFlowNextStep(
                action=str(progression.get("action", "stay_on_requested_target")),
                content_type=forced_content_type,
                target_stage=str(progression.get("target_stage", "target")),
                target_kc_ids=self._string_list(
                    progression.get("applied_target_kc_ids")
                    or request_context.get("target_kc_ids")
                ),
                rationale=self._workflow_step_rationale(
                    primary=self._maybe_str(progression.get("mastery_gate_reason")),
                    action=str(progression.get("action", "stay_on_requested_target")),
                    target_stage=str(progression.get("target_stage", "target")),
                    fallback=self._maybe_str(progression.get("rationale")),
                ),
            )
        follow_ups = self.next_step_planner.plan(generated_content)
        if not follow_ups:
            return LearnerFlowNextStep(
                action=str(progression.get("action", "stay_on_requested_target")),
                target_stage=str(progression.get("target_stage", "target")),
                target_kc_ids=self._string_list(
                    progression.get("applied_target_kc_ids")
                    or request_context.get("target_kc_ids")
                ),
                rationale=self._workflow_step_rationale(
                    primary=self._maybe_str(progression.get("mastery_gate_reason")),
                    action=str(progression.get("action", "stay_on_requested_target")),
                    target_stage=str(progression.get("target_stage", "target")),
                    fallback=self._maybe_str(progression.get("rationale")),
                ),
            )
        next_content_type, next_reason = follow_ups[0]
        target_kc_ids = self._string_list(progression.get("applied_target_kc_ids"))
        if next_content_type.value == RequestedContentType.assessment_probe.value:
            target_kc_ids = (
                self._string_list(progression.get("transfer_target_kc_ids"))
                or target_kc_ids
            )
        return LearnerFlowNextStep(
            action=str(progression.get("action", "stay_on_requested_target")),
            content_type=next_content_type.value,
            target_stage=str(progression.get("target_stage", "target")),
            target_kc_ids=target_kc_ids
            or self._string_list(request_context.get("target_kc_ids")),
            rationale=self._workflow_step_rationale(
                primary=self._maybe_str(progression.get("mastery_gate_reason")),
                action=str(progression.get("action", "stay_on_requested_target")),
                target_stage=str(progression.get("target_stage", "target")),
                fallback=self._first_text(
                    progression.get("rationale"),
                    next_reason,
                ),
            ),
        )

    def _continue_action_for_lesson_content(
        self,
        *,
        generated_content: GeneratedContent,
        next_step: LearnerFlowNextStep,
    ) -> LearnerContinueAction:
        if next_step.content_type is None:
            return LearnerContinueAction.idle(rationale=next_step.rationale)
        request_context = generated_content.request_context
        return LearnerContinueAction.generate_follow_up(
            outcome_id=generated_content.generation_id,
            generation_id=generated_content.generation_id,
            learning_session_id=self._maybe_str(
                request_context.get("learning_session_id")
            ),
            content_type=next_step.content_type,
            target_stage=next_step.target_stage,
            target_kc_ids=list(next_step.target_kc_ids),
            request_payload=self._generation_request_payload(
                generated_content=generated_content,
                next_step=next_step,
            ),
            rationale=next_step.rationale,
        )

    def _continue_action_for_remediation_content(
        self,
        *,
        generated_content: GeneratedContent,
        request_context: dict[str, object],
        remediation_data: dict[str, object],
        next_step: LearnerFlowNextStep,
    ) -> LearnerContinueAction:
        session_id = self._maybe_str(request_context.get("remediation_session_id"))
        if session_id is None:
            return LearnerContinueAction.idle(rationale=next_step.rationale)
        if str(remediation_data.get("status", "in_progress")) == "complete":
            summary_continue_action = self._dict_value(
                remediation_data.get("summary_continue_action")
            )
            if summary_continue_action:
                return LearnerContinueAction.model_validate(summary_continue_action)
            target_kc_ids = list(next_step.target_kc_ids) or self._string_list(
                request_context.get("focus_kc_ids")
                or request_context.get("target_kc_ids")
            )
            follow_up_step = next_step.model_copy(
                update={
                    "content_type": RequestedContentType.practice_problem.value,
                    "target_stage": "transfer",
                    "target_kc_ids": target_kc_ids,
                    "rationale": decision_grade_rationale(
                        next_step.rationale,
                        action="attempt_transfer",
                        target_stage="transfer",
                        fallback="Return to the target skill after remediation.",
                    ),
                }
            )
            return LearnerContinueAction.generate_follow_up(
                outcome_id=session_id,
                generation_id=generated_content.generation_id,
                learning_session_id=self._maybe_str(
                    request_context.get("learning_session_id")
                ),
                content_type=follow_up_step.content_type,
                target_stage=follow_up_step.target_stage,
                target_kc_ids=list(follow_up_step.target_kc_ids),
                request_payload=self._generation_request_payload(
                    generated_content=generated_content,
                    next_step=follow_up_step,
                ),
                rationale=follow_up_step.rationale,
            )
        return LearnerContinueAction.advance_remediation(
            endpoint=f"/api/remedial/sessions/{session_id}/advance",
            outcome_id=session_id,
            generation_id=generated_content.generation_id,
            learning_session_id=self._maybe_str(
                request_context.get("learning_session_id")
            ),
            content_type=next_step.content_type,
            target_stage=next_step.target_stage,
            target_kc_ids=list(next_step.target_kc_ids),
            request_payload={
                "curriculum_context": list(
                    generated_content.response.curriculum_context
                ),
            },
            rationale=next_step.rationale,
        )

    def _continue_action_from_session(
        self, session: SessionControlState
    ) -> LearnerContinueAction:
        if session.next_step.content_type is None:
            return LearnerContinueAction.idle(rationale=session.next_step.rationale)
        return LearnerContinueAction.generate_follow_up(
            learning_session_id=session.learning_session_id,
            content_type=session.next_step.content_type,
            target_stage=session.next_step.target_stage,
            target_kc_ids=list(session.next_step.target_kc_ids),
            request_payload={
                "student_id": str(session.student_id),
                "learning_session_id": session.learning_session_id,
                "target_kc_ids": list(session.active_target_kc_ids),
                "target_lo_ids": list(session.target_lo_ids),
                "intent": _intent_for_content_type(session.next_step.content_type),
                "requested_content_type": session.next_step.content_type,
            },
            rationale=session.next_step.rationale,
        )

    def _generation_request_payload(
        self,
        *,
        generated_content: GeneratedContent,
        next_step: LearnerFlowNextStep,
    ) -> dict[str, object]:
        request_context = generated_content.request_context
        return {
            "student_id": str(generated_content.student_id),
            "learning_session_id": self._maybe_str(
                request_context.get("learning_session_id")
            ),
            "target_kc_ids": list(next_step.target_kc_ids),
            "target_lo_ids": self._string_list(request_context.get("target_lo_ids")),
            "intent": _intent_for_content_type(next_step.content_type),
            "requested_content_type": next_step.content_type,
            "curriculum_context": list(generated_content.response.curriculum_context),
            "source_generation_id": generated_content.generation_id,
        }

    def _initial_content_type_for_stage(self, stage: str) -> str:
        if stage == "repair":
            return RequestedContentType.remedial_micro_module.value
        if stage == "bridge":
            return RequestedContentType.practice_problem.value
        return RequestedContentType.micro_explanation.value

    def _content_type_for_remediation_phase(
        self,
        *,
        phase: object,
        progression_decision: str,
    ) -> str | None:
        if progression_decision == "hold_bridge_target":
            return RequestedContentType.practice_problem.value
        if progression_decision.startswith("hold_"):
            return RequestedContentType.remedial_micro_module.value
        if phase is None:
            return None
        if str(phase) == "return":
            return RequestedContentType.practice_problem.value
        return RequestedContentType.remedial_micro_module.value

    def _remediation_next_step_target_kc_ids(
        self,
        *,
        remediation_data: dict[str, object],
    ) -> list[str]:
        progression_decision = str(
            remediation_data.get("progression_decision", "advance")
        )
        if progression_decision.startswith("hold_"):
            return self._string_list(remediation_data.get("progression_target_kc_ids"))
        return self._string_list(remediation_data.get("next_step_target_kc_ids"))

    def _target_stage_for_remediation_next_step(
        self,
        *,
        phase: str,
        progression_decision: str,
    ) -> str:
        if progression_decision == "hold_bridge_target":
            return "bridge"
        if progression_decision.startswith("hold_"):
            return "repair"
        return self._target_stage_for_phase(phase)

    def _forced_next_step_content_type(
        self, progression: dict[str, object]
    ) -> str | None:
        action = str(progression.get("action", ""))
        if action in {"hold_target", "hold_target_before_assessment"}:
            return RequestedContentType.practice_problem.value
        if action == "hold_bridge_target":
            return RequestedContentType.practice_problem.value
        if action in {
            "rebuild_prerequisite_first",
            "rebuild_prerequisite_before_assessment",
            "hold_repair_target",
            "hold_repair_target_before_assessment",
        }:
            return RequestedContentType.remedial_micro_module.value
        if action == "bridge_before_assessment":
            return RequestedContentType.practice_problem.value
        return None

    def _workflow_step_rationale(
        self,
        *,
        primary: str | None,
        action: str | None = None,
        target_stage: str | None = None,
        fallback: str | None,
    ) -> str | None:
        return decision_grade_rationale(
            primary,
            action=action,
            target_stage=target_stage,
            fallback=fallback,
        )

    def _target_stage_for_phase(self, phase: str) -> str:
        if phase == "bridge":
            return "bridge"
        if phase == "return":
            return "transfer"
        return "repair"

    def _dict_value(self, value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None]

    def _maybe_str(self, value: object) -> str | None:
        return str(value) if value is not None else None

    def _first_text(self, *values: object) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
