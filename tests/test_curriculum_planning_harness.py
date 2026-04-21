from __future__ import annotations

from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponentUpsert, OutcomeUpsert
from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.kc_sequence_planner import KcSequencePlanner
from dibble.services.harness.curriculum_planning import (
    CurriculumPlanningHarness,
    EnsureActiveTrajectoryCommand,
)
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.learner_goal_store import SQLiteLearnerGoalStore
from dibble.services.learner_progression_service import LearnerProgressionService
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.remediation_session_store import SQLiteRemediationSessionStore
from dibble.services.session_control_store import SQLiteSessionControlStore
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore
from dibble.services.sqlite_connection import create_connection
from dibble.services.trajectory_planner import TrajectoryPlanner
from dibble.services.trajectory_store import SQLiteTrajectoryStore
from dibble.services.within_session_controller_store import (
    SQLiteWithinSessionControllerStore,
)
from dibble.storage import ensure_database
from tests.support import build_knowledge_component, build_outcome, build_profile


def _planning_stack(tmp_path, *, student_id, kc_mastery):
    database_path = str(tmp_path / "planning-harness.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    profile_store = SQLiteProfileStore(conn)
    outcome_store = SQLiteOutcomeStore(conn)
    kc_store = SQLiteKnowledgeComponentStore(conn)
    goal_store = SQLiteLearnerGoalStore(conn)
    trajectory_store = SQLiteTrajectoryStore(conn)
    session_control_store = SQLiteSessionControlStore(conn)

    profile_store.upsert(
        LearnerProfile.model_validate(
            build_profile(student_id, frustration="low", total_load=0.2, kc_mastery=kc_mastery)
        )
    )
    outcome_store.upsert(
        OutcomeUpsert.model_validate(
            build_outcome(
                "CURR-1",
                title="Fraction Visual Foundations",
                knowledge_component_ids=["KC-1"],
            )
        )
    )
    outcome_store.upsert(
        OutcomeUpsert.model_validate(
            build_outcome(
                "CURR-2",
                title="Equivalent Fraction Practice",
                knowledge_component_ids=["KC-2"],
            )
        )
    )
    outcome_store.upsert(
        OutcomeUpsert.model_validate(
            build_outcome(
                "CURR-3",
                title="Compare Fraction Families",
                knowledge_component_ids=["KC-3"],
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component("KC-1", name="Identify equivalent fractions")
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-3",
                prerequisite_kc_ids=["KC-2"],
                name="Compare fraction families",
            )
        )
    )

    learner_flow_service = LearnerFlowService(
        audit_store=SQLiteAuditStore(conn),
        generated_content_store=SQLiteGeneratedContentStore(conn),
        socratic_session_store=SQLiteSocraticSessionStore(conn),
        remediation_session_store=SQLiteRemediationSessionStore(conn),
        within_session_controller_store=SQLiteWithinSessionControllerStore(conn),
        session_control_store=session_control_store,
    )
    progression_service = LearnerProgressionService(
        profile_store=profile_store,
        outcome_store=outcome_store,
        knowledge_component_store=kc_store,
        learner_flow_service=learner_flow_service,
    )
    harness = CurriculumPlanningHarness(
        profile_store=profile_store,
        outcome_store=outcome_store,
        learner_goal_store=goal_store,
        trajectory_store=trajectory_store,
        learner_progression_service=progression_service,
        trajectory_planner=TrajectoryPlanner(
            kc_sequence_planner=KcSequencePlanner(knowledge_component_store=kc_store),
        ),
    )
    return profile_store, goal_store, trajectory_store, harness


def test_curriculum_planning_harness_creates_goal_and_trajectory(tmp_path):
    student_id = uuid4()
    _, goal_store, trajectory_store, harness = _planning_stack(
        tmp_path,
        student_id=student_id,
        kc_mastery={"KC-1": 0.86, "KC-2": 0.42, "KC-3": 0.15},
    )

    result = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )

    assert result.goal_created is True
    assert result.goal is not None
    assert result.trajectory is not None
    assert result.goal.active_trajectory_id == result.trajectory.trajectory_id
    assert goal_store.get_active_for_student(student_id=student_id) is not None
    assert trajectory_store.get(result.trajectory.trajectory_id) is not None
    assert result.trajectory.nodes[0].outcome_id == "CURR-2"
    assert result.trajectory.checkpoints
    assert result.trajectory.revisions[-1].revision_kind == "created"


def test_curriculum_planning_harness_appends_revision_when_progression_moves(tmp_path):
    student_id = uuid4()
    profile_store, _, _, harness = _planning_stack(
        tmp_path,
        student_id=student_id,
        kc_mastery={"KC-1": 0.86, "KC-2": 0.42, "KC-3": 0.15},
    )
    initial = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )
    profile = profile_store.get(student_id)
    assert profile is not None

    updated_profile = profile.model_copy(
        update={
            "knowledge_state": profile.knowledge_state.model_copy(
                update={
                    "kc_mastery": {
                        **profile.knowledge_state.kc_mastery,
                        "KC-2": 0.9,
                    }
                }
            )
        }
    )
    profile_store.upsert(updated_profile)

    revised = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )

    assert initial.trajectory is not None
    assert revised.trajectory is not None
    assert revised.trajectory_revised is True
    assert len(revised.trajectory.revisions) == 2
    assert revised.trajectory.active_node_id != initial.trajectory.active_node_id
    assert revised.trajectory.nodes[0].outcome_id == "CURR-3"
