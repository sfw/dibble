from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from dibble.models.household import (
    AutonomousTeacherLearnerPlan,
    AutonomousTeacherSessionSuggestion,
    AutonomousTeacherWeeklySummary,
    Household,
    LearnerRelationshipState,
    ParentPreference,
    ParentNotification,
)
from dibble.services.harness.curriculum_planning import (
    CurriculumPlanningHarness,
    EnsureActiveTrajectoryCommand,
)
from dibble.services.harness.within_session_control import (
    EnsureSessionControlCommand,
    WithinSessionControlHarness,
)
from dibble.services.learner_summary_service import LearnerSummaryService
from dibble.services.protocols import (
    LearnerRelationshipStateStore,
    ParentNotificationStore,
    UserStore,
)


@dataclass(frozen=True, slots=True)
class AutonomousTeacherHouseholdResult:
    learner_plans: list[AutonomousTeacherLearnerPlan]
    notifications: list[ParentNotification]


@dataclass(slots=True)
class AutonomousTeacherHarness:
    learner_summary_service: LearnerSummaryService
    curriculum_planning_harness: CurriculumPlanningHarness
    within_session_control_harness: WithinSessionControlHarness
    learner_relationship_state_store: LearnerRelationshipStateStore
    parent_notification_store: ParentNotificationStore
    user_store: UserStore

    def orchestrate_household(
        self,
        *,
        household: Household,
        now: datetime | None = None,
    ) -> AutonomousTeacherHouseholdResult:
        reference_time = now or datetime.now(timezone.utc)
        learner_plans: list[AutonomousTeacherLearnerPlan] = []
        notifications: list[ParentNotification] = []
        for learner_id in household.learner_ids:
            plan = self._plan_for_learner(
                household=household,
                learner_id=learner_id,
                now=reference_time,
            )
            if plan is None:
                continue
            learner_plans.append(plan)
            notifications.extend(plan.notifications)
        return AutonomousTeacherHouseholdResult(
            learner_plans=learner_plans,
            notifications=sorted(
                notifications,
                key=lambda item: item.updated_at,
                reverse=True,
            ),
        )

    def _plan_for_learner(
        self,
        *,
        household: Household,
        learner_id: str,
        now: datetime,
    ) -> AutonomousTeacherLearnerPlan | None:
        student_id = UUID(learner_id)
        summary = self.learner_summary_service.build_for_student(student_id=student_id)
        if summary is None:
            return None
        planning = self.curriculum_planning_harness.ensure_active_trajectory(
            EnsureActiveTrajectoryCommand(student_id=student_id)
        )
        session = self.within_session_control_harness.ensure_session(
            EnsureSessionControlCommand(student_id=student_id)
        )
        existing_state = self.learner_relationship_state_store.get(
            household_id=household.household_id,
            learner_id=learner_id,
        )
        preferences = self._primary_preferences(household=household)
        cadence_decision = self._cadence_decision(
            last_event_at=summary.recent_activity.last_event_at,
            session_stuck_loop_risk=summary.current_flow.session_stuck_loop_risk,
            frustration=summary.frustration.value,
            now=now,
        )
        consecutive_stall_checks = self._stall_count(
            existing_state=existing_state,
            session_stuck_loop_risk=summary.current_flow.session_stuck_loop_risk,
            frustration=summary.frustration.value,
            progress_signal=summary.progress.signal,
            last_event_at=summary.recent_activity.last_event_at,
        )
        next_focus = (
            planning.trajectory.nodes[0].title
            if planning.trajectory is not None and planning.trajectory.nodes
            else planning.goal.title if planning.goal is not None else None
        )
        suggested_modality = self._suggested_modality(
            content_type=(
                session.next_step.content_type
                if session is not None
                else summary.current_flow.next_step.content_type
            )
        )
        relationship_state = LearnerRelationshipState(
            household_id=household.household_id,
            learner_id=learner_id,
            engagement_status=summary.engagement.value,
            frustration_status=summary.frustration.value,
            cadence_status=cadence_decision,
            soft_escalation_active=(
                preferences.soft_escalation_enabled and consecutive_stall_checks >= 2
            ),
            consecutive_stall_checks=consecutive_stall_checks,
            last_session_at=summary.recent_activity.last_event_at,
            last_weekly_summary_at=(
                existing_state.last_weekly_summary_at if existing_state is not None else None
            ),
            current_goal_title=planning.goal.title if planning.goal is not None else None,
            next_session_focus=next_focus,
            suggested_modality=suggested_modality,
            summary_headline=self._summary_headline(
                cadence_decision=cadence_decision,
                current_goal_title=planning.goal.title if planning.goal is not None else None,
            ),
            latest_weekly_summary=(
                existing_state.latest_weekly_summary if existing_state is not None else None
            ),
            session_suggestion_status="pending",
            session_suggestion_snoozed_until=None,
            session_suggestion_updated_at=(
                existing_state.session_suggestion_updated_at
                if existing_state is not None
                else None
            ),
            updated_at=now,
        )
        relationship_state = self._session_suggestion_state_for(
            relationship_state=relationship_state,
            existing_state=existing_state,
            now=now,
        )
        weekly_summary = self._maybe_build_weekly_summary(
            household=household,
            preferences=preferences,
            relationship_state=relationship_state,
            summary=summary,
            now=now,
        )
        if weekly_summary is not None:
            relationship_state = relationship_state.model_copy(
                update={
                    "last_weekly_summary_at": weekly_summary.generated_at,
                    "latest_weekly_summary": weekly_summary,
                }
            )
        self.learner_relationship_state_store.upsert(relationship_state)

        learner_notifications = self._notifications_for(
            household=household,
            preferences=preferences,
            relationship_state=relationship_state,
            weekly_summary=weekly_summary,
            now=now,
        )
        for notification in learner_notifications:
            self.parent_notification_store.upsert(notification)

        learner_user = next(
            (
                user
                for user in self.user_store.list()
                if user.learner_id == learner_id or user.user_id == learner_id
            ),
            None,
        )
        session_suggestion = self._build_session_suggestion(
            learner_id=learner_id,
            cadence_decision=cadence_decision,
            relationship_state=relationship_state,
            session=session,
            auto_session_suggestions=preferences.auto_session_suggestions,
            now=now,
        )
        return AutonomousTeacherLearnerPlan(
            learner_id=learner_id,
            learner_label=(
                learner_user.display_name
                if learner_user is not None and learner_user.display_name
                else learner_id
            ),
            grade_level=summary.grade_level,
            goal_title=planning.goal.title if planning.goal is not None else None,
            mastery_ratio=summary.curriculum_progression.mastered_outcome_ratio,
            cadence_decision=cadence_decision,
            next_session=session_suggestion,
            weekly_summary=relationship_state.latest_weekly_summary,
            relationship_state=relationship_state,
            notifications=learner_notifications,
        )

    def _primary_preferences(self, *, household: Household) -> ParentPreference:
        if household.parent_profiles:
            return household.parent_profiles[0].preferences
        return ParentPreference()

    def _cadence_decision(
        self,
        *,
        last_event_at: datetime | None,
        session_stuck_loop_risk: str,
        frustration: str,
        now: datetime,
    ) -> str:
        if session_stuck_loop_risk == "high" or frustration == "high":
            return "check_in"
        if last_event_at is None:
            return "session_due"
        elapsed = now - last_event_at
        if elapsed >= timedelta(days=5):
            return "reengage_now"
        if elapsed >= timedelta(days=2):
            return "session_due"
        return "watch"

    def _stall_count(
        self,
        *,
        existing_state: LearnerRelationshipState | None,
        session_stuck_loop_risk: str,
        frustration: str,
        progress_signal: str,
        last_event_at: datetime | None,
    ) -> int:
        stalled = (
            session_stuck_loop_risk == "high"
            or (frustration == "high" and progress_signal in {"flat", "negative"})
        )
        if not stalled:
            return 0
        baseline = existing_state.consecutive_stall_checks if existing_state else 0
        if existing_state is None:
            return 1
        if existing_state.last_session_at == last_event_at:
            return max(1, baseline)
        return baseline + 1

    def _summary_headline(
        self, *, cadence_decision: str, current_goal_title: str | None
    ) -> str:
        if cadence_decision == "reengage_now":
            return "Needs a gentle restart this week."
        if cadence_decision == "check_in":
            return "The teaching loop is asking for parent help."
        if current_goal_title:
            return f"Still moving toward {current_goal_title}."
        return "Progress is steady."

    def _maybe_build_weekly_summary(
        self,
        *,
        household: Household,
        preferences: ParentPreference,
        relationship_state: LearnerRelationshipState,
        summary,
        now: datetime,
    ) -> AutonomousTeacherWeeklySummary | None:
        last_summary_at = relationship_state.last_weekly_summary_at
        if last_summary_at is not None and now - last_summary_at < timedelta(days=7):
            return None
        if (
            last_summary_at is not None
            and self._weekday_name(now=now) != preferences.weekly_summary_day.lower()
        ):
            return None
        celebration = (
            f"Mastered {summary.curriculum_progression.mastered_outcome_count} of "
            f"{summary.curriculum_progression.outcome_count} mapped outcomes."
        )
        support_need = (
            "A short parent check-in would help reset momentum."
            if relationship_state.soft_escalation_active
            else None
        )
        return AutonomousTeacherWeeklySummary(
            learner_id=relationship_state.learner_id,
            headline=relationship_state.summary_headline or "Weekly learning update",
            celebration=celebration,
            support_need=support_need,
            next_focus=relationship_state.next_session_focus,
            generated_at=now,
        )

    def _notifications_for(
        self,
        *,
        household: Household,
        preferences: ParentPreference,
        relationship_state: LearnerRelationshipState,
        weekly_summary: AutonomousTeacherWeeklySummary | None,
        now: datetime,
    ) -> list[ParentNotification]:
        notifications: list[ParentNotification] = []
        week_stamp = now.isocalendar()
        if weekly_summary is not None:
            notifications.append(
                ParentNotification(
                    notification_id=str(uuid4()),
                    household_id=household.household_id,
                    learner_id=relationship_state.learner_id,
                    dedupe_key=(
                        f"weekly:{household.household_id}:{relationship_state.learner_id}:"
                        f"{week_stamp.year}-{week_stamp.week}"
                    ),
                    category="weekly_summary",
                    severity="info",
                    title="Weekly summary ready",
                    message=weekly_summary.headline,
                    created_at=now,
                    updated_at=now,
                    metadata={"next_focus": weekly_summary.next_focus},
                )
            )
        if preferences.soft_escalation_enabled and relationship_state.soft_escalation_active:
            notifications.append(
                ParentNotification(
                    notification_id=str(uuid4()),
                    household_id=household.household_id,
                    learner_id=relationship_state.learner_id,
                    dedupe_key=(
                        f"stall:{household.household_id}:{relationship_state.learner_id}:"
                        f"{relationship_state.consecutive_stall_checks}"
                    ),
                    category="soft_escalation",
                    severity="attention",
                    title="I need your help",
                    message=(
                        "The autonomous teacher sees repeated stall signals and wants a "
                        "quick parent check-in before pushing harder."
                    ),
                    created_at=now,
                    updated_at=now,
                    metadata={
                        "next_session_focus": relationship_state.next_session_focus,
                        "suggested_modality": relationship_state.suggested_modality,
                    },
                )
            )
        follow_up_notification = self._session_suggestion_follow_up_notification(
            household=household,
            relationship_state=relationship_state,
            now=now,
        )
        if follow_up_notification is not None:
            notifications.append(follow_up_notification)
        return notifications

    def _build_session_suggestion(
        self,
        *,
        learner_id: str,
        cadence_decision: str,
        relationship_state: LearnerRelationshipState,
        session,
        auto_session_suggestions: bool,
        now: datetime,
    ) -> AutonomousTeacherSessionSuggestion | None:
        if not auto_session_suggestions:
            return None
        if (
            relationship_state.session_suggestion_status == "snoozed"
            and relationship_state.session_suggestion_snoozed_until is not None
            and relationship_state.session_suggestion_snoozed_until > now
        ):
            return None
        if cadence_decision not in {"session_due", "reengage_now", "check_in"}:
            return None
        return AutonomousTeacherSessionSuggestion(
            learner_id=learner_id,
            cadence_decision=cadence_decision,
            status=relationship_state.session_suggestion_status,
            snoozed_until=relationship_state.session_suggestion_snoozed_until,
            suggested_for=now,
            focus_label=relationship_state.next_session_focus,
            rationale=relationship_state.summary_headline,
            learning_session_id=(
                session.learning_session_id if session is not None else None
            ),
            continue_action_endpoint=(
                session.continue_action.endpoint if session is not None else None
            ),
            target_kc_ids=(
                list(session.active_target_kc_ids) if session is not None else []
            ),
            modality=relationship_state.suggested_modality or "text",
        )

    def _suggested_modality(self, *, content_type: str | None) -> str:
        if content_type in {"worked_example"}:
            return "diagram"
        if content_type in {"micro_explanation", "remedial_micro_module"}:
            return "narrative"
        return "text"

    def _weekday_name(self, *, now: datetime) -> str:
        return now.strftime("%A").lower()

    def _session_suggestion_state_for(
        self,
        *,
        relationship_state: LearnerRelationshipState,
        existing_state: LearnerRelationshipState | None,
        now: datetime,
    ) -> LearnerRelationshipState:
        if existing_state is None:
            return relationship_state
        status = existing_state.session_suggestion_status
        snoozed_until = existing_state.session_suggestion_snoozed_until
        updated_at = existing_state.session_suggestion_updated_at
        if (
            updated_at is not None
            and relationship_state.last_session_at is not None
            and relationship_state.last_session_at > updated_at
        ):
            status = "pending"
            snoozed_until = None
            updated_at = relationship_state.last_session_at
        elif (
            status == "snoozed"
            and snoozed_until is not None
            and snoozed_until <= now
        ):
            status = "pending"
            snoozed_until = None
            updated_at = now
        return relationship_state.model_copy(
            update={
                "session_suggestion_status": status,
                "session_suggestion_snoozed_until": snoozed_until,
                "session_suggestion_updated_at": updated_at,
            }
        )

    def _session_suggestion_follow_up_notification(
        self,
        *,
        household: Household,
        relationship_state: LearnerRelationshipState,
        now: datetime,
    ) -> ParentNotification | None:
        status = relationship_state.session_suggestion_status
        updated_at = relationship_state.session_suggestion_updated_at
        if status not in {"accepted", "deferred"} or updated_at is None:
            return None
        if (
            relationship_state.last_session_at is not None
            and relationship_state.last_session_at > updated_at
        ):
            return None
        threshold = timedelta(days=2 if status == "accepted" else 1)
        if now - updated_at < threshold:
            return None
        if status == "accepted":
            title = "Accepted session still pending"
            message = (
                "You accepted a suggested session, but Dibble has not seen fresh learner "
                "activity yet. It may be time for a gentle follow-through."
            )
            severity = "attention"
        else:
            title = "Deferred session is ready to revisit"
            message = (
                "A deferred session suggestion is coming due. Dibble is ready to bring "
                "that learner back into the teaching loop."
            )
            severity = "info"
        return ParentNotification(
            notification_id=str(uuid4()),
            household_id=household.household_id,
            learner_id=relationship_state.learner_id,
            dedupe_key=(
                f"session-follow-up:{household.household_id}:{relationship_state.learner_id}:"
                f"{status}:{updated_at.isoformat()}"
            ),
            category="session_follow_up",
            severity=severity,
            title=title,
            message=message,
            created_at=now,
            updated_at=now,
            metadata={
                "session_suggestion_status": status,
                "next_session_focus": relationship_state.next_session_focus,
                "suggested_modality": relationship_state.suggested_modality,
            },
        )
