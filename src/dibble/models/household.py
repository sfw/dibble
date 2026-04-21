from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ParentPreference(BaseModel):
    session_cadence: str = "daily"
    auto_session_suggestions: bool = True
    weekly_summary_day: str = "sunday"
    soft_escalation_enabled: bool = True
    approval_mode: str = "guided"
    modality_introduction_requires_approval: bool = True
    trajectory_revision_requires_approval: bool = True
    high_autonomy_session_requires_approval: bool = True


class ParentProfile(BaseModel):
    parent_user_id: str
    display_name: str | None = None
    relationship_label: str = "parent"
    preferences: ParentPreference = Field(default_factory=ParentPreference)


class Household(BaseModel):
    household_id: str
    household_name: str
    parent_profiles: list[ParentProfile] = Field(default_factory=list)
    learner_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ParentApprovalType(str, Enum):
    modality_introduction = "modality_introduction"
    trajectory_revision = "trajectory_revision"
    high_autonomy_session = "high_autonomy_session"


class ParentApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class ParentApprovalRequest(BaseModel):
    approval_id: str
    learner_id: str
    approval_type: ParentApprovalType
    status: ParentApprovalStatus = ParentApprovalStatus.pending
    title: str
    message: str
    proposed_value: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    decided_at: datetime | None = None


class LearnerRelationshipState(BaseModel):
    household_id: str
    learner_id: str
    engagement_status: str = "steady"
    frustration_status: str = "low"
    cadence_status: str = "on_track"
    soft_escalation_active: bool = False
    consecutive_stall_checks: int = 0
    last_session_at: datetime | None = None
    last_weekly_summary_at: datetime | None = None
    current_goal_title: str | None = None
    next_session_focus: str | None = None
    suggested_modality: str | None = None
    summary_headline: str | None = None
    latest_weekly_summary: AutonomousTeacherWeeklySummary | None = None
    session_suggestion_status: str = "pending"
    session_suggestion_snoozed_until: datetime | None = None
    session_suggestion_updated_at: datetime | None = None
    approved_modalities: list[str] = Field(default_factory=lambda: ["text"])
    active_trajectory_signature: str | None = None
    approval_requests: list[ParentApprovalRequest] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class ParentNotification(BaseModel):
    notification_id: str
    household_id: str
    learner_id: str | None = None
    dedupe_key: str
    category: str
    severity: str = "info"
    title: str
    message: str
    status: str = "unread"
    snoozed_until: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, object] = Field(default_factory=dict)


class AutonomousTeacherWeeklySummary(BaseModel):
    learner_id: str
    headline: str
    celebration: str
    support_need: str | None = None
    next_focus: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)


class AutonomousTeacherSessionSuggestion(BaseModel):
    learner_id: str
    cadence_decision: str
    status: str = "pending"
    snoozed_until: datetime | None = None
    suggested_for: datetime | None = None
    focus_label: str | None = None
    rationale: str | None = None
    learning_session_id: str | None = None
    continue_action_endpoint: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    modality: str = "text"


class AutonomousTeacherLearnerPlan(BaseModel):
    learner_id: str
    learner_label: str
    grade_level: str
    goal_title: str | None = None
    mastery_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    cadence_decision: str
    next_session: AutonomousTeacherSessionSuggestion | None = None
    weekly_summary: AutonomousTeacherWeeklySummary | None = None
    relationship_state: LearnerRelationshipState
    notifications: list[ParentNotification] = Field(default_factory=list)


class HouseholdSetupRequest(BaseModel):
    household_name: str
    learner_ids: list[str] = Field(default_factory=list)
    relationship_label: str = "parent"
    preferences: ParentPreference = Field(default_factory=ParentPreference)


class HouseholdSetupResponse(BaseModel):
    household: Household


class HouseholdPreferenceUpdateRequest(BaseModel):
    relationship_label: str | None = None
    preferences: ParentPreference


class HouseholdNotificationSnoozeRequest(BaseModel):
    hours: int = Field(default=24, ge=1, le=24 * 14)


class HouseholdSessionSuggestionSnoozeRequest(BaseModel):
    hours: int = Field(default=24, ge=1, le=24 * 14)


class HouseholdLearnerOverview(BaseModel):
    learner_id: str
    learner_label: str
    grade_level: str
    goal_title: str | None = None
    mastery_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement: str
    frustration: str
    current_stage: str
    next_session_focus: str | None = None
    suggested_modality: str = "text"
    cadence_decision: str = "watch"
    soft_escalation_active: bool = False
    summary_headline: str | None = None
    pending_approval_count: int = 0


class HouseholdOverview(BaseModel):
    household: Household | None = None
    learners: list[HouseholdLearnerOverview] = Field(default_factory=list)
    session_suggestions: list[AutonomousTeacherSessionSuggestion] = Field(
        default_factory=list
    )
    pending_approvals: list[ParentApprovalRequest] = Field(default_factory=list)
    weekly_summaries: list[AutonomousTeacherWeeklySummary] = Field(default_factory=list)
    notifications: list[ParentNotification] = Field(default_factory=list)
    available_learners: list[dict[str, str | None]] = Field(default_factory=list)
