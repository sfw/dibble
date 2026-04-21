from __future__ import annotations

from uuid import uuid4

from dibble.models.curriculum import (
    CurriculumVersionReference,
    KnowledgeComponentUpsert,
    OutcomeUpsert,
)
from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.kc_sequence_planner import KcSequencePlanner
from dibble.services.harness.curriculum_planning import (
    CurriculumPlanningHarness,
    EnsureActiveTrajectoryCommand,
)
from dibble.services.planning_adaptation import PlanningAdaptationService
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
            build_profile(
                student_id, frustration="low", total_load=0.2, kc_mastery=kc_mastery
            )
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

    audit_store = SQLiteAuditStore(conn)
    learner_flow_service = LearnerFlowService(
        audit_store=audit_store,
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
        planning_adaptation_service=PlanningAdaptationService(audit_store=audit_store),
    )
    return profile_store, goal_store, trajectory_store, audit_store, harness


def _record_run_summary(
    audit_store,
    *,
    student_id,
    generation_id: str,
    target_kc_ids: list[str],
    run_summary_score: float,
    intent: str = "practice",
    content_type: str = "practice_problem",
    phase: str = "target",
    modality_plugin_id: str = "text",
    prompt_variant: str = "baseline",
):
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": generation_id,
            "intent": intent,
            "content_type": content_type,
            "target_kc_ids": target_kc_ids,
            "modality_plugin_id": modality_plugin_id,
            "progression_target_stage": phase,
            "prompt_template_variant": prompt_variant,
        },
    )
    return audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=str(student_id),
        payload={
            "source_generation_event_id": generation_event.event_id,
            "generation_id": generation_id,
            "intent": intent,
            "content_type": content_type,
            "target_kc_ids": target_kc_ids,
            "run_summary_score": run_summary_score,
            "run_calibration_signal": (
                "positive" if run_summary_score >= 0.65 else "negative"
            ),
            "run_calibration_confidence": 0.8,
        },
    )


def test_curriculum_planning_harness_creates_goal_and_trajectory(tmp_path):
    student_id = uuid4()
    _, goal_store, trajectory_store, _, harness = _planning_stack(
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
    profile_store, _, _, _, harness = _planning_stack(
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


def test_curriculum_planning_harness_revises_trajectory_from_outcome_history(tmp_path):
    student_id = uuid4()
    _, _, _, audit_store, harness = _planning_stack(
        tmp_path,
        student_id=student_id,
        kc_mastery={"KC-1": 0.86, "KC-2": 0.42, "KC-3": 0.15},
    )

    initial = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )
    _record_run_summary(
        audit_store,
        student_id=student_id,
        generation_id="gen-1",
        target_kc_ids=["KC-2"],
        run_summary_score=0.41,
    )
    _record_run_summary(
        audit_store,
        student_id=student_id,
        generation_id="gen-2",
        target_kc_ids=["KC-2"],
        run_summary_score=0.45,
    )
    _record_run_summary(
        audit_store,
        student_id=student_id,
        generation_id="gen-3",
        target_kc_ids=["KC-2"],
        run_summary_score=0.82,
        intent="remediation",
        content_type="remedial_micro_module",
        phase="repair",
        modality_plugin_id="diagram",
        prompt_variant="rebuild",
    )
    _record_run_summary(
        audit_store,
        student_id=student_id,
        generation_id="gen-4",
        target_kc_ids=["KC-2"],
        run_summary_score=0.43,
    )
    _record_run_summary(
        audit_store,
        student_id=student_id,
        generation_id="gen-5",
        target_kc_ids=["KC-2"],
        run_summary_score=0.84,
        intent="remediation",
        content_type="remedial_micro_module",
        phase="repair",
        modality_plugin_id="diagram",
        prompt_variant="rebuild",
    )

    revised = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )

    assert initial.trajectory is not None
    assert revised.trajectory is not None
    assert revised.trajectory_revised is True
    assert revised.trajectory.nodes[0].node_kind == "recovery_scaffold"
    assert revised.trajectory.nodes[1].outcome_id == "CURR-2"
    assert revised.trajectory.adaptation_state is not None
    assert revised.trajectory.adaptation_state.active_pacing_adjustment == "slower"
    assert revised.trajectory.adaptation_state.active_revisit_density >= 2
    assert revised.trajectory.adaptation_state.preferred_scaffolding_pattern is not None
    assert revised.trajectory.revisions[-1].reasons
    assert any(
        signal.kind.value == "recovery_pattern"
        for signal in revised.trajectory.revisions[-1].observed_signals
    )


def test_curriculum_planning_harness_keeps_weak_outcome_evidence_conservative(tmp_path):
    student_id = uuid4()
    _, _, _, audit_store, harness = _planning_stack(
        tmp_path,
        student_id=student_id,
        kc_mastery={"KC-1": 0.86, "KC-2": 0.42, "KC-3": 0.15},
    )

    initial = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )
    _record_run_summary(
        audit_store,
        student_id=student_id,
        generation_id="gen-1",
        target_kc_ids=["KC-2"],
        run_summary_score=0.44,
    )

    refreshed = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )

    assert initial.trajectory is not None
    assert refreshed.trajectory is not None
    assert refreshed.trajectory_revised is False
    assert refreshed.trajectory.nodes[0].node_kind != "recovery_scaffold"
    assert refreshed.trajectory.adaptation_state is not None
    assert refreshed.trajectory.adaptation_state.active_revisit_density == 1


def test_curriculum_planning_harness_carries_curriculum_snapshot_provenance(tmp_path):
    student_id = uuid4()
    _, _, _, _, harness = _planning_stack(
        tmp_path,
        student_id=student_id,
        kc_mastery={"KC-1": 0.86, "KC-2": 0.42, "KC-3": 0.15},
    )
    provenance = CurriculumVersionReference(
        framework_id="alberta-math-7",
        framework_version="2022",
        framework_import_id="import-123",
        published_snapshot_id="snapshot-123",
        source_label="Alberta Mathematics Grade 7 seed",
    )
    harness.outcome_store.upsert(
        OutcomeUpsert.model_validate(
            {
                **build_outcome(
                    "CURR-2",
                    title="Equivalent Fraction Practice",
                    knowledge_component_ids=["KC-2"],
                ),
                "curriculum_provenance": provenance.model_dump(mode="json"),
            }
        )
    )

    result = harness.ensure_active_trajectory(
        EnsureActiveTrajectoryCommand(student_id=student_id)
    )

    assert result.goal is not None
    assert result.trajectory is not None
    assert result.goal.curriculum_provenance is not None
    assert result.goal.curriculum_provenance.published_snapshot_id == "snapshot-123"
    assert result.trajectory.curriculum_provenance is not None
    assert result.trajectory.curriculum_provenance.framework_import_id == "import-123"
