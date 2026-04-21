from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from dibble.models.planning import LearnerGoal, TrajectoryPlan
from dibble.models.profile import LearnerCurriculumProgressionSummary
from dibble.services.errors import LearnerProfileNotFoundError
from dibble.services.learner_progression_service import LearnerProgressionService
from dibble.services.protocols import (
    LearnerGoalStore,
    OutcomeStore,
    ProfileStore,
    TrajectoryStore,
)
from dibble.services.trajectory_planner import TrajectoryPlanner


@dataclass(frozen=True, slots=True)
class CreateLearnerGoalCommand:
    student_id: UUID
    title: str | None = None
    target_outcome_id: str | None = None
    target_kc_ids: list[str] | None = None
    rationale: str | None = None
    source: str = "system_inferred"


@dataclass(frozen=True, slots=True)
class EnsureActiveTrajectoryCommand:
    student_id: UUID
    requested_outcome_id: str | None = None
    requested_target_kc_ids: list[str] | None = None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class CurriculumPlanningResult:
    goal: LearnerGoal | None
    trajectory: TrajectoryPlan | None
    progression: LearnerCurriculumProgressionSummary | None
    goal_created: bool = False
    trajectory_revised: bool = False


@dataclass(slots=True)
class CurriculumPlanningHarness:
    profile_store: ProfileStore
    outcome_store: OutcomeStore
    learner_goal_store: LearnerGoalStore
    trajectory_store: TrajectoryStore
    learner_progression_service: LearnerProgressionService
    trajectory_planner: TrajectoryPlanner

    def create_goal(self, command: CreateLearnerGoalCommand) -> CurriculumPlanningResult:
        profile = self.profile_store.get(command.student_id)
        if profile is None:
            raise LearnerProfileNotFoundError(command.student_id)
        progression = self.learner_progression_service.build_for_student(
            student_id=command.student_id
        )
        goal = self._goal_from_command(command=command, progression=progression)
        if goal is None:
            return CurriculumPlanningResult(goal=None, trajectory=None, progression=progression)

        trajectory = self.trajectory_planner.build_plan(
            student_id=command.student_id,
            goal=goal,
            progression=progression or LearnerCurriculumProgressionSummary(),
        )
        goal = goal.model_copy(
            update={
                "active_trajectory_id": trajectory.trajectory_id,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self.trajectory_store.upsert(
            self._bind_checkpoint_trajectory_ids(trajectory=trajectory)
        )
        self.learner_goal_store.upsert(goal)
        return CurriculumPlanningResult(
            goal=goal,
            trajectory=self.trajectory_store.get(trajectory.trajectory_id),
            progression=progression,
            goal_created=True,
        )

    def ensure_active_trajectory(
        self, command: EnsureActiveTrajectoryCommand
    ) -> CurriculumPlanningResult:
        profile = self.profile_store.get(command.student_id)
        if profile is None:
            raise LearnerProfileNotFoundError(command.student_id)

        progression = self.learner_progression_service.build_for_student(
            student_id=command.student_id
        )
        goal = self.learner_goal_store.get_active_for_student(student_id=command.student_id)
        goal_created = False
        if goal is None:
            seed_goal = self._goal_from_command(
                command=CreateLearnerGoalCommand(
                    student_id=command.student_id,
                    title=None,
                    target_outcome_id=command.requested_outcome_id,
                    target_kc_ids=command.requested_target_kc_ids,
                    rationale=command.rationale,
                ),
                progression=progression,
            )
            if seed_goal is None:
                return CurriculumPlanningResult(
                    goal=None,
                    trajectory=None,
                    progression=progression,
                )
            goal = seed_goal
            goal_created = True
        elif command.requested_outcome_id is not None or command.requested_target_kc_ids:
            goal = goal.model_copy(
                update={
                    "target_outcome_id": command.requested_outcome_id
                    or goal.target_outcome_id,
                    "target_kc_ids": list(
                        command.requested_target_kc_ids or goal.target_kc_ids
                    ),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        existing = (
            self.trajectory_store.get(goal.active_trajectory_id)
            if goal.active_trajectory_id is not None
            else self.trajectory_store.get_active_for_student(student_id=command.student_id)
        )
        baseline_progression = progression or LearnerCurriculumProgressionSummary()

        if existing is None:
            trajectory = self.trajectory_planner.build_plan(
                student_id=command.student_id,
                goal=goal,
                progression=baseline_progression,
            )
            trajectory = self._bind_checkpoint_trajectory_ids(trajectory=trajectory)
            goal = goal.model_copy(
                update={
                    "active_trajectory_id": trajectory.trajectory_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self.trajectory_store.upsert(trajectory)
            self.learner_goal_store.upsert(goal)
            return CurriculumPlanningResult(
                goal=goal,
                trajectory=trajectory,
                progression=progression,
                goal_created=goal_created,
            )

        revised = self.trajectory_planner.revise_plan(
            existing=existing,
            student_id=command.student_id,
            goal=goal,
            progression=baseline_progression,
            rationale=command.rationale or baseline_progression.rationale,
        )
        revised = self._bind_checkpoint_trajectory_ids(trajectory=revised)
        if self.trajectory_planner.semantic_signature(existing) != self.trajectory_planner.semantic_signature(revised) or existing.active_node_id != revised.active_node_id:
            goal = goal.model_copy(
                update={
                    "active_trajectory_id": revised.trajectory_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self.trajectory_store.upsert(revised)
            self.learner_goal_store.upsert(goal)
            return CurriculumPlanningResult(
                goal=goal,
                trajectory=revised,
                progression=progression,
                goal_created=goal_created,
                trajectory_revised=True,
            )

        if goal_created:
            goal = goal.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        self.learner_goal_store.upsert(goal)
        return CurriculumPlanningResult(
            goal=goal,
            trajectory=existing,
            progression=progression,
            goal_created=goal_created,
        )

    def _goal_from_command(
        self,
        *,
        command: CreateLearnerGoalCommand,
        progression: LearnerCurriculumProgressionSummary | None,
    ) -> LearnerGoal | None:
        outcome = (
            self.outcome_store.get(command.target_outcome_id)
            if command.target_outcome_id is not None
            else None
        )
        candidate_outcome_ids = [
            item
            for item in [
                command.target_outcome_id,
                progression.current_outcome.outcome_id
                if progression is not None and progression.current_outcome is not None
                else None,
                progression.next_outcome.outcome_id
                if progression is not None and progression.next_outcome is not None
                else None,
            ]
            if item is not None
        ]
        target_kc_ids = list(
            command.target_kc_ids
            or (list(outcome.knowledge_component_ids) if outcome is not None else [])
            or (
                list(progression.current_outcome.knowledge_component_ids)
                if progression is not None and progression.current_outcome is not None
                else []
            )
            or (
                list(progression.next_outcome.knowledge_component_ids)
                if progression is not None and progression.next_outcome is not None
                else []
            )
        )
        title = (
            command.title
            or (outcome.title if outcome is not None else None)
            or (
                progression.current_outcome.title
                if progression is not None and progression.current_outcome is not None
                else None
            )
            or (
                progression.next_outcome.title
                if progression is not None and progression.next_outcome is not None
                else None
            )
            or ("Current curriculum journey" if target_kc_ids else None)
        )
        if title is None:
            return None
        now = datetime.now(timezone.utc)
        return LearnerGoal(
            goal_id=str(uuid4()),
            student_id=command.student_id,
            title=title,
            source=command.source,
            status="active",
            target_outcome_id=command.target_outcome_id or (outcome.outcome_id if outcome is not None else None),
            target_outcome_ids=candidate_outcome_ids,
            target_kc_ids=target_kc_ids,
            rationale=command.rationale
            or (
                progression.rationale
                if progression is not None and progression.rationale is not None
                else None
            ),
            created_at=now,
            updated_at=now,
        )

    def _bind_checkpoint_trajectory_ids(self, *, trajectory: TrajectoryPlan) -> TrajectoryPlan:
        checkpoints = [
            checkpoint.model_copy(update={"trajectory_id": trajectory.trajectory_id})
            for checkpoint in trajectory.checkpoints
        ]
        return trajectory.model_copy(update={"checkpoints": checkpoints})
