from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from dibble.models.household import (
    AutonomousTeacherDecisionFactor,
    AutonomousTeacherDecisionTrace,
    AutonomousTeacherLearnerPlan,
    AutonomousTeacherModalityOutcome,
    AutonomousTeacherSessionSuggestion,
    AutonomousTeacherWeeklySummary,
    Household,
    LearnerRelationshipAdaptationState,
    LearnerRelationshipState,
    ParentApprovalRequest,
    ParentApprovalStatus,
    ParentApprovalType,
    ParentPreference,
    ParentNotification,
)
from dibble.models.observability import HarnessBoundary, OperationalTraceStatus
from dibble.models.planning import (
    PlanningModalityPreferenceEntry,
    PlanningModalityPreferenceSummary,
)
from dibble.models.rollout import (
    AutonomousOutboundMode,
    AutonomousSessionSuggestionMode,
    ParentApprovalEnforcementMode,
    RolloutCapability,
    RolloutCapabilityDecision,
)
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.rollout_decision_service import RolloutDecisionService
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
    AuditStore,
    LearnerRelationshipStateStore,
    ModalityRoutingPriorStore,
    ParentNotificationStore,
    UserStore,
)


@dataclass(frozen=True, slots=True)
class ParentApprovalCandidate:
    approval_type: ParentApprovalType
    title: str
    message: str
    proposed_value: str | None
    metadata: dict[str, object]
    expires_at: datetime | None = None

    def decision_signature(self) -> str:
        return str(self.metadata.get("decision_signature", ""))


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
    audit_store: AuditStore | None = None
    modality_routing_prior_store: ModalityRoutingPriorStore | None = None
    operational_observability_service: OperationalObservabilityService | None = None
    rollout_decision_service: RolloutDecisionService | None = None

    def orchestrate_household(
        self,
        *,
        household: Household,
        now: datetime | None = None,
    ) -> AutonomousTeacherHouseholdResult:
        return self._orchestrate_household(
            household=household,
            now=now,
            persist=True,
        )

    def preview_household(
        self,
        *,
        household: Household,
        now: datetime | None = None,
    ) -> AutonomousTeacherHouseholdResult:
        return self._orchestrate_household(
            household=household,
            now=now,
            persist=False,
        )

    def _orchestrate_household(
        self,
        *,
        household: Household,
        now: datetime | None,
        persist: bool,
    ) -> AutonomousTeacherHouseholdResult:
        reference_time = now or datetime.now(timezone.utc)
        learner_plans: list[AutonomousTeacherLearnerPlan] = []
        notifications: list[ParentNotification] = []
        for learner_id in household.learner_ids:
            plan = self._plan_for_learner(
                household=household,
                learner_id=learner_id,
                now=reference_time,
                persist=persist,
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
        persist: bool,
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
        base_preferences = self._primary_preferences(household=household)
        suggestion_decision = self._rollout_decision(
            capability=RolloutCapability.autonomous_session_suggestions,
            household_id=household.household_id,
            learner_id=learner_id,
        )
        approval_decision = self._rollout_decision(
            capability=RolloutCapability.parent_approval_enforcement,
            household_id=household.household_id,
            learner_id=learner_id,
        )
        outbound_decision = self._rollout_decision(
            capability=RolloutCapability.autonomous_teacher_outbound_actions,
            household_id=household.household_id,
            learner_id=learner_id,
        )
        preferences = self._preferences_with_rollout(
            preferences=base_preferences,
            approval_decision=approval_decision,
        )
        adaptation_state, approval_requests = self._adaptation_state_for(
            existing_state=existing_state,
            student_id=student_id,
            planning=planning,
            last_event_at=summary.recent_activity.last_event_at,
            session_stuck_loop_risk=summary.current_flow.session_stuck_loop_risk,
            frustration=summary.frustration.value,
            progress_signal=summary.progress.signal,
            now=now,
        )
        cadence_decision = self._cadence_decision(
            last_event_at=summary.recent_activity.last_event_at,
            session_stuck_loop_risk=summary.current_flow.session_stuck_loop_risk,
            frustration=summary.frustration.value,
            adaptation_state=adaptation_state,
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
            ),
            approved_modalities=(
                list(existing_state.approved_modalities)
                if existing_state is not None and existing_state.approved_modalities
                else ["text"]
            ),
            adaptation_state=adaptation_state,
        )
        trajectory_signature = self._trajectory_signature(
            planning=planning,
            next_focus=next_focus,
        )
        approved_modalities = (
            list(existing_state.approved_modalities)
            if existing_state is not None and existing_state.approved_modalities
            else ["text"]
        )
        approval_requests, blocking_approvals = self._resolve_approval_requests(
            household=household,
            learner_id=learner_id,
            preferences=preferences,
            existing_state=existing_state,
            approval_requests=approval_requests,
            approved_modalities=approved_modalities,
            trajectory_signature=trajectory_signature,
            cadence_decision=cadence_decision,
            next_focus=next_focus,
            suggested_modality=suggested_modality,
            session=session,
            now=now,
        )
        summary_headline = self._summary_headline(
            cadence_decision=cadence_decision,
            current_goal_title=planning.goal.title if planning.goal is not None else None,
            blocking_approvals=blocking_approvals,
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
            summary_headline=summary_headline,
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
            approved_modalities=approved_modalities,
            active_trajectory_signature=trajectory_signature,
            approval_requests=approval_requests,
            adaptation_state=adaptation_state,
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
        relationship_state = relationship_state.model_copy(
            update={
                "latest_decision_trace": self._decision_trace(
                    cadence_decision=cadence_decision,
                    suggested_modality=relationship_state.suggested_modality,
                    modality_preferences=relationship_state.adaptation_state.modality_preferences,
                    blocking_approvals=blocking_approvals,
                    adaptation_state=relationship_state.adaptation_state,
                    session_stuck_loop_risk=summary.current_flow.session_stuck_loop_risk,
                    frustration=summary.frustration.value,
                    last_event_at=summary.recent_activity.last_event_at,
                    now=now,
                )
            }
        )
        if persist:
            self.learner_relationship_state_store.upsert(relationship_state)

        learner_notifications = self._notifications_for(
            household=household,
            preferences=preferences,
            relationship_state=relationship_state,
            weekly_summary=weekly_summary,
            now=now,
            outbound_decision=outbound_decision,
        )
        if persist:
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
            auto_session_suggestions=(
                preferences.auto_session_suggestions
                and (
                    suggestion_decision is None
                    or suggestion_decision.mode
                    != AutonomousSessionSuggestionMode.disabled.value
                )
            ),
            blocking_approvals=blocking_approvals,
            now=now,
        )
        if persist:
            self._record_plan_trace(
                household_id=household.household_id,
                learner_id=learner_id,
                cadence_decision=cadence_decision,
                relationship_state=relationship_state,
                blocking_approvals=blocking_approvals,
                notifications=learner_notifications,
                session_suggestion=session_suggestion,
                suggestion_decision=suggestion_decision,
                approval_decision=approval_decision,
                outbound_decision=outbound_decision,
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

    def _record_plan_trace(
        self,
        *,
        household_id: str,
        learner_id: str,
        cadence_decision: str,
        relationship_state: LearnerRelationshipState,
        blocking_approvals: list[ParentApprovalRequest],
        notifications: list[ParentNotification],
        session_suggestion: AutonomousTeacherSessionSuggestion | None,
        suggestion_decision: RolloutCapabilityDecision | None,
        approval_decision: RolloutCapabilityDecision | None,
        outbound_decision: RolloutCapabilityDecision | None,
    ) -> None:
        payload = {
            "cadence_decision": cadence_decision,
            "suggested_modality": relationship_state.suggested_modality,
            "blocking_approval_types": [
                approval.approval_type.value for approval in blocking_approvals
            ],
            "notification_categories": [notification.category for notification in notifications],
            "session_suggestion_status": (
                session_suggestion.status if session_suggestion is not None else None
            ),
            "approval_request_count": len(relationship_state.approval_requests),
            "summary_headline": relationship_state.summary_headline,
            "rollout_bucket_id": (
                suggestion_decision.evaluation_bucket_id
                if suggestion_decision is not None
                else None
            ),
            "rollout_autonomous_suggestions_mode": (
                suggestion_decision.mode if suggestion_decision is not None else None
            ),
            "rollout_parent_approval_mode": (
                approval_decision.mode if approval_decision is not None else None
            ),
            "rollout_outbound_mode": (
                outbound_decision.mode if outbound_decision is not None else None
            ),
        }
        if self.audit_store is not None:
            self.audit_store.append(
                event_type="autonomous_teacher.plan",
                status="blocked" if blocking_approvals else "applied",
                student_id=learner_id,
                payload=payload,
            )
        if self.operational_observability_service is None:
            return
        self.operational_observability_service.record_trace(
            harness=HarnessBoundary.autonomous_teacher,
            operation="orchestrate_learner",
            status=OperationalTraceStatus.success,
            summary=(
                "Autonomous teacher produced a learner plan behind approval gates."
                if blocking_approvals
                else "Autonomous teacher produced a learner plan."
            ),
            student_id=learner_id,
            household_id=household_id,
            reason_code="approval_blocked" if blocking_approvals else "plan_generated",
            payload=payload,
        )

    def _primary_preferences(self, *, household: Household) -> ParentPreference:
        if household.parent_profiles:
            return household.parent_profiles[0].preferences
        return ParentPreference()

    def _rollout_decision(
        self,
        *,
        capability: RolloutCapability,
        household_id: str,
        learner_id: str,
    ) -> RolloutCapabilityDecision | None:
        if self.rollout_decision_service is None:
            return None
        return self.rollout_decision_service.decision_for(
            capability=capability,
            household_id=household_id,
            learner_id=learner_id,
        )

    def _preferences_with_rollout(
        self,
        *,
        preferences: ParentPreference,
        approval_decision: RolloutCapabilityDecision | None,
    ) -> ParentPreference:
        if approval_decision is None:
            return preferences
        if approval_decision.mode == ParentApprovalEnforcementMode.strict.value:
            return preferences.model_copy(
                update={
                    "modality_introduction_requires_approval": True,
                    "trajectory_revision_requires_approval": True,
                    "high_autonomy_session_requires_approval": True,
                }
            )
        if approval_decision.mode == ParentApprovalEnforcementMode.disabled.value:
            return preferences.model_copy(
                update={
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                }
            )
        return preferences

    def _adaptation_state_for(
        self,
        *,
        existing_state: LearnerRelationshipState | None,
        student_id: UUID,
        planning,
        last_event_at: datetime | None,
        session_stuck_loop_risk: str,
        frustration: str,
        progress_signal: str,
        now: datetime,
    ) -> tuple[LearnerRelationshipAdaptationState, list[ParentApprovalRequest]]:
        base = (
            existing_state.adaptation_state
            if existing_state is not None
            else LearnerRelationshipAdaptationState()
        )
        approval_requests = self._active_approval_requests(
            existing_state=existing_state,
            now=now,
        )
        stalled = (
            session_stuck_loop_risk == "high"
            or (frustration == "high" and progress_signal in {"flat", "negative"})
        )
        stall_episode_count = base.stall_episode_count
        recovery_episode_count = base.recovery_episode_count
        if stalled and (existing_state is None or existing_state.consecutive_stall_checks == 0):
            stall_episode_count += 1
        elif (
            not stalled
            and existing_state is not None
            and existing_state.consecutive_stall_checks > 0
        ):
            recovery_episode_count += 1
        average_session_outcome_score = self._recent_session_outcome_score(
            student_id=student_id
        )
        if self.audit_store is None and base.average_session_outcome_score != 0.5:
            average_session_outcome_score = base.average_session_outcome_score
        updated_approvals: list[ParentApprovalRequest] = []
        approval_follow_through_count = base.approval_follow_through_count
        for approval in approval_requests:
            if (
                approval.status == ParentApprovalStatus.approved
                and approval.decided_at is not None
                and last_event_at is not None
                and last_event_at > approval.decided_at
                and not bool(approval.metadata.get("follow_through_recorded"))
            ):
                approval_follow_through_count += 1
                updated_approvals.append(
                    approval.model_copy(
                        update={
                            "metadata": {
                                **approval.metadata,
                                "follow_through_recorded": True,
                            }
                        }
                    )
                )
                continue
            updated_approvals.append(approval)
        modality_outcomes = self._modality_outcomes_for(student_id=student_id)
        if not modality_outcomes and base.modality_outcomes:
            modality_outcomes = list(base.modality_outcomes)
        planning_adaptation = (
            planning.trajectory.adaptation_state
            if planning.trajectory is not None
            else None
        )
        trajectory_risk_level = (
            planning_adaptation.concept_cluster_markers[0].risk_level.value
            if planning_adaptation is not None
            and planning_adaptation.concept_cluster_markers
            else base.trajectory_risk_level
        )
        updated_state = base.model_copy(
            update={
                "approval_follow_through_count": approval_follow_through_count,
                "average_session_outcome_score": average_session_outcome_score,
                "recent_session_outcome_score": average_session_outcome_score,
                "stall_episode_count": stall_episode_count,
                "recovery_episode_count": recovery_episode_count,
                "planning_revision_count": (
                    len(planning.trajectory.revisions)
                    if planning.trajectory is not None
                    else base.planning_revision_count
                ),
                "trajectory_risk_level": trajectory_risk_level,
                "active_pacing_adjustment": (
                    planning_adaptation.active_pacing_adjustment
                    if planning_adaptation is not None
                    else base.active_pacing_adjustment
                ),
                "active_recovery_pattern": (
                    planning_adaptation.preferred_scaffolding_pattern
                    if planning_adaptation is not None
                    else base.active_recovery_pattern
                ),
                "modality_outcomes": modality_outcomes,
                "modality_preferences": (
                    planning_adaptation.modality_preferences
                    if planning_adaptation is not None
                    else base.modality_preferences
                ),
                "updated_at": now,
            }
        )
        return updated_state, updated_approvals

    def _recent_session_outcome_score(self, *, student_id: UUID) -> float:
        if self.audit_store is None:
            return 0.5
        summary_events = [
            event
            for event in self.audit_store.list(limit=120)
            if event.event_type == "learning.run.summary" and event.student_id == student_id
        ]
        if not summary_events:
            return 0.5
        recent_scores = [
            float(event.payload.get("run_summary_score", 0.5))
            for event in summary_events[:5]
        ]
        return round(sum(recent_scores) / len(recent_scores), 2)

    def _modality_outcomes_for(
        self,
        *,
        student_id: UUID,
    ) -> list[AutonomousTeacherModalityOutcome]:
        if self.modality_routing_prior_store is None:
            return []
        priors = [
            prior
            for prior in self.modality_routing_prior_store.list_for_learner(
                learner_id=student_id
            )
            if prior.scope == "plugin" and prior.context_key == "__global__"
        ]
        outcomes: list[AutonomousTeacherModalityOutcome] = []
        for prior in priors:
            outcomes.append(
                AutonomousTeacherModalityOutcome(
                    modality=prior.prior_key,
                    average_outcome_score=prior.average_outcome_score,
                    sample_count=prior.evidence_count,
                    completion_rate=prior.positive_outcome_rate,
                    last_outcome_at=prior.last_outcome_at,
                )
            )
        outcomes.sort(
            key=lambda item: (
                item.average_outcome_score,
                item.completion_rate,
                item.sample_count,
                item.modality,
            ),
            reverse=True,
        )
        return outcomes

    def _decision_trace(
        self,
        *,
        cadence_decision: str,
        suggested_modality: str | None,
        modality_preferences: PlanningModalityPreferenceSummary,
        blocking_approvals: list[ParentApprovalRequest],
        adaptation_state: LearnerRelationshipAdaptationState,
        session_stuck_loop_risk: str,
        frustration: str,
        last_event_at: datetime | None,
        now: datetime,
    ) -> AutonomousTeacherDecisionTrace:
        elapsed_days = (
            round((now - last_event_at).total_seconds() / (60 * 60 * 24), 1)
            if last_event_at is not None
            else None
        )
        return AutonomousTeacherDecisionTrace(
            cadence_decision=cadence_decision,
            suggested_modality=suggested_modality,
            modality_preferences=modality_preferences,
            blocking_approval_types=[
                approval.approval_type.value for approval in blocking_approvals
            ],
            average_session_outcome_score=adaptation_state.average_session_outcome_score,
            suggestion_completion_rate=adaptation_state.suggestion_completion_rate,
            reengagement_success_rate=adaptation_state.reengagement_success_rate,
            approval_follow_through_rate=adaptation_state.approval_follow_through_rate,
            recovery_rate=adaptation_state.recovery_rate,
            factors=[
                AutonomousTeacherDecisionFactor(
                    label="session_outcomes",
                    score=round(adaptation_state.average_session_outcome_score - 0.5, 2),
                    detail="Recent session outcomes provide a bounded long-horizon planning signal.",
                ),
                AutonomousTeacherDecisionFactor(
                    label="follow_through",
                    score=round(
                        adaptation_state.suggestion_completion_rate
                        - adaptation_state.deferred_suggestion_count / max(
                            adaptation_state.accepted_suggestion_count
                            + adaptation_state.deferred_suggestion_count,
                            1,
                        ),
                        2,
                    ),
                    detail=(
                        "Parent acceptance versus completion history keeps autonomous"
                        " suggestions from overcommitting when follow-through is weak."
                    ),
                ),
                AutonomousTeacherDecisionFactor(
                    label="stall_recovery",
                    score=round(adaptation_state.recovery_rate - 0.5, 2),
                    detail=(
                        "Repeated stalls and recoveries shape how assertively Dibble"
                        " tries to re-engage the learner."
                    ),
                ),
                AutonomousTeacherDecisionFactor(
                    label="trajectory_adaptation",
                    score=(
                        0.2
                        if adaptation_state.active_pacing_adjustment == "slower"
                        or adaptation_state.trajectory_risk_level in {"moderate", "high"}
                        else -0.05
                    ),
                    detail=(
                        "Long-horizon planning adjustments stay visible to the autonomous "
                        "teacher so re-engagement respects current pacing and risk."
                    ),
                ),
                AutonomousTeacherDecisionFactor(
                    label="current_risk",
                    score=(
                        0.45
                        if session_stuck_loop_risk == "high" or frustration == "high"
                        else -0.1
                    ),
                    detail=(
                        f"Current risk snapshot: stuck_loop={session_stuck_loop_risk},"
                        f" frustration={frustration}, days_since_activity={elapsed_days}."
                    ),
                ),
            ],
        )

    def _cadence_decision(
        self,
        *,
        last_event_at: datetime | None,
        session_stuck_loop_risk: str,
        frustration: str,
        adaptation_state: LearnerRelationshipAdaptationState,
        now: datetime,
    ) -> str:
        if session_stuck_loop_risk == "high" or frustration == "high":
            if (
                adaptation_state.accepted_suggestion_count >= 2
                and adaptation_state.suggestion_completion_rate < 0.34
            ):
                return "session_due"
            return "check_in"
        if last_event_at is None:
            return "session_due"
        elapsed = now - last_event_at
        if elapsed >= timedelta(days=5):
            if (
                adaptation_state.accepted_suggestion_count >= 2
                and adaptation_state.reengagement_success_rate < 0.34
            ):
                return "session_due"
            return "reengage_now"
        if elapsed >= timedelta(days=2):
            if adaptation_state.accepted_suggestion_count < 2:
                return "session_due"
            if (
                adaptation_state.average_session_outcome_score >= 0.68
                or adaptation_state.recovery_rate >= 0.5
            ):
                return "session_due"
            return "watch"
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
        self,
        *,
        cadence_decision: str,
        current_goal_title: str | None,
        blocking_approvals: list[ParentApprovalRequest],
    ) -> str:
        if any(
            approval.status == ParentApprovalStatus.rejected
            for approval in blocking_approvals
        ):
            return "A parent-held approval gate is pausing the next teaching change."
        if blocking_approvals:
            return "Waiting for parent approval before the next teaching change."
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
        outbound_decision: RolloutCapabilityDecision | None,
    ) -> list[ParentNotification]:
        if (
            outbound_decision is not None
            and outbound_decision.mode == AutonomousOutboundMode.disabled.value
        ):
            return []
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
        for approval in relationship_state.approval_requests:
            if approval.status != ParentApprovalStatus.pending:
                continue
            notifications.append(
                ParentNotification(
                    notification_id=str(uuid4()),
                    household_id=household.household_id,
                    learner_id=relationship_state.learner_id,
                    dedupe_key=(
                        f"approval:{household.household_id}:{relationship_state.learner_id}:"
                        f"{approval.approval_id}"
                    ),
                    category="approval_request",
                    severity="attention",
                    title=approval.title,
                    message=approval.message,
                    created_at=now,
                    updated_at=now,
                    metadata={
                        "approval_id": approval.approval_id,
                        "approval_type": approval.approval_type.value,
                        "proposed_value": approval.proposed_value,
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
        blocking_approvals: list[ParentApprovalRequest],
        now: datetime,
    ) -> AutonomousTeacherSessionSuggestion | None:
        if not auto_session_suggestions:
            return None
        if blocking_approvals:
            return None
        if (
            relationship_state.session_suggestion_status == "snoozed"
            and relationship_state.session_suggestion_snoozed_until is not None
            and relationship_state.session_suggestion_snoozed_until > now
        ):
            return None
        if (
            relationship_state.session_suggestion_status not in {"accepted", "deferred"}
            and cadence_decision not in {"session_due", "reengage_now", "check_in"}
        ):
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

    def _suggested_modality(
        self,
        *,
        content_type: str | None,
        approved_modalities: list[str],
        adaptation_state: LearnerRelationshipAdaptationState,
    ) -> str:
        if content_type in {"worked_example"}:
            default = "diagram"
        elif content_type in {"micro_explanation", "remedial_micro_module"}:
            default = "narrative"
        else:
            default = "text"
        contextual = self._contextual_modality_for_suggestion(
            content_type=content_type,
            adaptation_state=adaptation_state,
        )
        if contextual is not None:
            return contextual
        outcomes = {item.modality: item for item in adaptation_state.modality_outcomes}
        default_outcome = outcomes.get(default)
        text_outcome = outcomes.get("text")
        if (
            default_outcome is not None
            and default_outcome.sample_count >= 2
            and default_outcome.average_outcome_score < 0.56
            and text_outcome is not None
            and text_outcome.average_outcome_score
            >= default_outcome.average_outcome_score + 0.08
        ):
            default = "text"
        approved_outcomes = [
            item
            for item in adaptation_state.modality_outcomes
            if item.modality in approved_modalities and item.sample_count >= 2
        ]
        if approved_outcomes:
            approved_outcomes.sort(
                key=lambda item: (
                    item.average_outcome_score,
                    item.completion_rate,
                    item.sample_count,
                    item.modality,
                ),
                reverse=True,
            )
            best = approved_outcomes[0]
            if best.average_outcome_score >= 0.68:
                return best.modality
        return default

    def _contextual_modality_for_suggestion(
        self,
        *,
        content_type: str | None,
        adaptation_state: LearnerRelationshipAdaptationState,
    ) -> str | None:
        preferences = adaptation_state.modality_preferences
        candidates: list[PlanningModalityPreferenceEntry] = []
        if content_type is not None:
            candidates.extend(
                entry
                for entry in preferences.preferred_by_content_family
                if entry.preference_key == content_type
            )
        if adaptation_state.trajectory_risk_level in {"moderate", "high"}:
            candidates.extend(
                entry
                for entry in preferences.preferred_by_risk_bucket
                if entry.preference_key == adaptation_state.trajectory_risk_level
            )
        if adaptation_state.active_recovery_pattern is not None:
            candidates.extend(
                entry
                for entry in preferences.preferred_by_recovery_pattern
                if entry.context_label == adaptation_state.active_recovery_pattern
                or entry.preference_key == adaptation_state.active_recovery_pattern
            )
        conservative = [
            entry
            for entry in candidates
            if entry.sample_count >= 2
            and entry.average_outcome_score >= 0.68
            and entry.positive_outcome_rate >= 0.5
        ]
        if not conservative:
            return None
        conservative.sort(
            key=lambda entry: (
                entry.average_outcome_score,
                entry.positive_outcome_rate,
                entry.recovery_rate,
                entry.sample_count,
                entry.preferred_modality,
            ),
            reverse=True,
        )
        return conservative[0].preferred_modality

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
        adaptation_state = relationship_state.adaptation_state
        if (
            updated_at is not None
            and relationship_state.last_session_at is not None
            and relationship_state.last_session_at > (updated_at + timedelta(minutes=1))
        ):
            if status == "accepted":
                adaptation_state = adaptation_state.model_copy(
                    update={
                        "completed_suggestion_count": (
                            adaptation_state.completed_suggestion_count + 1
                        ),
                        "updated_at": relationship_state.last_session_at,
                    }
                )
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
                "adaptation_state": adaptation_state,
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

    def _trajectory_signature(self, *, planning, next_focus: str | None) -> str | None:
        if planning.goal is None and planning.trajectory is None:
            return None
        payload = {
            "goal_title": planning.goal.title if planning.goal is not None else None,
            "next_focus": next_focus,
            "node_titles": (
                [node.title for node in planning.trajectory.nodes[:3]]
                if planning.trajectory is not None
                else []
            ),
            "node_kinds": (
                [node.node_kind for node in planning.trajectory.nodes[:3]]
                if planning.trajectory is not None
                else []
            ),
            "expected_session_counts": (
                [node.expected_session_count for node in planning.trajectory.nodes[:3]]
                if planning.trajectory is not None
                else []
            ),
            "target_kc_ids": (
                sorted(
                    {
                        kc_id
                        for node in planning.trajectory.nodes[:3]
                        for kc_id in node.target_kc_ids
                    }
                )
                if planning.trajectory is not None
                else []
            ),
            "planning_adjustments": (
                [
                    adjustment.action_type.value
                    for adjustment in (
                        planning.trajectory.adaptation_state.active_adjustments
                        if planning.trajectory is not None
                        and planning.trajectory.adaptation_state is not None
                        else []
                    )
                ]
            ),
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _active_approval_requests(
        self,
        *,
        existing_state: LearnerRelationshipState | None,
        now: datetime,
    ) -> list[ParentApprovalRequest]:
        if existing_state is None:
            return []
        requests: list[ParentApprovalRequest] = []
        for approval in existing_state.approval_requests:
            if (
                approval.status == ParentApprovalStatus.pending
                and approval.expires_at is not None
                and approval.expires_at <= now
            ):
                requests.append(
                    approval.model_copy(
                        update={
                            "status": ParentApprovalStatus.expired,
                            "decided_at": now,
                        }
                    )
                )
                continue
            requests.append(approval)
        return requests

    def _resolve_approval_requests(
        self,
        *,
        household: Household,
        learner_id: str,
        preferences: ParentPreference,
        existing_state: LearnerRelationshipState | None,
        approval_requests: list[ParentApprovalRequest],
        approved_modalities: list[str],
        trajectory_signature: str | None,
        cadence_decision: str,
        next_focus: str | None,
        suggested_modality: str | None,
        session,
        now: datetime,
    ) -> tuple[list[ParentApprovalRequest], list[ParentApprovalRequest]]:
        resolved_requests = list(approval_requests)
        blocking: list[ParentApprovalRequest] = []
        for candidate in self._approval_candidates(
            household=household,
            learner_id=learner_id,
            preferences=preferences,
            existing_state=existing_state,
            approval_requests=approval_requests,
            approved_modalities=approved_modalities,
            trajectory_signature=trajectory_signature,
            cadence_decision=cadence_decision,
            next_focus=next_focus,
            suggested_modality=suggested_modality,
            session=session,
            now=now,
        ):
            existing_request = next(
                (
                    approval
                    for approval in reversed(resolved_requests)
                    if approval.metadata.get("decision_signature")
                    == candidate.decision_signature()
                ),
                None,
            )
            if existing_request is None:
                created = ParentApprovalRequest(
                    approval_id=str(uuid4()),
                    learner_id=learner_id,
                    approval_type=candidate.approval_type,
                    title=candidate.title,
                    message=candidate.message,
                    proposed_value=candidate.proposed_value,
                    metadata=candidate.metadata,
                    requested_at=now,
                    expires_at=candidate.expires_at,
                )
                resolved_requests.append(created)
                blocking.append(created)
                continue
            if existing_request.status in {
                ParentApprovalStatus.pending,
                ParentApprovalStatus.rejected,
            }:
                blocking.append(existing_request)
        return resolved_requests, blocking

    def _approval_candidates(
        self,
        *,
        household: Household,
        learner_id: str,
        preferences: ParentPreference,
        existing_state: LearnerRelationshipState | None,
        approval_requests: list[ParentApprovalRequest],
        approved_modalities: list[str],
        trajectory_signature: str | None,
        cadence_decision: str,
        next_focus: str | None,
        suggested_modality: str | None,
        session,
        now: datetime,
    ) -> list[ParentApprovalCandidate]:
        candidates: list[ParentApprovalCandidate] = []
        existing_trajectory_request = (
            next(
                (
                    approval
                    for approval in reversed(approval_requests)
                    if approval.approval_type == ParentApprovalType.trajectory_revision
                    and approval.metadata.get("trajectory_signature") == trajectory_signature
                ),
                None,
            )
            if trajectory_signature is not None
            else None
        )
        if (
            preferences.modality_introduction_requires_approval
            and suggested_modality is not None
            and suggested_modality not in approved_modalities
        ):
            decision_signature = self._approval_signature(
                learner_id=learner_id,
                approval_type=ParentApprovalType.modality_introduction,
                proposed_value=suggested_modality,
                extra={"household_id": household.household_id},
            )
            candidates.append(
                ParentApprovalCandidate(
                    approval_type=ParentApprovalType.modality_introduction,
                    title=f"Approve {suggested_modality} lessons",
                    message=(
                        "Dibble wants to introduce a new teaching modality for this learner "
                        f"before the next session: {suggested_modality}."
                    ),
                    proposed_value=suggested_modality,
                    metadata={
                        "decision_signature": decision_signature,
                        "suggested_modality": suggested_modality,
                    },
                    expires_at=now + timedelta(days=14),
                )
            )
        if (
            preferences.trajectory_revision_requires_approval
            and existing_state is not None
            and trajectory_signature is not None
            and (
                trajectory_signature != existing_state.active_trajectory_signature
                or existing_trajectory_request is not None
            )
        ):
            decision_signature = self._approval_signature(
                learner_id=learner_id,
                approval_type=ParentApprovalType.trajectory_revision,
                proposed_value=trajectory_signature,
                extra={"next_focus": next_focus},
            )
            candidates.append(
                ParentApprovalCandidate(
                    approval_type=ParentApprovalType.trajectory_revision,
                    title="Approve trajectory revision",
                    message=(
                        "Dibble wants to revise the learner's longer-horizon plan before "
                        f"continuing. Proposed next focus: {next_focus or 'the updated trajectory'}."
                    ),
                    proposed_value=next_focus,
                    metadata={
                        "decision_signature": decision_signature,
                        "trajectory_signature": trajectory_signature,
                        "next_focus": next_focus,
                    },
                    expires_at=now + timedelta(days=14),
                )
            )
        if (
            preferences.high_autonomy_session_requires_approval
            and session is not None
            and cadence_decision in {"check_in", "reengage_now"}
        ):
            decision_signature = self._approval_signature(
                learner_id=learner_id,
                approval_type=ParentApprovalType.high_autonomy_session,
                proposed_value=session.learning_session_id,
                extra={
                    "cadence_decision": cadence_decision,
                    "next_focus": next_focus,
                },
            )
            candidates.append(
                ParentApprovalCandidate(
                    approval_type=ParentApprovalType.high_autonomy_session,
                    title="Approve autonomous re-engagement",
                    message=(
                        "Dibble is ready to initiate a higher-autonomy session to re-engage "
                        "this learner, but it is waiting for parent approval first."
                    ),
                    proposed_value=session.learning_session_id,
                    metadata={
                        "decision_signature": decision_signature,
                        "learning_session_id": session.learning_session_id,
                        "cadence_decision": cadence_decision,
                        "next_focus": next_focus,
                    },
                    expires_at=now + timedelta(days=7),
                )
            )
        return candidates

    def _approval_signature(
        self,
        *,
        learner_id: str,
        approval_type: ParentApprovalType,
        proposed_value: str | None,
        extra: dict[str, object],
    ) -> str:
        payload = {
            "learner_id": learner_id,
            "approval_type": approval_type.value,
            "proposed_value": proposed_value,
            "extra": extra,
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
