from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

from dibble.models.generation import ContentIntent, GenerationRequest, RequestedContentType
from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep, LearnerStrategySummary
from dibble.models.remediation import RemediationWorkflowSession, RemediationWorkflowStep, RemediationWorkflowSummary
from dibble.services.protocols import RemediationSessionStore
from dibble.services.remediation_planner import RemediationPlan


class RemediationWorkflowNotFoundError(LookupError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Remediation workflow session not found: {session_id}.")
        self.session_id = session_id


class RemediationWorkflowCompleteError(LookupError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Remediation workflow session is already complete: {session_id}.")
        self.session_id = session_id


@dataclass(slots=True)
class RemediationWorkflowCoordinator:
    session_store: RemediationSessionStore

    def start_session(
        self,
        *,
        student_id: UUID,
        target_kc_id: str,
        misconception_description: str,
        curriculum_context: list[str],
        plan: RemediationPlan,
        strategy_summary: LearnerStrategySummary | None = None,
    ) -> RemediationWorkflowSession:
        steps = self._build_steps(plan)
        if steps:
            steps[0] = steps[0].model_copy(update={"status": "active"})
        session = RemediationWorkflowSession(
            session_id=str(uuid4()),
            student_id=student_id,
            target_kc_id=target_kc_id,
            focus_kc_ids=plan.focus_kc_ids,
            prerequisite_kc_ids=plan.prerequisite_kc_ids,
            misconception_description=misconception_description,
            curriculum_context=curriculum_context,
            rationale=plan.rationale,
            blueprint=plan.module_blueprint,
            strategy_summary=strategy_summary or LearnerStrategySummary(),
            kc_sequence=plan.kc_sequence,
            steps=steps,
            current_step_index=0 if steps else None,
        )
        return self.session_store.upsert(self._with_summary(session))

    def get(self, session_id: str) -> RemediationWorkflowSession | None:
        return self.session_store.get(session_id)

    def generation_request_for_current_step(
        self,
        *,
        session_id: str,
        learner_prompt: str | None = None,
        curriculum_context: list[str] | None = None,
    ) -> tuple[RemediationWorkflowSession, RemediationWorkflowStep, GenerationRequest]:
        session = self.session_store.get(session_id)
        if session is None:
            raise RemediationWorkflowNotFoundError(session_id)
        if session.current_step_index is None:
            raise RemediationWorkflowCompleteError(session_id)
        return self.generation_request_for_step(
            session_id=session_id,
            step_index=session.current_step_index,
            learner_prompt=learner_prompt,
            curriculum_context=curriculum_context,
        )

    def generation_request_for_step(
        self,
        *,
        session_id: str,
        step_index: int,
        learner_prompt: str | None = None,
        curriculum_context: list[str] | None = None,
    ) -> tuple[RemediationWorkflowSession, RemediationWorkflowStep, GenerationRequest]:
        session = self.session_store.get(session_id)
        if session is None:
            raise RemediationWorkflowNotFoundError(session_id)
        current_step = self._step_at(session, step_index)
        if current_step is None:
            raise RemediationWorkflowCompleteError(session_id)
        request = GenerationRequest(
            student_id=session.student_id,
            learning_session_id=session.session_id,
            target_kc_ids=current_step.target_kc_ids,
            intent=self._intent_for(current_step.recommended_content_type),
            requested_content_type=current_step.recommended_content_type,
            learner_prompt=self._learner_prompt(
                learner_prompt=learner_prompt,
                objective=current_step.objective,
                guidance=current_step.guidance,
            ),
            curriculum_context=[
                session.misconception_description,
                current_step.objective,
                current_step.guidance,
                *self._strategy_curriculum_context(session.strategy_summary),
                *self._sequencing_curriculum_context(session.kc_sequence),
                *session.curriculum_context,
                *(curriculum_context or []),
            ],
        )
        return session, current_step, request

    def complete_current_step(
        self,
        *,
        session_id: str,
        generation_id: str,
    ) -> RemediationWorkflowSession:
        session = self.session_store.get(session_id)
        if session is None:
            raise RemediationWorkflowNotFoundError(session_id)
        current_index = session.current_step_index
        if current_index is None or current_index >= len(session.steps):
            raise RemediationWorkflowCompleteError(session_id)
        steps = list(session.steps)
        current_step = steps[current_index]
        steps[current_index] = current_step.model_copy(
            update={"status": "completed", "generated_content_id": generation_id}
        )
        next_index = current_index + 1
        if next_index < len(steps):
            steps[next_index] = steps[next_index].model_copy(update={"status": "active"})
            updated_index: int | None = next_index
        else:
            updated_index = None
        updated_session = session.model_copy(
            update={
                "steps": steps,
                "current_step_index": updated_index,
                "completed_generation_ids": [*session.completed_generation_ids, generation_id],
                "progression_decision": "advance",
                "progression_rationale": None,
                "progression_target_kc_ids": [],
                "progression_evidence_observation_count": 0,
                "progression_evidence_confidence": 0.0,
                "progression_average_observed_mastery": None,
                "progression_low_support_success_count": 0,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return self.session_store.upsert(self._with_summary(updated_session))

    def update_progression_decision(
        self,
        *,
        session_id: str,
        decision: str,
        rationale: str | None,
        target_kc_ids: list[str],
        generation_id: str | None = None,
        step_index: int | None = None,
        evidence_observation_count: int = 0,
        evidence_confidence: float = 0.0,
        average_observed_mastery: float | None = None,
        low_support_success_count: int = 0,
    ) -> RemediationWorkflowSession:
        session = self.session_store.get(session_id)
        if session is None:
            raise RemediationWorkflowNotFoundError(session_id)
        steps = list(session.steps)
        if generation_id is not None and step_index is not None and 0 <= step_index < len(steps):
            steps[step_index] = steps[step_index].model_copy(update={"generated_content_id": generation_id})
        updated_session = session.model_copy(
            update={
                "steps": steps,
                "progression_decision": decision,
                "progression_rationale": rationale,
                "progression_target_kc_ids": target_kc_ids,
                "progression_evidence_observation_count": evidence_observation_count,
                "progression_evidence_confidence": evidence_confidence,
                "progression_average_observed_mastery": average_observed_mastery,
                "progression_low_support_success_count": low_support_success_count,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return self.session_store.upsert(self._with_summary(updated_session))

    def _build_steps(self, plan: RemediationPlan) -> list[RemediationWorkflowStep]:
        steps: list[RemediationWorkflowStep] = []
        for raw_step in plan.module_blueprint.get("steps", []):
            if not isinstance(raw_step, dict):
                continue
            phase = str(raw_step.get("phase", "repair"))
            steps.append(
                RemediationWorkflowStep(
                    phase=phase,
                    title=str(raw_step.get("title", phase.replace("_", " ").title())),
                    target_kc_ids=[str(item) for item in raw_step.get("target_kc_ids", []) if item is not None],
                    support_level=str(raw_step.get("support_level", "medium")),
                    objective=str(raw_step.get("objective", "")),
                    guidance=str(raw_step.get("guidance", "")),
                    misconception_ids=[str(item) for item in raw_step.get("misconception_ids", []) if item is not None],
                    recommended_content_type=self._content_type_for_phase(phase),
                )
            )
        return steps

    def _current_step(self, session: RemediationWorkflowSession) -> RemediationWorkflowStep | None:
        if session.current_step_index is None:
            return None
        return self._step_at(session, session.current_step_index)

    def _step_at(self, session: RemediationWorkflowSession, step_index: int) -> RemediationWorkflowStep | None:
        if step_index < 0 or step_index >= len(session.steps):
            return None
        return session.steps[step_index]

    def _content_type_for_phase(self, phase: str) -> RequestedContentType:
        if phase == "return":
            return RequestedContentType.practice_problem
        return RequestedContentType.remedial_micro_module

    def _with_summary(self, session: RemediationWorkflowSession) -> RemediationWorkflowSession:
        return session.model_copy(update={"summary": self._summary_for(session)})

    def _summary_for(self, session: RemediationWorkflowSession) -> RemediationWorkflowSummary:
        current_step = self._current_step(session)
        next_step = self._next_step_for_summary(session=session, current_step=current_step)
        status = "complete" if session.current_step_index is None else "in_progress"
        if session.progression_decision.startswith("hold_"):
            status = "held"
        return RemediationWorkflowSummary(
            status=status,
            current_phase=current_step.phase if current_step is not None else None,
            current_step_title=current_step.title if current_step is not None else None,
            current_step_target_kc_ids=list(current_step.target_kc_ids) if current_step is not None else [],
            next_phase=next_step.action if next_step.action not in {"complete", "advance"} else None,
            completed_step_count=len(session.completed_generation_ids),
            step_count=len(session.steps),
            progression_decision=session.progression_decision,
            progression_rationale=session.progression_rationale,
            progression_target_kc_ids=list(session.progression_target_kc_ids),
            progression_evidence_observation_count=session.progression_evidence_observation_count,
            progression_evidence_confidence=session.progression_evidence_confidence,
            progression_average_observed_mastery=session.progression_average_observed_mastery,
            progression_low_support_success_count=session.progression_low_support_success_count,
            next_step=next_step,
            continue_action=self._continue_action_for_summary(
                session=session,
                status=status,
                next_step=next_step,
            ),
        )

    def _next_step_for_summary(
        self,
        *,
        session: RemediationWorkflowSession,
        current_step: RemediationWorkflowStep | None,
    ):
        if session.progression_decision.startswith("hold_"):
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
        if current_step is None:
            return LearnerFlowNextStep(
                action="complete",
                content_type=None,
                target_stage="transfer",
                target_kc_ids=list(session.kc_sequence.deferred_kc_ids or session.focus_kc_ids),
                rationale="The remediation workflow is complete.",
            )
        target_stage = "transfer" if current_step.phase == "return" else "bridge" if current_step.phase == "bridge" else "repair"
        return LearnerFlowNextStep(
            action=current_step.phase,
            content_type=current_step.recommended_content_type.value,
            target_stage=target_stage,
            target_kc_ids=list(current_step.target_kc_ids),
            rationale=session.progression_rationale or current_step.guidance or session.rationale,
        )

    def _continue_action_for_summary(
        self,
        *,
        session: RemediationWorkflowSession,
        status: str,
        next_step: LearnerFlowNextStep,
    ) -> LearnerContinueAction:
        if status == "complete":
            target_kc_ids = list(session.kc_sequence.deferred_kc_ids or session.focus_kc_ids)
            return LearnerContinueAction.generate_follow_up(
                resource_id=session.session_id,
                content_type=RequestedContentType.practice_problem.value,
                target_stage="transfer",
                target_kc_ids=target_kc_ids,
                request_payload={
                    "student_id": str(session.student_id),
                    "target_kc_ids": target_kc_ids,
                    "curriculum_context": list(session.curriculum_context),
                    "requested_content_type": RequestedContentType.practice_problem.value,
                },
                rationale=next_step.rationale,
            )
        return LearnerContinueAction.advance_remediation(
            endpoint=f"/api/remedial/sessions/{session.session_id}/advance",
            resource_id=session.session_id,
            content_type=next_step.content_type,
            target_stage=next_step.target_stage,
            target_kc_ids=list(next_step.target_kc_ids),
            request_payload={
                "curriculum_context": list(session.curriculum_context),
            },
            rationale=next_step.rationale,
        )

    def _intent_for(self, content_type: RequestedContentType) -> ContentIntent:
        if content_type == RequestedContentType.practice_problem:
            return ContentIntent.practice
        if content_type == RequestedContentType.assessment_probe:
            return ContentIntent.assessment
        return ContentIntent.remediation

    def _learner_prompt(
        self,
        *,
        learner_prompt: str | None,
        objective: str,
        guidance: str,
    ) -> str:
        workflow_prompt = guidance.strip() or objective.strip()
        if learner_prompt:
            return f"{learner_prompt} {workflow_prompt}".strip()
        return workflow_prompt

    def _strategy_curriculum_context(self, strategy_summary: LearnerStrategySummary) -> list[str]:
        if strategy_summary.signal == "insufficient":
            return []
        context = [f"Learner strategy: {strategy_summary.signal} ({strategy_summary.recovery_focus})."]
        if strategy_summary.rationale is not None:
            context.append(strategy_summary.rationale)
        if strategy_summary.recovery_focus == "prerequisite_rebuild":
            context.append("Rebuild prerequisite understanding before asking for transfer back to the target.")
        elif strategy_summary.recovery_focus == "targeted_repair":
            context.append("Keep support explicit and verify each repair step before fading support.")
        elif strategy_summary.recovery_focus == "independent_practice":
            context.append("Fade support sooner and end with an independent check on the target skill.")
        elif strategy_summary.recovery_focus == "guided_practice":
            context.append("Keep guidance present, but start fading support once the learner is stable.")
        return context

    def _sequencing_curriculum_context(self, kc_sequence) -> list[str]:
        if kc_sequence.action == "monitor":
            return []
        context = [f"KC sequencing: {kc_sequence.action}."]
        if kc_sequence.primary_kc_id is not None:
            context.append(f"Stay centered on {kc_sequence.primary_kc_id} before moving on.")
        if kc_sequence.bridge_kc_ids:
            context.append(
                "Bridge through nearby KC(s) "
                + ", ".join(kc_sequence.bridge_kc_ids)
                + " before the final target return."
            )
        if kc_sequence.rationale is not None:
            context.append(kc_sequence.rationale)
        return context
