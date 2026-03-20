from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.history import (
    MAX_HISTORY_LIMIT,
    LearnerGenerationHistoryEntry,
    LearnerGenerationHistoryPage,
    LearnerRemediationSessionHistoryEntry,
    LearnerRemediationSessionHistoryPage,
    LearnerSocraticSessionHistoryEntry,
    LearnerSocraticSessionHistoryPage,
)
from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep
from dibble.services.protocols import (
    GeneratedContentStore,
    RemediationSessionStore,
    SocraticSessionStore,
)


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
        offset: int = 0,
    ) -> LearnerGenerationHistoryPage:
        safe_limit = _clamp_limit(limit if limit is not None else self.default_limit)
        safe_offset = max(0, offset)
        entries = self.generated_content_store.list_recent_for_student(
            student_id=str(student_id),
            limit=safe_limit + 1,
            offset=safe_offset,
            include_predictive_warm=False,
        )
        has_more = len(entries) > safe_limit
        items: list[LearnerGenerationHistoryEntry] = []
        for content in entries[:safe_limit]:
            workflow_summary = content.workflow_summary
            request_context = content.request_context
            mode_cal = self._mode_calibration(request_context)
            items.append(
                LearnerGenerationHistoryEntry(
                    generation_id=content.generation_id,
                    learning_session_id=self._maybe_str(
                        workflow_summary.learning_session_id
                        if workflow_summary is not None
                        else None
                    )
                    or self._maybe_str(request_context.get("learning_session_id")),
                    source_generation_id=self._maybe_str(
                        request_context.get("source_generation_id")
                    ),
                    content_type=content.content_type,
                    flow_type=workflow_summary.flow_type
                    if workflow_summary is not None
                    else "lesson",
                    status=workflow_summary.status
                    if workflow_summary is not None
                    else "delivered",
                    delivered_phase=workflow_summary.delivered_phase
                    if workflow_summary is not None
                    else "target",
                    progression_action=(
                        workflow_summary.progression_action
                        if workflow_summary is not None
                        else "stay_on_requested_target"
                    ),
                    target_stage=workflow_summary.target_stage
                    if workflow_summary is not None
                    else "target",
                    active_target_kc_ids=(
                        list(workflow_summary.active_target_kc_ids)
                        if workflow_summary is not None
                        else self._string_list(request_context.get("target_kc_ids"))
                    ),
                    intervention_type=content.response.route.intervention_type.value,
                    rationale=workflow_summary.rationale
                    if workflow_summary is not None
                    else None,
                    mastery_signal=mode_cal.get("signal", "insufficient"),
                    mastery_confidence=float(mode_cal.get("confidence", 0.0)),
                    progress_signal=mode_cal.get("progress_signal", "insufficient"),
                    evidence_signal=mode_cal.get(
                        "current_evidence_signal", "steady"
                    ),
                    evidence_rationale=self._maybe_str(
                        mode_cal.get("current_evidence_rationale")
                    ),
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
        return LearnerGenerationHistoryPage(
            items=items,
            offset=safe_offset,
            limit=safe_limit,
            has_more=has_more,
        )

    def list_socratic_session_history(
        self,
        *,
        student_id: UUID,
        limit: int | None = None,
        offset: int = 0,
    ) -> LearnerSocraticSessionHistoryPage:
        safe_limit = _clamp_limit(limit if limit is not None else self.default_limit)
        safe_offset = max(0, offset)
        sessions = self.socratic_session_store.list_recent_for_student(
            student_id=str(student_id),
            limit=safe_limit + 1,
            offset=safe_offset,
        )
        has_more = len(sessions) > safe_limit
        items = [
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
            for session in sessions[:safe_limit]
        ]
        return LearnerSocraticSessionHistoryPage(
            items=items,
            offset=safe_offset,
            limit=safe_limit,
            has_more=has_more,
        )

    def list_remediation_session_history(
        self,
        *,
        student_id: UUID,
        limit: int | None = None,
        offset: int = 0,
    ) -> LearnerRemediationSessionHistoryPage:
        safe_limit = _clamp_limit(limit if limit is not None else self.default_limit)
        safe_offset = max(0, offset)
        sessions = self.remediation_session_store.list_recent_for_student(
            student_id=str(student_id),
            limit=safe_limit + 1,
            offset=safe_offset,
        )
        has_more = len(sessions) > safe_limit
        items = [
            LearnerRemediationSessionHistoryEntry(
                session_id=session.session_id,
                target_kc_id=session.target_kc_id,
                focus_kc_ids=list(session.focus_kc_ids),
                prerequisite_kc_ids=list(session.prerequisite_kc_ids),
                latest_generation_id=self._latest_remediation_generation_id(session),
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
            for session in sessions[:safe_limit]
        ]
        return LearnerRemediationSessionHistoryPage(
            items=items,
            offset=safe_offset,
            limit=safe_limit,
            has_more=has_more,
        )

    @staticmethod
    def _mode_calibration(request_context: dict[str, object]) -> dict[str, object]:
        raw = request_context.get("mode_calibration", {})
        if isinstance(raw, dict):
            return raw
        return {}

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

    @staticmethod
    def _latest_remediation_generation_id(session) -> str | None:
        for step in reversed(session.steps):
            if step.generated_content_id:
                return str(step.generated_content_id)
        if session.completed_generation_ids:
            return str(session.completed_generation_ids[-1])
        return None


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, MAX_HISTORY_LIMIT))
