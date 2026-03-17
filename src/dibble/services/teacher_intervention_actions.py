from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.auth import AuthIdentity
from dibble.models.generation import RequestedContentType
from dibble.models.profile import ContinueActionKind, LearnerContinueAction, LearnerFlowSummary
from dibble.models.teacher_actions import (
    TeacherInterventionActionContract,
    TeacherInterventionDecision,
    TeacherInterventionDecisionRecord,
    TeacherInterventionDecisionRequest,
    TeacherInterventionDecisionStatus,
    TeacherInterventionOption,
    TeacherInterventionProposalStatus,
)
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.protocols import AuditStore


class TeacherInterventionActionUnavailableError(RuntimeError):
    """Raised when no current backend-owned intervention action is available."""


class TeacherInterventionOptionNotFoundError(RuntimeError):
    """Raised when a selected teacher intervention option is unavailable."""


@dataclass(slots=True)
class TeacherInterventionActionService:
    audit_store: AuditStore
    learner_flow_service: LearnerFlowService
    max_events: int = 300

    def build_for_student(self, *, student_id: UUID) -> TeacherInterventionActionContract:
        flow = self.learner_flow_service.build_for_student(student_id=student_id)
        action_key = self._action_key_for_flow(flow)
        proposal_available = flow.continue_action.kind != ContinueActionKind.idle
        available_options = self._available_options_for(student_id=student_id, flow=flow) if proposal_available else []
        return TeacherInterventionActionContract(
            action_key=action_key,
            proposal_status=(
                TeacherInterventionProposalStatus.available
                if proposal_available
                else TeacherInterventionProposalStatus.unavailable
            ),
            flow_type=flow.flow_type,
            learning_session_id=flow.learning_session_id,
            remediation_session_id=flow.remediation_session_id,
            socratic_session_id=flow.socratic_session_id,
            progression_action=flow.progression_action,
            target_stage=flow.target_stage,
            active_target_kc_ids=list(flow.active_target_kc_ids),
            current_phase=flow.current_phase,
            rationale=flow.rationale,
            next_step=flow.next_step.model_copy(),
            proposed_action=flow.continue_action.model_copy(),
            available_options=available_options,
            allowed_decisions=self._allowed_decisions_for(
                proposal_available=proposal_available,
                option_count=len(available_options),
            ),
            latest_decision=self._latest_decision(student_id=student_id, action_key=action_key),
            updated_at=flow.updated_at,
        )

    def record_decision(
        self,
        *,
        student_id: UUID,
        decision: TeacherInterventionDecisionRequest,
        identity: AuthIdentity | None = None,
    ) -> TeacherInterventionActionContract:
        contract = self.build_for_student(student_id=student_id)
        if contract.proposal_status != TeacherInterventionProposalStatus.available:
            raise TeacherInterventionActionUnavailableError("No teacher-approvable intervention is available.")
        parsed_decision = self._parse_decision(decision.decision)

        selected_option = self._selected_option(contract=contract, decision=decision, parsed_decision=parsed_decision)
        execution_action = self._execution_action_for(
            contract=contract,
            decision=parsed_decision,
            selected_option=selected_option,
        )
        decision_status = self._status_for(parsed_decision)
        event = self.audit_store.append(
            event_type="teacher.intervention.decision",
            status="success",
            student_id=str(student_id),
            payload={
                "action_key": contract.action_key,
                "decision": parsed_decision.value,
                "status": decision_status.value,
                "selected_option_id": selected_option.option_id if selected_option is not None else None,
                "note": decision.note,
                "decided_by": identity.principal_id if identity is not None else None,
                "decided_role": identity.role if identity is not None else None,
                "flow_type": contract.flow_type,
                "learning_session_id": contract.learning_session_id,
                "remediation_session_id": contract.remediation_session_id,
                "socratic_session_id": contract.socratic_session_id,
                "current_phase": contract.current_phase,
                "progression_action": contract.progression_action,
                "target_stage": contract.target_stage,
                "active_target_kc_ids": list(contract.active_target_kc_ids),
                "rationale": contract.rationale,
                "next_step": contract.next_step.model_dump(mode="json"),
                "proposed_action": contract.proposed_action.model_dump(mode="json"),
                "available_options": [option.model_dump(mode="json") for option in contract.available_options],
                "execution_action": execution_action.model_dump(mode="json"),
            },
        )
        return contract.model_copy(
            update={
                "latest_decision": TeacherInterventionDecisionRecord(
                    action_key=contract.action_key,
                    decision_id=event.event_id,
                    decision=parsed_decision,
                    status=decision_status,
                    selected_option_id=selected_option.option_id if selected_option is not None else None,
                    note=decision.note,
                    decided_by=identity.principal_id if identity is not None else None,
                    decided_role=identity.role if identity is not None else None,
                    decided_at=event.created_at,
                    execution_action=execution_action,
                )
            }
        )

    def _latest_decision(self, *, student_id: UUID, action_key: str) -> TeacherInterventionDecisionRecord | None:
        event = next(
            (
                candidate
                for candidate in self.audit_store.list(limit=self.max_events)
                if candidate.student_id == student_id
                and candidate.event_type == "teacher.intervention.decision"
                and candidate.payload.get("action_key") == action_key
            ),
            None,
        )
        if event is None:
            return None
        return TeacherInterventionDecisionRecord(
            action_key=action_key,
            decision_id=event.event_id,
            decision=self._decision_from_value(event.payload.get("decision")),
            status=self._decision_status_from_value(event.payload.get("status")),
            selected_option_id=self._maybe_str(event.payload.get("selected_option_id")),
            note=self._maybe_str(event.payload.get("note")),
            decided_by=self._maybe_str(event.payload.get("decided_by")),
            decided_role=self._maybe_str(event.payload.get("decided_role")),
            decided_at=event.created_at,
            execution_action=LearnerContinueAction.model_validate(event.payload.get("execution_action") or {}),
        )

    def _available_options_for(
        self,
        *,
        student_id: UUID,
        flow: LearnerFlowSummary,
    ) -> list[TeacherInterventionOption]:
        proposed_action = flow.continue_action
        options: list[TeacherInterventionOption] = [
            TeacherInterventionOption(
                option_id="recommended",
                label=self._label_for_action(proposed_action, fallback="Recommended next step"),
                rationale=flow.rationale or proposed_action.rationale,
                is_recommended=True,
                continue_action=proposed_action.model_copy(),
            )
        ]

        if proposed_action.kind not in {
            ContinueActionKind.generate_follow_up,
            ContinueActionKind.continue_socratic,
        }:
            return options

        target_kc_ids = list(proposed_action.target_kc_ids or flow.active_target_kc_ids)
        if not target_kc_ids:
            return options

        lesson_payload = self._base_generation_payload(
            student_id=student_id,
            flow=flow,
            proposed_action=proposed_action,
        )
        if not lesson_payload:
            return options

        current_type = proposed_action.content_type
        if current_type != RequestedContentType.worked_example.value:
            options.append(
                self._generation_option(
                    option_id="worked_example_support_reset",
                    label=self._label_for_content_type(
                        content_type=RequestedContentType.worked_example.value,
                        target_stage="target" if flow.target_stage == "transfer" else flow.target_stage,
                        fallback="Worked Example",
                    ),
                    rationale="Offer a more supported worked example on the active target before continuing.",
                    base_payload=lesson_payload,
                    learning_session_id=flow.learning_session_id,
                    source_generation_id=proposed_action.generation_id,
                    content_type=RequestedContentType.worked_example.value,
                    target_stage="target" if flow.target_stage == "transfer" else flow.target_stage,
                    target_kc_ids=target_kc_ids,
                )
            )
        if current_type != RequestedContentType.practice_problem.value:
            options.append(
                self._generation_option(
                    option_id="practice_problem_same_target",
                    label=self._label_for_content_type(
                        content_type=RequestedContentType.practice_problem.value,
                        target_stage=flow.target_stage,
                        fallback="Practice Problem",
                    ),
                    rationale="Stay on the same target with another practice step before moving on.",
                    base_payload=lesson_payload,
                    learning_session_id=flow.learning_session_id,
                    source_generation_id=proposed_action.generation_id,
                    content_type=RequestedContentType.practice_problem.value,
                    target_stage=flow.target_stage,
                    target_kc_ids=target_kc_ids,
                )
            )
        if flow.target_stage == "transfer" and current_type != RequestedContentType.assessment_probe.value:
            options.append(
                self._generation_option(
                    option_id="assessment_probe_transfer_check",
                    label=self._label_for_content_type(
                        content_type=RequestedContentType.assessment_probe.value,
                        target_stage="transfer",
                        fallback="Assessment Probe",
                    ),
                    rationale="Verify transfer explicitly before assigning more independent work.",
                    base_payload=lesson_payload,
                    learning_session_id=flow.learning_session_id,
                    source_generation_id=proposed_action.generation_id,
                    content_type=RequestedContentType.assessment_probe.value,
                    target_stage="transfer",
                    target_kc_ids=target_kc_ids,
                )
            )
        return options

    def _selected_option(
        self,
        *,
        contract: TeacherInterventionActionContract,
        decision: TeacherInterventionDecisionRequest,
        parsed_decision: TeacherInterventionDecision,
    ) -> TeacherInterventionOption | None:
        if parsed_decision == TeacherInterventionDecision.approve:
            return next((option for option in contract.available_options if option.is_recommended), None)
        if parsed_decision != TeacherInterventionDecision.select_option:
            return None
        if decision.option_id is None:
            raise ValueError("Selecting an intervention option requires option_id.")
        selected = next(
            (option for option in contract.available_options if option.option_id == decision.option_id),
            None,
        )
        if selected is None:
            raise TeacherInterventionOptionNotFoundError("Teacher intervention option is not available.")
        return selected

    @staticmethod
    def _action_key_for_flow(flow: LearnerFlowSummary) -> str:
        if flow.remediation_session_id is not None:
            return f"remediation:{flow.remediation_session_id}"
        if flow.socratic_session_id is not None:
            return f"socratic:{flow.socratic_session_id}"
        if flow.last_generation_id is not None:
            return f"generation:{flow.last_generation_id}"
        if flow.learning_session_id is not None:
            return f"session:{flow.learning_session_id}"
        return f"idle:{flow.flow_type}"

    @staticmethod
    def _execution_action_for(
        *,
        contract: TeacherInterventionActionContract,
        decision: TeacherInterventionDecision,
        selected_option: TeacherInterventionOption | None,
    ) -> LearnerContinueAction:
        if decision in {TeacherInterventionDecision.approve, TeacherInterventionDecision.select_option}:
            return (
                selected_option.continue_action.model_copy()
                if selected_option is not None
                else contract.proposed_action.model_copy()
            )
        return LearnerContinueAction.idle(
            rationale=(
                "Teacher deferred the backend-recommended intervention."
                if decision == TeacherInterventionDecision.defer
                else "Teacher escalated this intervention for human review."
            ),
        )

    @staticmethod
    def _status_for(decision: TeacherInterventionDecision) -> TeacherInterventionDecisionStatus:
        mapping = {
            TeacherInterventionDecision.approve: TeacherInterventionDecisionStatus.approved,
            TeacherInterventionDecision.select_option: TeacherInterventionDecisionStatus.option_selected,
            TeacherInterventionDecision.defer: TeacherInterventionDecisionStatus.deferred,
            TeacherInterventionDecision.escalate_human: TeacherInterventionDecisionStatus.escalated_human,
        }
        return mapping[decision]

    @staticmethod
    def _maybe_str(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _label_for_action(action: LearnerContinueAction, *, fallback: str) -> str:
        if action.kind == ContinueActionKind.advance_remediation:
            return "Advance Remediation"
        if action.kind == ContinueActionKind.continue_socratic:
            return "Continue Socratic"
        return TeacherInterventionActionService._label_for_content_type(
            content_type=action.content_type,
            target_stage=action.target_stage,
            fallback=fallback,
        )

    @staticmethod
    def _label_for_content_type(
        *,
        content_type: str | None,
        target_stage: str,
        fallback: str,
    ) -> str:
        if content_type == RequestedContentType.micro_explanation.value:
            if target_stage == "repair":
                return "Repair Explanation"
            if target_stage == "bridge":
                return "Bridge Explanation"
            if target_stage == "transfer":
                return "Transfer Explanation"
            return "Micro Explanation"
        if content_type == RequestedContentType.worked_example.value:
            if target_stage == "repair":
                return "Repair Worked Example"
            if target_stage == "bridge":
                return "Bridge Worked Example"
            if target_stage == "transfer":
                return "Transfer Worked Example"
            return "Worked Example"
        if content_type == RequestedContentType.practice_problem.value:
            if target_stage == "repair":
                return "Repair Practice"
            if target_stage == "bridge":
                return "Bridge Practice"
            if target_stage == "transfer":
                return "Transfer Practice"
            return "Practice Problem"
        if content_type == RequestedContentType.assessment_probe.value:
            if target_stage == "transfer":
                return "Transfer Check"
            return "Assessment Probe"
        return fallback

    def _base_generation_payload(
        self,
        *,
        student_id: UUID,
        flow: LearnerFlowSummary,
        proposed_action: LearnerContinueAction,
    ) -> dict[str, object]:
        payload = dict(proposed_action.request_payload)
        payload["student_id"] = str(student_id)
        if flow.learning_session_id is not None:
            payload["learning_session_id"] = flow.learning_session_id
        if proposed_action.target_kc_ids or flow.active_target_kc_ids:
            payload["target_kc_ids"] = list(proposed_action.target_kc_ids or flow.active_target_kc_ids)
        if "curriculum_context" not in payload:
            payload["curriculum_context"] = []
        return payload

    def _generation_option(
        self,
        *,
        option_id: str,
        label: str,
        rationale: str,
        base_payload: dict[str, object],
        learning_session_id: str | None,
        source_generation_id: str | None,
        content_type: str,
        target_stage: str,
        target_kc_ids: list[str],
    ) -> TeacherInterventionOption:
        payload = dict(base_payload)
        payload["requested_content_type"] = content_type
        payload["intent"] = self._intent_for_content_type(content_type)
        payload["target_kc_ids"] = list(target_kc_ids)
        if source_generation_id is not None:
            payload["source_generation_id"] = source_generation_id
        return TeacherInterventionOption(
            option_id=option_id,
            label=label,
            rationale=rationale,
            continue_action=LearnerContinueAction.generate_follow_up(
                resource_id=source_generation_id,
                generation_id=source_generation_id,
                learning_session_id=learning_session_id,
                content_type=content_type,
                target_stage=target_stage,
                target_kc_ids=list(target_kc_ids),
                request_payload=payload,
                rationale=rationale,
            ),
        )

    @staticmethod
    def _intent_for_content_type(content_type: str) -> str:
        mapping = {
            RequestedContentType.micro_explanation.value: "explanation",
            RequestedContentType.worked_example.value: "explanation",
            RequestedContentType.practice_problem.value: "practice",
            RequestedContentType.assessment_probe.value: "assessment",
            RequestedContentType.remedial_micro_module.value: "remediation",
        }
        return mapping.get(content_type, "explanation")

    @staticmethod
    def _allowed_decisions_for(
        *,
        proposal_available: bool,
        option_count: int,
    ) -> list[TeacherInterventionDecision]:
        if not proposal_available:
            return []
        decisions = [
            TeacherInterventionDecision.approve,
            TeacherInterventionDecision.defer,
            TeacherInterventionDecision.escalate_human,
        ]
        if option_count > 1:
            decisions.insert(1, TeacherInterventionDecision.select_option)
        return decisions

    @staticmethod
    def _parse_decision(value: str) -> TeacherInterventionDecision:
        try:
            return TeacherInterventionDecision(value)
        except ValueError as exc:
            raise ValueError("Unsupported teacher intervention decision.") from exc

    @staticmethod
    def _decision_from_value(value: object) -> TeacherInterventionDecision:
        try:
            return TeacherInterventionDecision(str(value or TeacherInterventionDecision.defer.value))
        except ValueError:
            return TeacherInterventionDecision.defer

    @staticmethod
    def _decision_status_from_value(value: object) -> TeacherInterventionDecisionStatus:
        try:
            return TeacherInterventionDecisionStatus(str(value or TeacherInterventionDecisionStatus.deferred.value))
        except ValueError:
            return TeacherInterventionDecisionStatus.deferred
