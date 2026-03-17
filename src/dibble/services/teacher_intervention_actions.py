from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.auth import AuthIdentity
from dibble.models.profile import LearnerContinueAction, LearnerFlowSummary
from dibble.models.teacher_actions import (
    TeacherInterventionActionContract,
    TeacherInterventionDecisionRecord,
    TeacherInterventionDecisionRequest,
)
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.protocols import AuditStore


class TeacherInterventionActionUnavailableError(RuntimeError):
    """Raised when no current backend-owned intervention action is available."""


@dataclass(slots=True)
class TeacherInterventionActionService:
    audit_store: AuditStore
    learner_flow_service: LearnerFlowService
    max_events: int = 300

    def build_for_student(self, *, student_id: UUID) -> TeacherInterventionActionContract:
        flow = self.learner_flow_service.build_for_student(student_id=student_id)
        action_key = self._action_key_for_flow(flow)
        proposal_available = flow.continue_action.kind != "idle"
        return TeacherInterventionActionContract(
            action_key=action_key,
            proposal_status="available" if proposal_available else "unavailable",
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
            allowed_decisions=(["approve", "defer", "escalate_human"] if proposal_available else []),
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
        if contract.proposal_status != "available":
            raise TeacherInterventionActionUnavailableError("No teacher-approvable intervention is available.")
        if decision.decision not in {"approve", "defer", "escalate_human"}:
            raise ValueError("Unsupported teacher intervention decision.")

        execution_action = self._execution_action_for(contract=contract, decision=decision.decision)
        event = self.audit_store.append(
            event_type="teacher.intervention.decision",
            status="success",
            student_id=str(student_id),
            payload={
                "action_key": contract.action_key,
                "decision": decision.decision,
                "status": self._status_for(decision.decision),
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
                "execution_action": execution_action.model_dump(mode="json"),
            },
        )
        return contract.model_copy(
            update={
                "latest_decision": TeacherInterventionDecisionRecord(
                    action_key=contract.action_key,
                    decision_id=event.event_id,
                    decision=decision.decision,
                    status=self._status_for(decision.decision),
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
            decision=str(event.payload.get("decision") or "defer"),
            status=str(event.payload.get("status") or "deferred"),
            note=self._maybe_str(event.payload.get("note")),
            decided_by=self._maybe_str(event.payload.get("decided_by")),
            decided_role=self._maybe_str(event.payload.get("decided_role")),
            decided_at=event.created_at,
            execution_action=LearnerContinueAction.model_validate(event.payload.get("execution_action") or {}),
        )

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
        decision: str,
    ) -> LearnerContinueAction:
        if decision == "approve":
            return contract.proposed_action.model_copy()
        return LearnerContinueAction(
            kind="idle",
            rationale=(
                "Teacher deferred the backend-recommended intervention."
                if decision == "defer"
                else "Teacher escalated this intervention for human review."
            ),
        )

    @staticmethod
    def _status_for(decision: str) -> str:
        mapping = {
            "approve": "approved",
            "defer": "deferred",
            "escalate_human": "escalated_human",
        }
        return mapping[decision]

    @staticmethod
    def _maybe_str(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
