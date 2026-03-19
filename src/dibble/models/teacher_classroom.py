from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from dibble.models.profile import (
    ContinueActionKind,
    LearnerCurriculumProgressionSummary,
    LearnerFlowSummary,
    RecentLearnerActivity,
)
from dibble.models.teacher_actions import (
    TeacherInterventionDecisionStatus,
    TeacherInterventionProposalStatus,
)


class TeacherLearnerInterventionSummary(BaseModel):
    action_key: str = "idle"
    proposal_status: TeacherInterventionProposalStatus = (
        TeacherInterventionProposalStatus.unavailable
    )
    recommended_action_kind: ContinueActionKind = ContinueActionKind.idle
    option_count: int = Field(default=0, ge=0)
    latest_decision_status: TeacherInterventionDecisionStatus | None = None


class TeacherLearnerCard(BaseModel):
    student_id: str
    grade_level: str
    engagement: str
    frustration: str
    current_flow: LearnerFlowSummary
    curriculum_progression: LearnerCurriculumProgressionSummary
    recent_activity: RecentLearnerActivity
    intervention: TeacherLearnerInterventionSummary = Field(
        default_factory=TeacherLearnerInterventionSummary
    )
    display_rationale: str | None = None
    attention_level: str = "normal"
    triage_section: str = "on_track"
    attention_reasons: list[str] = Field(default_factory=list)


class TeacherClassroomOverview(BaseModel):
    classroom_id: str
    course_id: str
    title: str
    teacher_label: str | None = None
    grade_level: str | None = None
    subject: str | None = None
    learner_count: int = Field(default=0, ge=0)
    active_flow_count: int = Field(default=0, ge=0)
    intervention_available_count: int = Field(default=0, ge=0)
    blocked_progression_count: int = Field(default=0, ge=0)
    attention_needed_count: int = Field(default=0, ge=0)
    missing_learner_count: int = Field(default=0, ge=0)
    updated_at: datetime | None = None


class TeacherClassroomReadModel(TeacherClassroomOverview):
    missing_student_ids: list[str] = Field(default_factory=list)
    learners: list[TeacherLearnerCard] = Field(default_factory=list)
