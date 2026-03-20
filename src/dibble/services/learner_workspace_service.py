from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from dibble.contract_labels import affective_support_message
from dibble.models.generation import ContentIntent, GenerationRequest
from dibble.models.profile import ContinueActionKind, LearnerContinueAction
from dibble.models.workspace import (
    AffectiveSupportMessage,
    LearnerWorkspace,
    LearnerWorkspaceArtifact,
)
from dibble.services.content_workflow import ContentWorkflowService
from dibble.services.learner_summary_service import LearnerSummaryService
from dibble.services.socratic_assessment import SocraticAssessmentService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LearnerWorkspaceService:
    learner_summary_service: LearnerSummaryService
    content_workflow_service: ContentWorkflowService
    socratic_assessment_service: SocraticAssessmentService

    def build_for_student(self, *, student_id: UUID) -> LearnerWorkspace | None:
        summary = self.learner_summary_service.build_for_student(student_id=student_id)
        if summary is None:
            return None

        flow = summary.current_flow
        generated_content = None
        remediation_session = None
        socratic_session = None
        artifact = LearnerWorkspaceArtifact(
            learning_session_id=flow.learning_session_id,
            flow_type=flow.flow_type,
            status=flow.status,
            current_phase=flow.current_phase,
            content_type=flow.current_content_type,
            rationale=flow.rationale,
        )

        if flow.remediation_session_id is not None:
            remediation_session = self.content_workflow_service.get_remediation_session(
                flow.remediation_session_id
            )
            generation_id = self._latest_remediation_generation_id(remediation_session)
            generated_content = (
                self.content_workflow_service.get_generated_content(generation_id)
                if generation_id is not None
                else None
            )
            artifact = artifact.model_copy(
                update={
                    "kind": "remediation_session",
                    "resource_id": flow.remediation_session_id,
                    "generation_id": generation_id,
                    "content_type": (
                        generated_content.content_type
                        if generated_content is not None
                        else flow.current_content_type
                    ),
                }
            )
        elif flow.socratic_session_id is not None:
            socratic_session = self.socratic_assessment_service.get_session(
                flow.socratic_session_id
            )
            artifact = artifact.model_copy(
                update={
                    "kind": "socratic_session",
                    "resource_id": flow.socratic_session_id,
                }
            )
        else:
            generation_id = (
                flow.last_generation_id or summary.recent_activity.last_generation_id
            )
            generated_content = (
                self.content_workflow_service.get_generated_content(generation_id)
                if generation_id is not None
                else None
            )
            artifact = artifact.model_copy(
                update={
                    "kind": "generated_content"
                    if generated_content is not None
                    else "idle",
                    "resource_id": generation_id
                    if generated_content is not None
                    else None,
                    "generation_id": generation_id
                    if generated_content is not None
                    else None,
                    "content_type": (
                        generated_content.content_type
                        if generated_content is not None
                        else flow.current_content_type
                    ),
                }
            )

        continue_action = flow.continue_action
        # When the flow is idle but the progression has ready outcomes,
        # eagerly generate content for the first ready outcome so the
        # learner has a lesson waiting when they click Resume.
        if (
            continue_action.kind == ContinueActionKind.idle
            and summary.curriculum_progression.next_outcome is not None
        ):
            next_outcome = summary.curriculum_progression.next_outcome
            target_kc_ids = list(next_outcome.knowledge_component_ids)

            if generated_content is None:
                generated_content = self._eager_generate(
                    student_id=student_id,
                    target_kc_ids=target_kc_ids,
                )

            continue_action = LearnerContinueAction.generate_follow_up(
                outcome_id=next_outcome.outcome_id,
                generation_id=(
                    generated_content.generation_id
                    if generated_content is not None
                    else None
                ),
                target_stage="target",
                target_kc_ids=target_kc_ids,
                request_payload={
                    "student_id": str(student_id),
                    "target_kc_ids": target_kc_ids,
                    "intent": "explanation",
                },
                rationale=(
                    f"Ready to start {next_outcome.title}."
                ),
            )

            if generated_content is not None:
                artifact = artifact.model_copy(
                    update={
                        "kind": "generated_content",
                        "resource_id": generated_content.generation_id,
                        "generation_id": generated_content.generation_id,
                        "content_type": generated_content.content_type,
                    }
                )

        return LearnerWorkspace(
            student_id=student_id,
            summary=summary,
            active_artifact=artifact,
            continue_action=continue_action,
            affective_support=(
                AffectiveSupportMessage.model_validate(message)
                if (
                    message := affective_support_message(
                        frustration=summary.frustration.value,
                        engagement=summary.engagement.value,
                    )
                )
                is not None
                else None
            ),
            generated_content=generated_content,
            remediation_session=remediation_session,
            socratic_session=socratic_session,
        )

    def _eager_generate(
        self,
        *,
        student_id: UUID,
        target_kc_ids: list[str],
    ):
        """Generate the first lesson eagerly so learners never see an empty page."""
        try:
            request = GenerationRequest(
                student_id=student_id,
                target_kc_ids=target_kc_ids,
                intent=ContentIntent.explanation,
            )
            return self.content_workflow_service.generate_content(request)
        except Exception:
            logger.exception(
                "Eager content generation failed for student %s", student_id
            )
            return None

    def _latest_remediation_generation_id(self, remediation_session) -> str | None:
        if remediation_session is None:
            return None
        for step in reversed(remediation_session.steps):
            if step.generated_content_id:
                return str(step.generated_content_id)
        if remediation_session.completed_generation_ids:
            return str(remediation_session.completed_generation_ids[-1])
        return None
