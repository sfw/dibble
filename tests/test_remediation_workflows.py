from uuid import uuid4

import pytest

from dibble.models.profile import LearnerStrategySummary
from dibble.models.remediation import KcSequenceSummary
from dibble.services.remediation_planner import RemediationPlan
from dibble.services.remediation_session_store import SQLiteRemediationSessionStore
from dibble.services.remediation_workflows import (
    RemediationWorkflowCompleteError,
    RemediationWorkflowCoordinator,
)
from dibble.storage import ensure_database


def test_remediation_workflow_coordinator_persists_and_advances_steps(tmp_path):
    database_path = str(tmp_path / "remediation-workflows.db")
    ensure_database(database_path)
    session_store = SQLiteRemediationSessionStore(database_path)
    coordinator = RemediationWorkflowCoordinator(session_store=session_store)

    plan = RemediationPlan(
        focus_kc_ids=["KC-1", "KC-2"],
        prerequisite_kc_ids=["KC-1"],
        misconception_signals=[],
        rationale="Step back through the prerequisite before returning to the target.",
        module_blueprint={
            "trigger": "misconception_detected",
            "steps": [
                {
                    "phase": "step_back",
                    "target_kc_ids": ["KC-1"],
                    "support_level": "high",
                    "objective": "Reconnect the prerequisite concept.",
                    "guidance": "Use one simple example.",
                },
                {
                    "phase": "repair",
                    "target_kc_ids": ["KC-1"],
                    "support_level": "medium",
                    "objective": "Repair the misconception explicitly.",
                    "guidance": "Contrast the misconception with the correct reasoning.",
                    "misconception_ids": ["fraction-whole-number-bias"],
                },
                {
                    "phase": "return",
                    "target_kc_ids": ["KC-2"],
                    "support_level": "low",
                    "objective": "Bridge back to the target.",
                    "guidance": "End with one transfer check.",
                },
            ],
        },
        kc_sequence=KcSequenceSummary(
            action="rebuild_prerequisite_first",
            primary_kc_id="KC-1",
            ordered_kc_ids=["KC-1", "KC-2"],
            deferred_kc_ids=["KC-2"],
            rationale="Rebuild the prerequisite before returning to the target.",
        ),
    )

    session = coordinator.start_session(
        student_id=uuid4(),
        target_kc_id="KC-2",
        misconception_description="The learner compares numerator and denominator like whole numbers.",
        curriculum_context=["Equivalent fractions"],
        plan=plan,
        strategy_summary=LearnerStrategySummary(
            signal="support_intensive",
            source="strategy_profile",
            support_bias=-1,
            recovery_focus="prerequisite_rebuild",
            confidence=0.79,
            matched_run_count=4,
            matched_session_count=3,
            rationale="The learner has struggled across sessions and should step back before transfer.",
        ),
    )

    assert session.current_step_index == 0
    assert [step.status for step in session.steps] == ["active", "pending", "pending"]
    assert session.strategy_summary.signal == "support_intensive"

    loaded_session, current_step, generation_request = coordinator.generation_request_for_current_step(
        session_id=session.session_id,
        learner_prompt="Keep it visual.",
        curriculum_context=["Use a fraction bar."],
    )

    assert loaded_session.session_id == session.session_id
    assert current_step.phase == "step_back"
    assert generation_request.learning_session_id == session.session_id
    assert generation_request.target_kc_ids == ["KC-1"]
    assert generation_request.requested_content_type == "remedial_micro_module"
    assert "Keep it visual." in (generation_request.learner_prompt or "")
    assert "Use one simple example." in (generation_request.learner_prompt or "")
    assert "Reconnect the prerequisite concept." in generation_request.curriculum_context
    assert any("Learner strategy: support_intensive" in item for item in generation_request.curriculum_context)
    assert any("Rebuild prerequisite understanding" in item for item in generation_request.curriculum_context)
    assert any("KC sequencing: rebuild_prerequisite_first" in item for item in generation_request.curriculum_context)

    updated_session = coordinator.complete_current_step(
        session_id=session.session_id,
        generation_id="gen-step-back",
    )
    assert updated_session.current_step_index == 1
    assert [step.status for step in updated_session.steps] == ["completed", "active", "pending"]
    assert updated_session.completed_generation_ids == ["gen-step-back"]

    updated_session = coordinator.complete_current_step(
        session_id=session.session_id,
        generation_id="gen-repair",
    )
    assert updated_session.current_step_index == 2
    assert updated_session.steps[2].recommended_content_type == "practice_problem"

    updated_session = coordinator.complete_current_step(
        session_id=session.session_id,
        generation_id="gen-return",
    )
    assert updated_session.current_step_index is None
    assert [step.status for step in updated_session.steps] == ["completed", "completed", "completed"]
    assert updated_session.completed_generation_ids == [
        "gen-step-back",
        "gen-repair",
        "gen-return",
    ]

    with pytest.raises(RemediationWorkflowCompleteError):
        coordinator.generation_request_for_current_step(session_id=session.session_id)


def test_remediation_workflow_coordinator_carries_bridge_sequence_context(tmp_path):
    database_path = str(tmp_path / "remediation-workflows-bridge.db")
    ensure_database(database_path)
    session_store = SQLiteRemediationSessionStore(database_path)
    coordinator = RemediationWorkflowCoordinator(session_store=session_store)

    plan = RemediationPlan(
        focus_kc_ids=["KC-1", "KC-2", "KC-3"],
        prerequisite_kc_ids=["KC-1"],
        misconception_signals=[],
        rationale="Repair the prerequisite, bridge through a nearby KC, then return to the target.",
        module_blueprint={
            "trigger": "misconception_detected",
            "bridge_target_kc_ids": ["KC-2"],
            "steps": [
                {
                    "phase": "step_back",
                    "target_kc_ids": ["KC-1"],
                    "support_level": "high",
                    "objective": "Reconnect the prerequisite concept.",
                    "guidance": "Use one simple example.",
                },
                {
                    "phase": "bridge",
                    "target_kc_ids": ["KC-2"],
                    "support_level": "medium",
                    "objective": "Bridge through a nearby knowledge component.",
                    "guidance": "Fade support a bit before the target return.",
                },
                {
                    "phase": "return",
                    "target_kc_ids": ["KC-3"],
                    "support_level": "low",
                    "objective": "Check transfer on the target.",
                    "guidance": "End with one transfer check.",
                },
            ],
        },
        kc_sequence=KcSequenceSummary(
            action="rebuild_prerequisite_first",
            primary_kc_id="KC-1",
            ordered_kc_ids=["KC-1", "KC-2", "KC-3"],
            bridge_kc_ids=["KC-2"],
            deferred_kc_ids=["KC-3"],
            rationale="Use nearby bridge KC(s) KC-2 before returning fully to the target.",
        ),
    )

    session = coordinator.start_session(
        student_id=uuid4(),
        target_kc_id="KC-3",
        misconception_description="The learner needs a nearby bridge before returning to the target.",
        curriculum_context=["Equivalent fractions"],
        plan=plan,
        strategy_summary=LearnerStrategySummary(
            signal="support_intensive",
            source="strategy_profile",
            recovery_focus="prerequisite_rebuild",
        ),
    )

    session = coordinator.complete_current_step(
        session_id=session.session_id,
        generation_id="gen-step-back",
    )
    loaded_session, current_step, generation_request = coordinator.generation_request_for_current_step(
        session_id=session.session_id,
        learner_prompt="Keep it visual.",
    )

    assert loaded_session.session_id == session.session_id
    assert current_step.phase == "bridge"
    assert current_step.recommended_content_type == "remedial_micro_module"
    assert any("Bridge through nearby KC(s) KC-2" in item for item in generation_request.curriculum_context)
