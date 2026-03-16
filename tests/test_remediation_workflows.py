from uuid import uuid4

import pytest

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
    )

    session = coordinator.start_session(
        student_id=uuid4(),
        target_kc_id="KC-2",
        misconception_description="The learner compares numerator and denominator like whole numbers.",
        curriculum_context=["Equivalent fractions"],
        plan=plan,
    )

    assert session.current_step_index == 0
    assert [step.status for step in session.steps] == ["active", "pending", "pending"]

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
