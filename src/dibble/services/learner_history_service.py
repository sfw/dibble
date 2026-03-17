from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.history import (
    LearnerGenerationHistoryEntry,
    LearnerRemediationSessionHistoryEntry,
    LearnerSocraticSessionHistoryEntry,
)
from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep
from dibble.services.protocols import GeneratedContentStore, RemediationSessionStore, SocraticSessionStore


@dataclass(slots=True)
class LearnerHistoryService:
    generated_content_store: GeneratedContentStore
    socratic_session_store: SocraticSessionStore
    remediation_session_store: RemediationSessionStore
    default_limit: int = 20

    def list_generation_history(
        self,
        *,
        student_id: UUID,
        limit: int | None = None,
    ) -> list[LearnerGenerationHistoryEntry]:
        entries = self.generated_content_store.list_recent_for_student(
            student_id=str(student_id),
            limit=limit or self.default_limit,
            include_predictive_warm=False,
        )
        history: list[LearnerGenerationHistoryEntry] = []
        for content in entries:
            workflow_summary = content.workflow_summary
            request_context = content.request_context
            history.append(
                LearnerGenerationHistoryEntry(
                    generation_id=content.generation_id,
                    learning_session_id=self._maybe_str(
                        workflow_summary.learning_session_id if workflow_summary is not None else None
                    )
                    or self._maybe_str(request_context.get("learning_session_id")),
                    source_generation_id=self._maybe_str(request_context.get("source_generation_id")),
                    content_type=content.content_type,
                    flow_type=workflow_summary.flow_type if workflow_summary is not None else "lesson",
                    status=workflow_summary.status if workflow_summary is not None else "delivered",
                    delivered_phase=workflow_summary.delivered_phase if workflow_summary is not None else "target",
                    progression_action=(
                        workflow_summary.progression_action
                        if workflow_summary is not None
                        else "stay_on_requested_target"
                    ),
                    target_stage=workflow_summary.target_stage if workflow_summary is not None else "target",
                    active_target_kc_ids=(
                        list(workflow_summary.active_target_kc_ids)
                        if workflow_summary is not None
                        else self._string_list(request_context.get("target_kc_ids"))
                    ),
                    intervention_type=content.response.route.intervention_type.value,
                    rationale=workflow_summary.rationale if workflow_summary is not None else None,
                    next_step=(
                        workflow_summary.next_step.model_copy()
                        if workflow_summary is not None
                        else LearnerFlowNextStep()
                    ),
                    continue_action=(
                        workflow_summary.continue_action.model_copy()
                        if workflow_summary is not None
                        else LearnerContinueAction()
                    ),
                    created_at=content.created_at,
                )
            )
        return history

    def list_socratic_session_history(
        self,
        *,
        student_id: UUID,
        limit: int | None = None,
    ) -> list[LearnerSocraticSessionHistoryEntry]:
        sessions = self.socratic_session_store.list_recent_for_student(
            student_id=str(student_id),
            limit=limit or self.default_limit,
        )
        return [
            LearnerSocraticSessionHistoryEntry(
                session_id=session.session_id,
                learning_session_id=session.learning_session_id,
                target_kc_ids=list(session.target_kc_ids),
                target_lo_ids=list(session.target_lo_ids),
                status=session.summary.status,
                turn_count=session.summary.turn_count,
                latest_prompt_style=session.summary.latest_prompt_style,
                latest_steering_action=session.summary.latest_steering_action,
                latest_next_action=session.summary.latest_next_action,
                latest_evidence_strength=session.summary.latest_evidence_strength,
                rationale=session.summary.rationale,
                next_step=session.summary.next_step.model_copy(),
                continue_action=session.summary.continue_action.model_copy(),
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            for session in sessions
        ]

    def list_remediation_session_history(
        self,
        *,
        student_id: UUID,
        limit: int | None = None,
    ) -> list[LearnerRemediationSessionHistoryEntry]:
        sessions = self.remediation_session_store.list_recent_for_student(
            student_id=str(student_id),
            limit=limit or self.default_limit,
        )
        return [
            LearnerRemediationSessionHistoryEntry(
                session_id=session.session_id,
                target_kc_id=session.target_kc_id,
                focus_kc_ids=list(session.focus_kc_ids),
                prerequisite_kc_ids=list(session.prerequisite_kc_ids),
                latest_generation_id=(
                    str(session.completed_generation_ids[-1]) if session.completed_generation_ids else None
                ),
                status=session.summary.status,
                current_phase=session.summary.current_phase,
                completed_step_count=session.summary.completed_step_count,
                step_count=session.summary.step_count,
                progression_decision=session.summary.progression_decision,
                progression_rationale=session.summary.progression_rationale,
                next_step=session.summary.next_step.model_copy(),
                continue_action=session.summary.continue_action.model_copy(),
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            for session in sessions
        ]

    @staticmethod
    def _maybe_str(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]
