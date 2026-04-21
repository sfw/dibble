from __future__ import annotations

from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationRequest,
    GenerationResponse,
    InterventionType,
    RequestedContentType,
)
from dibble.models.curriculum import KnowledgeComponentUpsert, OutcomeUpsert
from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.harness.curriculum_planning import (
    CurriculumPlanningHarness,
)
from dibble.services.harness.within_session_control import (
    BindGenerationRequestCommand,
    SummarizeGeneratedContentCommand,
    WithinSessionControlHarness,
)
from dibble.services.kc_sequence_planner import KcSequencePlanner
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


def _control_harness(tmp_path, *, student_id):
    database_path = str(tmp_path / "session-control.db")
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
            build_profile(
                student_id,
                frustration="low",
                total_load=0.2,
                kc_mastery={"KC-1": 0.86, "KC-2": 0.4},
            )
        )
    )
    outcome_store.upsert(OutcomeUpsert.model_validate(build_outcome()))
    kc_store.upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component()))

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
    planning_harness = CurriculumPlanningHarness(
        profile_store=profile_store,
        outcome_store=outcome_store,
        learner_goal_store=goal_store,
        trajectory_store=trajectory_store,
        learner_progression_service=progression_service,
        trajectory_planner=TrajectoryPlanner(
            kc_sequence_planner=KcSequencePlanner(knowledge_component_store=kc_store)
        ),
    )
    return WithinSessionControlHarness(
        curriculum_planning_harness=planning_harness,
        session_control_store=session_control_store,
    )


def test_within_session_control_harness_owns_next_step_and_continue_action(tmp_path):
    student_id = uuid4()
    harness = _control_harness(tmp_path, student_id=student_id)

    bound = harness.bind_generation_request(
        BindGenerationRequestCommand(
            request=GenerationRequest(
                student_id=student_id,
                learning_session_id="session-1",
                target_kc_ids=["KC-1"],
                requested_content_type=RequestedContentType.micro_explanation,
            )
        )
    )
    assert bound.session is not None

    content = GeneratedContent(
        generation_id="gen-1",
        student_id=student_id,
        content_type=RequestedContentType.micro_explanation.value,
        request_context={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "progression": {
                "action": "hold_target",
                "target_stage": "target",
                "applied_target_kc_ids": ["KC-1"],
                "transfer_target_kc_ids": ["KC-1"],
                "rationale": "Stay on the current target for one more guided step.",
            },
        },
        response=GenerationResponse(
            student_id=student_id,
            route=AdaptiveRouteDecision(
                intervention_type=InterventionType.reteach,
                delivery_mode=DeliveryMode.generated,
                scaffolding_level="medium",
                reasons=["test"],
            ),
            blocks=[GeneratedBlock(kind="explanation", title="Explain", body="Body")],
            curriculum_context=["Equivalent fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(),
    )

    result = harness.summarize_generated_content(
        SummarizeGeneratedContentCommand(generated_content=content)
    )

    assert result.session is not None
    assert result.session.current_generation_id == "gen-1"
    assert result.content.workflow_summary is not None
    assert result.content.workflow_summary.goal_id == bound.session.goal_id
    assert result.content.workflow_summary.next_step.content_type == "practice_problem"
    assert (
        result.content.workflow_summary.continue_action.kind.value
        == "generate_follow_up"
    )
