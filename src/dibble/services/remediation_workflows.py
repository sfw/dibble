from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

from dibble.models.generation import ContentIntent, GenerationRequest, RequestedContentType
from dibble.models.profile import LearnerStrategySummary
from dibble.models.remediation import RemediationWorkflowSession, RemediationWorkflowStep
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
        return self.session_store.upsert(session)

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
        current_step = self._current_step(session)
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
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return self.session_store.upsert(updated_session)

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
        if session.current_step_index >= len(session.steps):
            return None
        return session.steps[session.current_step_index]

    def _content_type_for_phase(self, phase: str) -> RequestedContentType:
        if phase == "return":
            return RequestedContentType.practice_problem
        return RequestedContentType.remedial_micro_module

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
