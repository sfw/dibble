from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from dibble.models.assessment import SocraticAssessmentSession, SocraticNextAction
from dibble.models.generation import RequestedContentType
from dibble.models.profile import LearnerFlowNextStep, LearnerFlowSummary
from dibble.models.remediation import RemediationWorkflowSession
from dibble.models.session_adaptation import WithinSessionControllerState
from dibble.services.predictive_next_step_planner import PredictiveNextStepPlanner
from dibble.services.protocols import (
    AuditStore,
    GeneratedContentStore,
    RemediationSessionStore,
    SocraticSessionStore,
    WithinSessionControllerStore,
)


@dataclass(slots=True)
class LearnerFlowService:
    audit_store: AuditStore
    generated_content_store: GeneratedContentStore
    socratic_session_store: SocraticSessionStore
    remediation_session_store: RemediationSessionStore
    within_session_controller_store: WithinSessionControllerStore | None = None
    max_events: int = 300
    max_generated_content: int = 100
    next_step_planner: PredictiveNextStepPlanner = field(default_factory=PredictiveNextStepPlanner)

    def build_for_student(self, *, student_id: UUID) -> LearnerFlowSummary:
        events = [event for event in self.audit_store.list(limit=self.max_events) if event.student_id == student_id]

        candidates: list[tuple[int, datetime | None, LearnerFlowSummary]] = []
        remediation_flow = self._remediation_flow(events=events)
        if remediation_flow is not None:
            candidates.append((3, remediation_flow.updated_at, remediation_flow))

        socratic_flow = self._socratic_flow(events=events)
        if socratic_flow is not None:
            candidates.append((2, socratic_flow.updated_at, socratic_flow))

        generation_flow = self._generation_flow(student_id=student_id, events=events)
        if generation_flow is not None:
            candidates.append((1, generation_flow.updated_at, generation_flow))

        if not candidates:
            controller_flow = self._controller_flow(events=events)
            if controller_flow is not None:
                candidates.append((0, controller_flow.updated_at, controller_flow))

        if not candidates:
            return LearnerFlowSummary(updated_at=events[0].created_at if events else None)

        candidates.sort(
            key=lambda item: (
                item[1] or datetime.min,
                item[0],
            ),
            reverse=True,
        )
        return candidates[0][2]

    def _generation_flow(self, *, student_id: UUID, events) -> LearnerFlowSummary | None:
        generation_event = next((event for event in events if event.event_type == "content.generate"), None)
        latest_content = next(
            (
                content
                for content in self.generated_content_store.list_recent(limit=self.max_generated_content)
                if content.student_id == student_id
                and not bool(content.request_context.get("is_predictive_warm"))
                and (
                    generation_event is None
                    or content.generation_id == self._maybe_str(generation_event.payload.get("generation_id"))
                )
            ),
            None,
        )
        if latest_content is None and generation_event is None:
            return None

        request_context = latest_content.request_context if latest_content is not None else {}
        controller = self._controller_for_session(self._maybe_str(request_context.get("learning_session_id")))
        if controller is None and generation_event is not None:
            controller = self._controller_for_session(self._maybe_str(generation_event.payload.get("learning_session_id")))

        progression = self._progression_from_generation_event(generation_event)
        session_adaptation = (
            self._session_adaptation_from_controller(controller)
            if controller is not None
            else self._session_adaptation_from_request_context(request_context)
        )
        next_content_type, next_reason = self._next_step_from_predictive_event(
            events=events,
            generation_id=self._maybe_str(generation_event.payload.get("generation_id")) if generation_event is not None else None,
        )
        if next_content_type is None:
            next_steps = self.next_step_planner.plan(latest_content) if latest_content is not None else []
            next_content_type, next_reason = next_steps[0] if next_steps else (None, None)

        active_target_kc_ids = self._string_list(
            progression.get("applied_target_kc_ids")
            or (
                generation_event.payload.get("target_kc_ids")
                if generation_event is not None
                else request_context.get("target_kc_ids")
            )
        )
        target_stage = str(progression.get("target_stage", "target"))
        progression_action = str(
            progression.get("action")
            or session_adaptation.get("sequence_action")
            or "stay_on_requested_target"
        )

        return LearnerFlowSummary(
            status="ready_for_next_step" if next_content_type is not None else "idle",
            flow_type="lesson",
            learning_session_id=(
                self._maybe_str(generation_event.payload.get("learning_session_id"))
                if generation_event is not None
                else self._maybe_str(request_context.get("learning_session_id"))
            ),
            current_phase=str(session_adaptation.get("phase") or target_stage),
            current_content_type=(
                latest_content.content_type
                if latest_content is not None
                else self._maybe_str(generation_event.payload.get("content_type"))
            ),
            last_generation_id=(
                latest_content.generation_id
                if latest_content is not None
                else self._maybe_str(generation_event.payload.get("generation_id"))
            ),
            progression_action=progression_action,
            target_stage=target_stage,
            active_target_kc_ids=active_target_kc_ids,
            deferred_target_kc_ids=self._string_list(progression.get("deferred_target_kc_ids")),
            transfer_target_kc_ids=self._string_list(progression.get("transfer_target_kc_ids")),
            session_phase=str(session_adaptation.get("phase", "monitor")),
            session_arc_action=str(session_adaptation.get("arc_action", "steady")),
            session_stuck_loop_risk=str(session_adaptation.get("stuck_loop_risk", "low")),
            rationale=self._first_text(
                progression.get("mastery_gate_reason"),
                progression.get("rationale"),
                session_adaptation.get("rationale"),
                request_context.get("selection_rationale"),
            ),
            next_step=LearnerFlowNextStep(
                action=progression_action,
                content_type=next_content_type.value if next_content_type is not None else None,
                target_stage=target_stage,
                target_kc_ids=self._next_step_target_kc_ids(
                    progression=progression,
                    fallback_target_kc_ids=active_target_kc_ids,
                    next_content_type=next_content_type,
                ),
                rationale=self._first_text(next_reason, progression.get("mastery_gate_reason"), progression.get("rationale")),
            ),
            updated_at=(
                latest_content.created_at
                if latest_content is not None
                else generation_event.created_at
            ),
        )

    def _remediation_flow(self, *, events) -> LearnerFlowSummary | None:
        remediation_event = next(
            (event for event in events if event.event_type in {"remediation.advance", "remediation.trigger"}),
            None,
        )
        if remediation_event is None:
            return None
        session_id = remediation_event.payload.get("remediation_session_id")
        if session_id is None:
            return None
        session = self.remediation_session_store.get(str(session_id))
        if session is None:
            return None

        current_step = self._current_remediation_step(session)
        hold_next_step = self._held_remediation_next_step(session)
        next_step = hold_next_step or self._planned_remediation_next_step(session, current_step=current_step)
        current_phase = current_step.phase if current_step is not None else "complete"
        target_stage = self._remediation_target_stage(
            decision=session.progression_decision,
            phase=current_phase,
        )

        return LearnerFlowSummary(
            status="complete" if session.current_step_index is None else "in_progress",
            flow_type="remediation",
            learning_session_id=session.session_id,
            remediation_session_id=session.session_id,
            current_phase=current_phase,
            current_content_type=self._maybe_str(next_step.content_type),
            progression_action=session.progression_decision,
            target_stage=target_stage,
            active_target_kc_ids=list(next_step.target_kc_ids),
            deferred_target_kc_ids=list(session.kc_sequence.deferred_kc_ids),
            transfer_target_kc_ids=list(session.kc_sequence.deferred_kc_ids),
            rationale=self._first_text(session.progression_rationale, session.rationale),
            next_step=next_step,
            updated_at=session.updated_at,
        )

    def _socratic_flow(self, *, events) -> LearnerFlowSummary | None:
        assessment_event = next((event for event in events if event.event_type == "assessment.socratic"), None)
        if assessment_event is None:
            return None
        session_id = assessment_event.payload.get("session_id")
        if session_id is None:
            return None
        session = self.socratic_session_store.get(str(session_id))
        if session is None or not isinstance(session, SocraticAssessmentSession) or not session.turns:
            return None

        latest_turn = session.turns[-1]
        next_content_type = self._socratic_next_content_type(latest_turn.evaluation.next_action)
        target_stage = "transfer" if latest_turn.evaluation.next_action == SocraticNextAction.advance else "assessment"
        if latest_turn.evaluation.next_action == SocraticNextAction.step_back:
            target_stage = "repair"

        return LearnerFlowSummary(
            status="ready_for_follow_up" if latest_turn.evaluation.next_action == SocraticNextAction.advance else "in_progress",
            flow_type="socratic_assessment",
            learning_session_id=session.learning_session_id,
            socratic_session_id=session.session_id,
            current_phase=latest_turn.prompt_style.value,
            current_content_type="assessment_probe",
            progression_action=latest_turn.evaluation.next_action.value,
            target_stage=target_stage,
            active_target_kc_ids=list(session.target_kc_ids),
            rationale=self._first_text(latest_turn.evaluation.rationale, latest_turn.policy_rationale),
            next_step=LearnerFlowNextStep(
                action=latest_turn.steering_action.value,
                content_type=next_content_type.value if next_content_type is not None else None,
                target_stage=target_stage,
                target_kc_ids=list(session.target_kc_ids),
                rationale=self._first_text(latest_turn.evaluation.rationale, latest_turn.policy_rationale),
            ),
            updated_at=session.updated_at,
        )

    def _controller_flow(self, *, events) -> LearnerFlowSummary | None:
        if self.within_session_controller_store is None:
            return None
        learning_session_id = next(
            (
                self._maybe_str(event.payload.get("learning_session_id"))
                for event in events
                if event.payload.get("learning_session_id")
            ),
            None,
        )
        if learning_session_id is None:
            return None
        controller = self.within_session_controller_store.get(learning_session_id)
        if controller is None:
            return None

        next_content_type = self._controller_next_content_type(controller)
        return LearnerFlowSummary(
            status="in_progress",
            flow_type="session_controller",
            learning_session_id=controller.learning_session_id,
            current_phase=controller.phase,
            progression_action=controller.sequence_action,
            target_stage=self._controller_target_stage(controller),
            active_target_kc_ids=list(controller.target_kc_ids),
            session_phase=controller.phase,
            session_arc_action=controller.arc_action,
            session_stuck_loop_risk=controller.stuck_loop_risk,
            rationale=controller.rationale,
            next_step=LearnerFlowNextStep(
                action=controller.arc_action,
                content_type=next_content_type.value if next_content_type is not None else None,
                target_stage=self._controller_target_stage(controller),
                target_kc_ids=list(controller.target_kc_ids),
                rationale=controller.rationale,
            ),
            updated_at=controller.updated_at,
        )

    def _session_adaptation_from_request_context(self, request_context: dict[str, object]) -> dict[str, object]:
        session_adaptation = self._dict_value(request_context.get("session_adaptation"))
        if session_adaptation:
            return session_adaptation
        mode_calibration = self._dict_value(request_context.get("mode_calibration"))
        if not mode_calibration or mode_calibration.get("session_signal") in {None, "insufficient"}:
            return {}
        return {
            "phase": mode_calibration.get("session_phase"),
            "arc_action": mode_calibration.get("session_arc_action"),
            "stuck_loop_risk": mode_calibration.get("session_stuck_loop_risk"),
            "sequence_action": mode_calibration.get("session_sequence_action"),
            "rationale": mode_calibration.get("session_rationale"),
        }

    def _session_adaptation_from_controller(
        self,
        controller: WithinSessionControllerState,
    ) -> dict[str, object]:
        return {
            "phase": controller.phase,
            "arc_action": controller.arc_action,
            "stuck_loop_risk": controller.stuck_loop_risk,
            "sequence_action": controller.sequence_action,
            "rationale": controller.rationale,
        }

    def _progression_from_generation_event(self, generation_event) -> dict[str, object]:
        if generation_event is None:
            return {}
        payload = generation_event.payload
        return {
            "action": payload.get("progression_action"),
            "target_stage": payload.get("progression_target_stage"),
            "target_redirect_applied": payload.get("progression_target_redirect_applied"),
            "requested_target_kc_ids": payload.get("requested_target_kc_ids"),
            "applied_target_kc_ids": payload.get("applied_target_kc_ids"),
            "transfer_target_kc_ids": payload.get("progression_transfer_target_kc_ids"),
            "deferred_target_kc_ids": payload.get("progression_deferred_target_kc_ids"),
            "bridge_kc_ids": payload.get("progression_bridge_kc_ids"),
            "rationale": payload.get("progression_rationale"),
            "requested_content_type": payload.get("progression_requested_content_type"),
            "applied_content_type": payload.get("progression_applied_content_type"),
            "mastery_gate_applied": payload.get("progression_mastery_gate_applied"),
            "mastery_gate_reason": payload.get("progression_mastery_gate_reason"),
            "observation_count": payload.get("progression_evidence_observation_count"),
            "assessment_count": payload.get("progression_evidence_assessment_count"),
            "confidence": payload.get("progression_evidence_confidence"),
            "average_observed_mastery": payload.get("progression_average_observed_mastery"),
            "average_assessment_mastery": payload.get("progression_average_assessment_mastery"),
        }

    def _planned_remediation_next_step(
        self,
        session: RemediationWorkflowSession,
        *,
        current_step,
    ) -> LearnerFlowNextStep:
        if current_step is None:
            return LearnerFlowNextStep(
                action="complete",
                content_type=None,
                target_stage="transfer",
                target_kc_ids=list(session.kc_sequence.deferred_kc_ids or session.focus_kc_ids),
                rationale="The remediation workflow is complete.",
            )
        return LearnerFlowNextStep(
            action=current_step.phase,
            content_type=current_step.recommended_content_type.value,
            target_stage=self._remediation_target_stage(decision=session.progression_decision, phase=current_step.phase),
            target_kc_ids=list(current_step.target_kc_ids),
            rationale=self._first_text(session.progression_rationale, current_step.guidance, session.rationale),
        )

    def _held_remediation_next_step(self, session: RemediationWorkflowSession) -> LearnerFlowNextStep | None:
        if not session.progression_decision.startswith("hold_"):
            return None
        target_stage = "bridge" if session.progression_decision == "hold_bridge_target" else "repair"
        content_type = (
            RequestedContentType.practice_problem.value
            if session.progression_decision == "hold_bridge_target"
            else RequestedContentType.remedial_micro_module.value
        )
        return LearnerFlowNextStep(
            action=session.progression_decision,
            content_type=content_type,
            target_stage=target_stage,
            target_kc_ids=list(session.progression_target_kc_ids),
            rationale=session.progression_rationale,
        )

    def _current_remediation_step(self, session: RemediationWorkflowSession):
        if session.current_step_index is None or session.current_step_index >= len(session.steps):
            return None
        return session.steps[session.current_step_index]

    def _remediation_target_stage(self, *, decision: str, phase: str) -> str:
        if decision == "hold_bridge_target" or phase == "bridge":
            return "bridge"
        if decision == "advance" and phase == "return":
            return "transfer"
        if decision == "complete":
            return "transfer"
        return "repair"

    def _socratic_next_content_type(self, next_action: SocraticNextAction) -> RequestedContentType:
        if next_action == SocraticNextAction.step_back:
            return RequestedContentType.remedial_micro_module
        if next_action == SocraticNextAction.advance:
            return RequestedContentType.practice_problem
        return RequestedContentType.assessment_probe

    def _controller_next_content_type(self, controller: WithinSessionControllerState) -> RequestedContentType:
        if controller.phase == "transfer_check" or controller.sequence_action == "attempt_transfer":
            return RequestedContentType.assessment_probe
        if controller.phase in {"stabilize", "repair"}:
            return RequestedContentType.remedial_micro_module
        return RequestedContentType.practice_problem

    def _controller_for_session(self, learning_session_id: str | None) -> WithinSessionControllerState | None:
        if learning_session_id is None or self.within_session_controller_store is None:
            return None
        return self.within_session_controller_store.get(learning_session_id)

    def _controller_target_stage(self, controller: WithinSessionControllerState) -> str:
        if controller.phase == "bridge":
            return "bridge"
        if controller.phase == "transfer_check" or controller.sequence_action == "attempt_transfer":
            return "transfer"
        if controller.phase in {"stabilize", "repair"}:
            return "repair"
        return "target"

    def _next_step_target_kc_ids(
        self,
        *,
        progression: dict[str, object],
        fallback_target_kc_ids: list[str],
        next_content_type: RequestedContentType | None,
    ) -> list[str]:
        if next_content_type == RequestedContentType.assessment_probe:
            transfer_target_kc_ids = self._string_list(progression.get("transfer_target_kc_ids"))
            if transfer_target_kc_ids:
                return transfer_target_kc_ids
        applied_target_kc_ids = self._string_list(progression.get("applied_target_kc_ids"))
        return applied_target_kc_ids or fallback_target_kc_ids

    def _next_step_from_predictive_event(
        self,
        *,
        events,
        generation_id: str | None,
    ) -> tuple[RequestedContentType | None, str | None]:
        if generation_id is None:
            return None, None
        predictive_event = next(
            (
                event
                for event in events
                if event.event_type == "content.warm.predictive"
                and event.payload.get("source_generation_id") == generation_id
            ),
            None,
        )
        if predictive_event is None:
            return None, None
        content_types = predictive_event.payload.get("predicted_content_types")
        reasons = predictive_event.payload.get("warm_reasons")
        if not isinstance(content_types, list) or not content_types:
            return None, None
        try:
            next_content_type = RequestedContentType(str(content_types[0]))
        except ValueError:
            return None, None
        next_reason = None
        if isinstance(reasons, list) and reasons:
            next_reason = self._maybe_str(reasons[0])
        return next_content_type, next_reason

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
