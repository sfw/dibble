from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.contract_labels import triage_section_for
from dibble.models.classroom import Classroom
from dibble.models.teacher_actions import TeacherInterventionProposalStatus
from dibble.models.teacher_classroom import (
    TeacherClassroomOverview,
    TeacherClassroomReadModel,
    TeacherLearnerCard,
    TeacherLearnerInterventionSummary,
)
from dibble.services.learner_summary_service import LearnerSummaryService
from dibble.services.teacher_intervention_actions import (
    TeacherInterventionActionService,
)


@dataclass(slots=True)
class TeacherClassroomService:
    learner_summary_service: LearnerSummaryService
    teacher_intervention_action_service: TeacherInterventionActionService

    def build_classroom(self, classroom: Classroom) -> TeacherClassroomReadModel:
        learners: list[TeacherLearnerCard] = []
        missing_student_ids: list[str] = []
        for student_id in classroom.student_ids:
            try:
                parsed_student_id = UUID(student_id)
            except ValueError:
                missing_student_ids.append(student_id)
                continue
            summary = self.learner_summary_service.build_for_student(
                student_id=parsed_student_id
            )
            if summary is None:
                missing_student_ids.append(student_id)
                continue
            intervention = self.teacher_intervention_action_service.build_for_student(
                student_id=parsed_student_id
            )
            attention_reasons = self._attention_reasons(
                summary=summary, intervention=intervention
            )
            attention_level = self._attention_level(attention_reasons)
            display_rationale = self._display_rationale(
                summary=summary, intervention=intervention
            )
            learners.append(
                TeacherLearnerCard(
                    student_id=str(summary.student_id),
                    grade_level=summary.grade_level,
                    engagement=summary.engagement.value,
                    frustration=summary.frustration.value,
                    current_flow=summary.current_flow,
                    curriculum_progression=summary.curriculum_progression,
                    recent_activity=summary.recent_activity,
                    intervention=TeacherLearnerInterventionSummary(
                        action_key=intervention.action_key,
                        proposal_status=intervention.proposal_status,
                        recommended_action_kind=intervention.proposed_action.kind,
                        option_count=len(intervention.available_options),
                        latest_decision_status=(
                            intervention.latest_decision.status
                            if intervention.latest_decision is not None
                            else None
                        ),
                    ),
                    display_rationale=display_rationale,
                    attention_level=attention_level,
                    triage_section=triage_section_for(
                        attention_level=attention_level,
                        proposal_status=intervention.proposal_status.value,
                    ),
                    attention_reasons=attention_reasons,
                )
            )

        learners.sort(
            key=lambda learner: (
                0
                if learner.attention_level == "high"
                else 1
                if learner.attention_level == "medium"
                else 2,
                learner.student_id,
            )
        )

        return TeacherClassroomReadModel(
            **self._overview_payload(
                classroom=classroom,
                learners=learners,
                missing_student_ids=missing_student_ids,
            ),
            missing_student_ids=missing_student_ids,
            learners=learners,
        )

    def list_classrooms(
        self, classrooms: list[Classroom]
    ) -> list[TeacherClassroomOverview]:
        overviews: list[TeacherClassroomOverview] = []
        for classroom in classrooms:
            read_model = self.build_classroom(classroom)
            overviews.append(
                TeacherClassroomOverview(
                    **self._overview_payload(
                        classroom=classroom,
                        learners=read_model.learners,
                        missing_student_ids=read_model.missing_student_ids,
                    )
                )
            )
        return overviews

    def _overview_payload(
        self,
        *,
        classroom: Classroom,
        learners: list[TeacherLearnerCard],
        missing_student_ids: list[str],
    ) -> dict[str, object]:
        active_flow_count = sum(
            1 for learner in learners if learner.current_flow.status != "idle"
        )
        intervention_available_count = sum(
            1
            for learner in learners
            if learner.intervention.proposal_status
            == TeacherInterventionProposalStatus.available
        )
        blocked_progression_count = sum(
            1
            for learner in learners
            if learner.curriculum_progression.status == "blocked_on_prerequisites"
        )
        attention_needed_count = sum(
            1 for learner in learners if learner.attention_level != "normal"
        )
        return {
            "classroom_id": classroom.classroom_id,
            "title": classroom.title,
            "teacher_label": classroom.teacher_label,
            "grade_level": classroom.grade_level,
            "subject": classroom.subject,
            "learner_count": len(learners),
            "active_flow_count": active_flow_count,
            "intervention_available_count": intervention_available_count,
            "blocked_progression_count": blocked_progression_count,
            "attention_needed_count": attention_needed_count,
            "missing_learner_count": len(missing_student_ids),
            "updated_at": classroom.updated_at,
        }

    @staticmethod
    def _display_rationale(*, summary, intervention) -> str | None:
        latest_decision_status = (
            intervention.latest_decision.status
            if intervention.latest_decision is not None
            else None
        )
        if latest_decision_status is not None:
            label = (
                latest_decision_status.value.replace("_", " ")
                .replace("-", " ")
                .title()
            )
            return f"Latest teacher decision: {label}."
        if summary.curriculum_progression.rationale is not None:
            return summary.curriculum_progression.rationale
        if summary.current_flow.next_step.rationale is not None:
            return summary.current_flow.next_step.rationale
        if summary.current_flow.rationale is not None:
            return summary.current_flow.rationale
        return None

    def _attention_reasons(self, *, summary, intervention) -> list[str]:
        reasons: list[str] = []
        if summary.curriculum_progression.status == "blocked_on_prerequisites":
            reasons.append("blocked_on_prerequisites")
        if intervention.proposal_status == TeacherInterventionProposalStatus.available:
            reasons.append("teacher_intervention_available")
        if summary.current_flow.flow_type == "remediation":
            reasons.append("active_remediation")
        if summary.frustration.value == "high":
            reasons.append("high_frustration")
        return reasons

    @staticmethod
    def _attention_level(reasons: list[str]) -> str:
        if not reasons:
            return "normal"
        if "high_frustration" in reasons or "active_remediation" in reasons:
            return "high"
        return "medium"
