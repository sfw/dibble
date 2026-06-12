from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.household import Household, ParentProfile
from dibble.models.household import LearnerRelationshipState
from dibble.models.profile import (
    LearnerContinueAction,
    LearnerFlowNextStep,
    ProfileSummary,
)
from dibble.models.planning import (
    LearnerGoal,
    PlanningAdaptationState,
    PlanningConceptClusterMarker,
    PlanningModalityPreferenceEntry,
    PlanningModalityPreferenceSummary,
    TrajectoryNode,
    TrajectoryPlan,
    TrajectoryRiskLevel,
)
from dibble.models.session_control import SessionControlState
from dibble.services.autonomous_teacher_harness import AutonomousTeacherHarness


@dataclass
class _PlanningResult:
    goal: LearnerGoal | None
    trajectory: TrajectoryPlan | None


class _LearnerSummaryService:
    def __init__(self, summary: ProfileSummary) -> None:
        self.summary = summary

    def build_for_student(self, *, student_id):
        return self.summary


class _CurriculumPlanningHarness:
    def __init__(
        self,
        learner_id: str,
        adaptation_state: PlanningAdaptationState | None = None,
    ) -> None:
        self.learner_id = learner_id
        self.adaptation_state = adaptation_state

    def ensure_active_trajectory(self, command):
        now = datetime.now(timezone.utc)
        goal = LearnerGoal(
            goal_id="goal-1",
            student_id=command.student_id,
            title="Equivalent Fractions",
            target_kc_ids=["KC-1"],
            created_at=now,
            updated_at=now,
        )
        trajectory = TrajectoryPlan(
            trajectory_id="traj-1",
            goal_id=goal.goal_id,
            student_id=command.student_id,
            nodes=[
                TrajectoryNode(
                    node_id="node-1",
                    title="Model equivalent fractions visually",
                    target_kc_ids=["KC-1"],
                )
            ],
            adaptation_state=self.adaptation_state
            or PlanningAdaptationState(
                active_pacing_adjustment="slower",
                preferred_scaffolding_pattern="repair -> remediation",
                concept_cluster_markers=[
                    PlanningConceptClusterMarker(
                        cluster_key="KC-1",
                        label="KC KC-1",
                        target_kc_ids=["KC-1"],
                        risk_level=TrajectoryRiskLevel.moderate,
                        sample_count=3,
                    )
                ],
            ),
            created_at=now,
            updated_at=now,
        )
        return _PlanningResult(goal=goal, trajectory=trajectory)


class _WithinSessionControlHarness:
    def __init__(self, content_type: str = "worked_example") -> None:
        self.content_type = content_type

    def ensure_session(self, command):
        return SessionControlState(
            learning_session_id="session-1",
            student_id=command.student_id,
            goal_id="goal-1",
            trajectory_id="traj-1",
            status="ready_for_next_step",
            phase="target",
            target_stage="target",
            active_target_kc_ids=["KC-1"],
            transfer_target_kc_ids=["KC-1"],
            next_step=LearnerFlowNextStep(
                action="stay_on_requested_target",
                content_type=self.content_type,
                target_stage="target",
                target_kc_ids=["KC-1"],
            ),
            continue_action=LearnerContinueAction.generate_follow_up(
                learning_session_id="session-1",
                content_type=self.content_type,
                target_stage="target",
                target_kc_ids=["KC-1"],
                request_payload={"student_id": str(command.student_id)},
            ),
        )


class _LearnerRelationshipStore:
    def __init__(self) -> None:
        self.states = {}

    def upsert(self, state):
        self.states[(state.household_id, state.learner_id)] = state
        return state

    def get(self, *, household_id: str, learner_id: str):
        return self.states.get((household_id, learner_id))

    def list_for_household(self, *, household_id: str):
        return [state for (hid, _), state in self.states.items() if hid == household_id]


class _ParentNotificationStore:
    def __init__(self) -> None:
        self.notifications = {}

    def upsert(self, notification):
        self.notifications[notification.notification_id] = notification
        return notification

    def list_for_household(self, *, household_id: str):
        return [item for item in self.notifications.values() if item.household_id == household_id]

    def get(self, notification_id: str):
        return self.notifications.get(notification_id)


class _UserStore:
    def list(self):
        return [
            type("User", (), {"learner_id": "learner-1", "user_id": "learner-user-1", "display_name": "Avery", "role": "learner"})()
        ]


def _profile_summary(
    *,
    learner_id: str,
    now: datetime,
    content_type: str = "micro_explanation",
) -> ProfileSummary:
    return ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "low",
            "total_load": 0.4,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": (now - timedelta(days=6)).isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "high",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": content_type,
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": now.isoformat(),
        }
    )


def test_autonomous_teacher_harness_emits_session_suggestion_and_soft_escalation():
    learner_id = str(uuid4())
    now = datetime.now(timezone.utc)
    summary = ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "high",
            "total_load": 0.5,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": (now - timedelta(days=6)).isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "high",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": "worked_example",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": now.isoformat(),
        }
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(learner_id),
        within_session_control_harness=_WithinSessionControlHarness(),
        learner_relationship_state_store=_LearnerRelationshipStore(),
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[
            ParentProfile(
                parent_user_id="parent-1",
                display_name="Pat",
                preferences={
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            )
        ],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    assert len(result.learner_plans) == 1
    plan = result.learner_plans[0]
    assert plan.cadence_decision == "check_in"
    assert plan.next_session is not None
    assert plan.next_session.modality == "diagram"
    assert plan.relationship_state.soft_escalation_active is False
    assert plan.relationship_state.adaptation_state.active_pacing_adjustment == "slower"
    assert plan.relationship_state.adaptation_state.trajectory_risk_level == "moderate"
    assert plan.weekly_summary is not None
    assert result.notifications


def test_autonomous_teacher_harness_blocks_session_until_parent_approval():
    learner_id = str(uuid4())
    now = datetime.now(timezone.utc)
    summary = ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "high",
            "total_load": 0.5,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": (now - timedelta(days=6)).isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "high",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": "worked_example",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": now.isoformat(),
        }
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(learner_id),
        within_session_control_harness=_WithinSessionControlHarness(),
        learner_relationship_state_store=_LearnerRelationshipStore(),
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[ParentProfile(parent_user_id="parent-1", display_name="Pat")],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    plan = result.learner_plans[0]
    assert plan.next_session is None
    assert {
        approval.approval_type
        for approval in plan.relationship_state.approval_requests
        if approval.status == "pending"
    } == {"modality_introduction", "high_autonomy_session"}
    assert any(
        notification.category == "approval_request"
        for notification in result.notifications
    )


def test_autonomous_teacher_harness_respects_parent_preferences_and_persists_latest_summary():
    learner_id = str(uuid4())
    now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    previous_summary = {
        "learner_id": learner_id,
        "headline": "Weekly learning update",
        "celebration": "Mastered 1 of 4 mapped outcomes.",
        "next_focus": "Model equivalent fractions visually",
        "generated_at": "2026-04-18T12:00:00+00:00",
    }
    summary = ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "high",
            "total_load": 0.5,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": (now - timedelta(days=6)).isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "high",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": "worked_example",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": now.isoformat(),
        }
    )
    relationship_store = _LearnerRelationshipStore()
    relationship_store.upsert(
        LearnerRelationshipState.model_validate(
            {
                "household_id": "household-1",
                "learner_id": learner_id,
                "engagement_status": "medium",
                "frustration_status": "low",
                "cadence_status": "watch",
                "soft_escalation_active": False,
                "consecutive_stall_checks": 1,
                "last_weekly_summary_at": "2026-04-18T12:00:00+00:00",
                "latest_weekly_summary": previous_summary,
                "updated_at": "2026-04-18T12:00:00+00:00",
            }
        )
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(learner_id),
        within_session_control_harness=_WithinSessionControlHarness(),
        learner_relationship_state_store=relationship_store,
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[
            ParentProfile(
                parent_user_id="parent-1",
                display_name="Pat",
                preferences={
                    "auto_session_suggestions": False,
                    "soft_escalation_enabled": False,
                    "weekly_summary_day": "sunday",
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            )
        ],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    assert len(result.learner_plans) == 1
    plan = result.learner_plans[0]
    assert plan.next_session is None
    assert plan.relationship_state.soft_escalation_active is False
    assert plan.weekly_summary is not None
    assert plan.weekly_summary.generated_at.isoformat() == "2026-04-18T12:00:00+00:00"
    assert result.notifications == []


def test_autonomous_teacher_harness_resets_session_suggestion_status_after_new_activity():
    learner_id = str(uuid4())
    prior_now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    last_event_at = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    current_now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    summary = ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "low",
            "total_load": 0.4,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": last_event_at.isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "low",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": "worked_example",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": current_now.isoformat(),
        }
    )
    relationship_store = _LearnerRelationshipStore()
    relationship_store.upsert(
        LearnerRelationshipState.model_validate(
            {
                "household_id": "household-1",
                "learner_id": learner_id,
                "engagement_status": "medium",
                "frustration_status": "low",
                "cadence_status": "session_due",
                "session_suggestion_status": "accepted",
                "session_suggestion_updated_at": prior_now.isoformat(),
                "last_session_at": prior_now.isoformat(),
                "updated_at": prior_now.isoformat(),
            }
        )
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(learner_id),
        within_session_control_harness=_WithinSessionControlHarness(),
        learner_relationship_state_store=relationship_store,
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[
            ParentProfile(
                parent_user_id="parent-1",
                display_name="Pat",
                preferences={
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            )
        ],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=current_now)

    assert len(result.learner_plans) == 1
    plan = result.learner_plans[0]
    assert plan.next_session is not None
    assert plan.next_session.status == "pending"


def test_autonomous_teacher_harness_emits_follow_up_for_stale_accepted_suggestion():
    learner_id = str(uuid4())
    action_at = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    summary = ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "low",
            "total_load": 0.4,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": action_at.isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "low",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": "worked_example",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": now.isoformat(),
        }
    )
    relationship_store = _LearnerRelationshipStore()
    relationship_store.upsert(
        LearnerRelationshipState.model_validate(
            {
                "household_id": "household-1",
                "learner_id": learner_id,
                "engagement_status": "medium",
                "frustration_status": "low",
                "cadence_status": "session_due",
                "next_session_focus": "Model equivalent fractions visually",
                "suggested_modality": "diagram",
                "session_suggestion_status": "accepted",
                "session_suggestion_updated_at": action_at.isoformat(),
                "last_session_at": action_at.isoformat(),
                "updated_at": action_at.isoformat(),
            }
        )
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(learner_id),
        within_session_control_harness=_WithinSessionControlHarness(),
        learner_relationship_state_store=relationship_store,
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[
            ParentProfile(
                parent_user_id="parent-1",
                display_name="Pat",
                preferences={
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            )
        ],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    follow_up = next(
        notification
        for notification in result.notifications
        if notification.category == "session_follow_up"
    )
    assert follow_up.title == "Accepted session still pending"
    assert follow_up.metadata["session_suggestion_status"] == "accepted"


def test_autonomous_teacher_harness_emits_follow_up_for_stale_deferred_suggestion():
    learner_id = str(uuid4())
    action_at = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    summary = ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "low",
            "total_load": 0.4,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": action_at.isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "low",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": "worked_example",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": now.isoformat(),
        }
    )
    relationship_store = _LearnerRelationshipStore()
    relationship_store.upsert(
        LearnerRelationshipState.model_validate(
            {
                "household_id": "household-1",
                "learner_id": learner_id,
                "engagement_status": "medium",
                "frustration_status": "low",
                "cadence_status": "session_due",
                "next_session_focus": "Model equivalent fractions visually",
                "suggested_modality": "diagram",
                "session_suggestion_status": "deferred",
                "session_suggestion_updated_at": action_at.isoformat(),
                "last_session_at": action_at.isoformat(),
                "updated_at": action_at.isoformat(),
            }
        )
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(learner_id),
        within_session_control_harness=_WithinSessionControlHarness(),
        learner_relationship_state_store=relationship_store,
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[
            ParentProfile(
                parent_user_id="parent-1",
                display_name="Pat",
                preferences={
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            )
        ],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    follow_up = next(
        notification
        for notification in result.notifications
        if notification.category == "session_follow_up"
    )
    assert follow_up.title == "Deferred session is ready to revisit"
    assert follow_up.metadata["session_suggestion_status"] == "deferred"


def test_autonomous_teacher_harness_uses_relationship_outcomes_to_shift_modality_and_trace():
    learner_id = str(uuid4())
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    summary = ProfileSummary.model_validate(
        {
            "student_id": learner_id,
            "grade_level": "5",
            "profile_version": "v1",
            "kc_count": 1,
            "lo_count": 1,
            "engagement": "medium",
            "frustration": "low",
            "total_load": 0.4,
            "confidence_calibration": 0.4,
            "help_seeking": "medium",
            "recent_activity": {"last_event_at": (now - timedelta(days=6)).isoformat()},
            "current_flow": {
                "session_stuck_loop_risk": "high",
                "next_step": {
                    "action": "stay_on_requested_target",
                    "content_type": "worked_example",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                },
                "continue_action": {
                    "kind": "generate_follow_up",
                    "target_stage": "target",
                    "target_kc_ids": ["KC-1"],
                    "request_payload": {},
                },
            },
            "curriculum_progression": {
                "mastered_outcome_ratio": 0.25,
                "mastered_outcome_count": 1,
                "outcome_count": 4,
            },
            "updated_at": now.isoformat(),
        }
    )
    relationship_store = _LearnerRelationshipStore()
    relationship_store.upsert(
        LearnerRelationshipState.model_validate(
            {
                "household_id": "household-1",
                "learner_id": learner_id,
                "engagement_status": "medium",
                "frustration_status": "low",
                "cadence_status": "watch",
                "approved_modalities": ["text", "diagram"],
                "adaptation_state": {
                    "accepted_suggestion_count": 4,
                    "completed_suggestion_count": 0,
                    "deferred_suggestion_count": 3,
                    "session_suggestion_count": 7,
                    "average_session_outcome_score": 0.42,
                    "modality_outcomes": [
                        {
                            "modality": "diagram",
                            "average_outcome_score": 0.48,
                            "sample_count": 3,
                            "completion_rate": 0.33,
                        },
                        {
                            "modality": "text",
                            "average_outcome_score": 0.79,
                            "sample_count": 4,
                            "completion_rate": 0.75,
                        },
                    ],
                },
                "updated_at": now.isoformat(),
            }
        )
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(learner_id),
        within_session_control_harness=_WithinSessionControlHarness(),
        learner_relationship_state_store=relationship_store,
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[
            ParentProfile(
                parent_user_id="parent-1",
                display_name="Pat",
                preferences={
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            )
        ],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    plan = result.learner_plans[0]
    assert plan.cadence_decision == "session_due"
    assert plan.relationship_state.suggested_modality == "text"
    assert plan.relationship_state.latest_decision_trace is not None
    assert any(
        factor.label == "follow_through"
        for factor in plan.relationship_state.latest_decision_trace.factors
    )


def test_autonomous_teacher_ignores_weak_contextual_modality_evidence():
    learner_id = str(uuid4())
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    summary = _profile_summary(
        learner_id=learner_id,
        now=now,
        content_type="micro_explanation",
    )
    adaptation_state = PlanningAdaptationState(
        modality_preferences=PlanningModalityPreferenceSummary(
            preferred_by_content_family=[
                PlanningModalityPreferenceEntry(
                    preference_key="micro_explanation",
                    context_label="content family micro_explanation",
                    preferred_modality="diagram",
                    sample_count=1,
                    average_outcome_score=0.9,
                    positive_outcome_rate=1.0,
                )
            ]
        )
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(
            learner_id,
            adaptation_state=adaptation_state,
        ),
        within_session_control_harness=_WithinSessionControlHarness(
            content_type="micro_explanation"
        ),
        learner_relationship_state_store=_LearnerRelationshipStore(),
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[
            ParentProfile(
                parent_user_id="parent-1",
                preferences={
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            )
        ],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    plan = result.learner_plans[0]
    assert plan.relationship_state.suggested_modality == "narrative"
    assert plan.relationship_state.latest_decision_trace is not None
    assert (
        plan.relationship_state.latest_decision_trace.modality_preferences
        .preferred_by_content_family[0]
        .preferred_modality
        == "diagram"
    )


def test_autonomous_teacher_contextual_modality_still_requires_parent_approval():
    learner_id = str(uuid4())
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    summary = _profile_summary(
        learner_id=learner_id,
        now=now,
        content_type="micro_explanation",
    )
    adaptation_state = PlanningAdaptationState(
        modality_preferences=PlanningModalityPreferenceSummary(
            preferred_by_content_family=[
                PlanningModalityPreferenceEntry(
                    preference_key="micro_explanation",
                    context_label="content family micro_explanation",
                    preferred_modality="diagram",
                    sample_count=3,
                    average_outcome_score=0.76,
                    positive_outcome_rate=0.67,
                )
            ]
        )
    )
    relationship_store = _LearnerRelationshipStore()
    relationship_store.upsert(
        LearnerRelationshipState(
            household_id="household-1",
            learner_id=learner_id,
            approved_modalities=["text"],
        )
    )
    harness = AutonomousTeacherHarness(
        learner_summary_service=_LearnerSummaryService(summary),
        curriculum_planning_harness=_CurriculumPlanningHarness(
            learner_id,
            adaptation_state=adaptation_state,
        ),
        within_session_control_harness=_WithinSessionControlHarness(
            content_type="micro_explanation"
        ),
        learner_relationship_state_store=relationship_store,
        parent_notification_store=_ParentNotificationStore(),
        user_store=_UserStore(),
    )
    household = Household(
        household_id="household-1",
        household_name="Home",
        parent_profiles=[ParentProfile(parent_user_id="parent-1")],
        learner_ids=[learner_id],
    )

    result = harness.orchestrate_household(household=household, now=now)

    plan = result.learner_plans[0]
    assert plan.relationship_state.suggested_modality == "diagram"
    assert plan.next_session is None
    approval = plan.relationship_state.approval_requests[0]
    assert approval.approval_type.value == "modality_introduction"
    assert approval.proposed_value == "diagram"
    assert plan.relationship_state.latest_decision_trace is not None
    assert (
        "modality_introduction"
        in plan.relationship_state.latest_decision_trace.blocking_approval_types
    )
