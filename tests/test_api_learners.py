from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app

from tests.support import build_curriculum_resource, build_knowledge_component, build_profile


def test_healthcheck(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_profile_round_trip_and_summary(client, student_id):
    put_response = client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    profile_response = client.get(f"/api/learners/{student_id}/profile")
    summary_response = client.get(f"/api/learners/{student_id}/summary")
    list_response = client.get("/api/learners")

    assert put_response.status_code == 200
    assert profile_response.status_code == 200
    assert summary_response.status_code == 200
    assert summary_response.json()["kc_count"] == 2
    assert summary_response.json()["engagement"] == "medium"
    assert summary_response.json()["frustration"] == "high"
    assert summary_response.json()["confidence_calibration"] == 0.5
    assert summary_response.json()["calibration"]["source"] == "insufficient"
    assert summary_response.json()["progress"]["source"] == "insufficient"
    assert summary_response.json()["strategy"]["source"] == "insufficient"
    assert summary_response.json()["state_profile"]["source"] == "insufficient"
    assert summary_response.json()["trait_profile"]["source"] == "insufficient"
    assert summary_response.json()["recent_activity"]["generation_count"] == 0
    assert summary_response.json()["current_flow"]["status"] == "idle"
    assert summary_response.json()["current_flow"]["flow_type"] == "idle"
    assert profile_response.json()["profile_metadata"]["student_id"] == str(student_id)
    assert str(student_id) in list_response.json()


def test_learner_workspace_returns_machine_readable_not_found_error(client, student_id):
    response = client.get(f"/api/learners/{student_id}/workspace")

    assert response.status_code == 404
    assert response.headers["x-dibble-error-code"] == "learner_profile_not_found"


def test_profile_summary_exposes_recent_calibration_and_activity(client, student_id, app_settings):
    from dibble.services.audit_store import SQLiteAuditStore

    audit_store = SQLiteAuditStore(app_settings.database_path)
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, engagement="high", help_seeking="medium"))
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "summary-gen-1",
            "learning_session_id": "summary-session-1",
        },
    )
    audit_store.append(
        event_type="learning.calibration.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "average_run_outcome_score": 0.79,
            "average_run_confidence": 0.74,
            "matched_run_count": 4,
            "matched_session_count": 2,
            "profile_signal": "positive",
        },
    )
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.78,
            "average_run_confidence": 0.73,
            "matched_run_count": 4,
            "matched_session_count": 2,
            "positive_run_rate": 0.75,
            "negative_run_rate": 0.0,
            "recent_average_run_outcome_score": 0.82,
            "prior_average_run_outcome_score": 0.69,
            "progress_delta": 0.13,
            "progress_signal": "improving",
        },
    )
    audit_store.append(
        event_type="learning.strategy.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "average_run_outcome_score": 0.78,
            "average_run_confidence": 0.73,
            "matched_run_count": 4,
            "matched_session_count": 2,
            "progress_signal": "improving",
            "progress_delta": 0.13,
            "strategy_signal": "independence_ready",
            "strategy_support_bias": 1,
            "strategy_recovery_focus": "independent_practice",
            "strategy_trajectory_state": "accelerating",
            "strategy_recommended_next_action": "check_transfer_readiness",
            "strategy_volatility_index": 0.0,
            "strategy_relapse_risk": 0.05,
        },
    )
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "average_run_outcome_score": 0.78,
            "average_run_confidence": 0.73,
            "matched_run_count": 4,
            "matched_session_count": 2,
            "progress_signal": "improving",
            "progress_delta": 0.13,
            "strategy_signal": "independence_ready",
            "strategy_trajectory_state": "accelerating",
            "state_profile_signal": "independence_ready",
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.44,
            "confidence_calibration": 0.77,
            "help_seeking": "low",
            "self_monitoring": 0.8,
        },
    )
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "matched_observation_count": 6,
            "matched_session_count": 2,
            "profile_signal": "stable",
            "processing_speed": {"value": 0.75, "confidence": 0.78},
            "working_memory": {"value": 0.71, "confidence": 0.77},
            "spatial_reasoning": {"value": 0.66, "confidence": 0.63},
        },
    )

    response = client.get(f"/api/learners/{student_id}/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["engagement"] == "high"
    assert payload["help_seeking"] == "medium"
    assert payload["calibration"]["source"] == "profile"
    assert payload["calibration"]["signal"] == "positive"
    assert payload["calibration"]["matched_session_count"] == 2
    assert payload["progress"]["source"] == "profile"
    assert payload["progress"]["signal"] == "improving"
    assert payload["progress"]["progress_delta"] == 0.13
    assert payload["strategy"]["source"] == "strategy_profile"
    assert payload["strategy"]["signal"] == "independence_ready"
    assert payload["strategy"]["support_bias"] == 1
    assert payload["strategy"]["trajectory_state"] == "accelerating"
    assert payload["strategy"]["recommended_next_action"] == "check_transfer_readiness"
    assert payload["state_profile"]["source"] == "state_profile"
    assert payload["state_profile"]["signal"] == "independence_ready"
    assert payload["state_profile"]["total_load"] == 0.44
    assert payload["trait_profile"]["source"] == "trait_profile"
    assert payload["trait_profile"]["processing_speed"]["value"] == 0.75
    assert payload["trait_profile"]["working_memory"]["value"] == 0.71
    assert payload["recent_activity"]["generation_count"] == 1
    assert payload["recent_activity"]["last_generation_id"] == "summary-gen-1"
    assert payload["recent_activity"]["last_learning_session_id"] == "summary-session-1"
    assert payload["current_flow"]["status"] == "idle"


def test_learner_flow_endpoint_exposes_backend_owned_next_step(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    for hints_used, confidence in [(3, 0.62), (2, 0.58)]:
        observe_response = client.post(
            f"/api/learners/{student_id}/observations",
            json={
                "response_time_ms": 21000,
                "hints_used": hints_used,
                "error_count": 0,
                "pause_count": 1,
                "modality_switches": 0,
                "completed": True,
                "confidence": confidence,
                "task_type": "practice",
                "support_level": "high",
                "expected_duration_ms": 18000,
                "learning_session_id": "flow-session-1",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
            },
        )
        assert observe_response.status_code == 200

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "flow-session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    flow_response = client.get(f"/api/learners/{student_id}/flow")
    summary_response = client.get(f"/api/learners/{student_id}/summary")

    assert generate_response.status_code == 200
    assert flow_response.status_code == 200
    assert summary_response.status_code == 200

    flow_payload = flow_response.json()
    summary_payload = summary_response.json()
    assert flow_payload["status"] == "ready_for_next_step"
    assert flow_payload["flow_type"] == "lesson"
    assert flow_payload["learning_session_id"] == "flow-session-1"
    assert flow_payload["progression_action"] == "hold_target"
    assert flow_payload["progression_source"] == "workflow_summary"
    assert flow_payload["target_stage"] == "target"
    assert flow_payload["active_target_kc_ids"] == ["KC-1"]
    assert flow_payload["next_step_source"] == "workflow_summary"
    assert flow_payload["next_step"]["content_type"] == "practice_problem"
    assert flow_payload["next_step"]["target_kc_ids"] == ["KC-1"]
    assert flow_payload["continue_action"]["kind"] == "generate_follow_up"
    assert flow_payload["continue_action"]["endpoint"] == "/api/content/generate"
    assert summary_payload["current_flow"]["progression_action"] == "hold_target"
    assert summary_payload["current_flow"]["progression_source"] == "workflow_summary"
    assert summary_payload["current_flow"]["next_step_source"] == "workflow_summary"
    assert summary_payload["current_flow"]["next_step"]["content_type"] == "practice_problem"
    assert summary_payload["current_flow"]["continue_action"]["kind"] == "generate_follow_up"


def test_learner_flow_endpoint_prefers_active_remediation_workflow(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify numerator and denominator"),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            name="Generate equivalent fractions",
            common_misconceptions=[
                {
                    "misconception_id": "fraction-whole-number-bias",
                    "label": "Treats fraction parts like unrelated whole numbers",
                    "description": "The learner compares numerator and denominator separately instead of the whole amount.",
                    "trigger_terms": ["different amounts", "numerator", "denominator", "whole number"],
                    "prerequisite_kc_ids": ["KC-1"],
                    "remediation_hint": "Use one visual model to compare the total amount before naming the parts.",
                }
            ],
        ),
    )

    trigger_response = client.post(
        "/api/remedial/trigger",
        json={
            "student_id": str(student_id),
            "target_kc_id": "KC-2",
            "misconception_description": "The learner thinks 1/2 and 2/4 are different amounts.",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    flow_response = client.get(f"/api/learners/{student_id}/flow")
    summary_response = client.get(f"/api/learners/{student_id}/summary")

    assert trigger_response.status_code == 200
    assert flow_response.status_code == 200
    assert summary_response.status_code == 200

    flow_payload = flow_response.json()
    summary_payload = summary_response.json()
    assert flow_payload["status"] == "in_progress"
    assert flow_payload["flow_type"] == "remediation"
    assert flow_payload["remediation_session_id"] == trigger_response.json()["request_context"]["remediation_session_id"]
    assert flow_payload["current_phase"] == "repair"
    assert flow_payload["progression_action"] == "advance"
    assert flow_payload["target_stage"] == "repair"
    assert flow_payload["next_step"]["content_type"] == "remedial_micro_module"
    assert flow_payload["next_step"]["target_kc_ids"] == ["KC-1"]
    assert flow_payload["continue_action"]["kind"] == "advance_remediation"
    assert summary_payload["current_flow"]["flow_type"] == "remediation"
    assert summary_payload["current_flow"]["current_phase"] == "repair"
    assert summary_payload["current_flow"]["continue_action"]["kind"] == "advance_remediation"


def test_learner_history_endpoints_expose_generation_socratic_and_remediation_history(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify numerator and denominator"),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            name="Generate equivalent fractions",
            common_misconceptions=[
                {
                    "misconception_id": "fraction-whole-number-bias",
                    "label": "Treats fraction parts like unrelated whole numbers",
                    "description": "The learner compares numerator and denominator separately instead of the whole amount.",
                    "trigger_terms": ["numerator", "denominator", "whole number", "fraction"],
                    "prerequisite_kc_ids": ["KC-1"],
                    "remediation_hint": "Use one visual model to compare the total amount before naming the parts.",
                }
            ],
        ),
    )

    lesson_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "history-lesson-session",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    socratic_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "learning_session_id": "history-socratic-session",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "learner_response": "Equivalent fractions are the same amount because 1/2 and 2/4 cover equal space on the model.",
            "learner_confidence": 0.72,
        },
    )
    remediation_response = client.post(
        "/api/remedial/trigger",
        json={
            "student_id": str(student_id),
            "target_kc_id": "KC-2",
            "misconception_description": "The learner compares numerator and denominator like whole numbers.",
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    generations_response = client.get(f"/api/learners/{student_id}/history/generations")
    socratic_history_response = client.get(f"/api/learners/{student_id}/history/socratic-sessions")
    remediation_history_response = client.get(f"/api/learners/{student_id}/history/remediation-sessions")

    assert lesson_response.status_code == 200
    assert socratic_response.status_code == 200
    assert remediation_response.status_code == 200
    assert generations_response.status_code == 200
    assert socratic_history_response.status_code == 200
    assert remediation_history_response.status_code == 200

    generations_payload = generations_response.json()
    socratic_history_payload = socratic_history_response.json()
    remediation_history_payload = remediation_history_response.json()

    assert generations_payload[0]["flow_type"] == "remediation"
    assert generations_payload[0]["generation_id"] == remediation_response.json()["generation_id"]
    assert generations_payload[0]["continue_action"]["kind"] == "advance_remediation"
    assert generations_payload[0]["content_type"] == "remedial_micro_module"
    assert generations_payload[0]["intervention_type"] is not None
    assert any(entry["generation_id"] == lesson_response.json()["generation_id"] for entry in generations_payload)

    assert socratic_history_payload[0]["session_id"] == socratic_response.json()["session_id"]
    assert socratic_history_payload[0]["status"] == "ready_for_follow_up"
    assert socratic_history_payload[0]["latest_steering_action"] == "verify_transfer"
    assert socratic_history_payload[0]["continue_action"]["kind"] == "generate_follow_up"

    assert remediation_history_payload[0]["session_id"] == remediation_response.json()["request_context"]["remediation_session_id"]
    assert remediation_history_payload[0]["target_kc_id"] == "KC-2"
    assert remediation_history_payload[0]["status"] == "in_progress"
    assert remediation_history_payload[0]["current_phase"] == "repair"
    assert remediation_history_payload[0]["continue_action"]["kind"] == "advance_remediation"


def test_learner_history_endpoints_return_machine_readable_not_found_error(client, student_id):
    generations_response = client.get(f"/api/learners/{student_id}/history/generations")
    socratic_history_response = client.get(f"/api/learners/{student_id}/history/socratic-sessions")
    remediation_history_response = client.get(f"/api/learners/{student_id}/history/remediation-sessions")

    assert generations_response.status_code == 404
    assert generations_response.headers["x-dibble-error-code"] == "learner_profile_not_found"
    assert socratic_history_response.status_code == 404
    assert socratic_history_response.headers["x-dibble-error-code"] == "learner_profile_not_found"
    assert remediation_history_response.status_code == 404
    assert remediation_history_response.headers["x-dibble-error-code"] == "learner_profile_not_found"


def test_teacher_intervention_action_contract_exposes_backend_owned_proposal_and_records_approval(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "teacher-action-session",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    contract_response = client.get(f"/api/learners/{student_id}/intervention-action")
    approve_response = client.post(
        f"/api/learners/{student_id}/intervention-action",
        json={"decision": "approve", "note": "Teacher approves the next backend-owned move."},
    )
    refreshed_contract_response = client.get(f"/api/learners/{student_id}/intervention-action")
    audit_response = client.get("/api/audit/events")

    assert generate_response.status_code == 200
    assert contract_response.status_code == 200
    assert approve_response.status_code == 200
    assert refreshed_contract_response.status_code == 200

    contract_payload = contract_response.json()
    approve_payload = approve_response.json()
    refreshed_payload = refreshed_contract_response.json()

    assert contract_payload["proposal_status"] == "available"
    assert contract_payload["flow_type"] == "lesson"
    assert contract_payload["allowed_decisions"] == ["approve", "defer", "escalate_human"]
    assert contract_payload["proposed_action"]["kind"] == "generate_follow_up"
    assert contract_payload["proposed_action"]["endpoint"] == "/api/content/generate"

    assert approve_payload["latest_decision"]["decision"] == "approve"
    assert approve_payload["latest_decision"]["status"] == "approved"
    assert approve_payload["latest_decision"]["note"] == "Teacher approves the next backend-owned move."
    assert approve_payload["latest_decision"]["execution_action"]["kind"] == "generate_follow_up"
    assert approve_payload["latest_decision"]["execution_action"]["request_payload"]["source_generation_id"] == (
        generate_response.json()["generation_id"]
    )

    assert refreshed_payload["latest_decision"]["decision"] == "approve"
    assert refreshed_payload["latest_decision"]["status"] == "approved"
    assert refreshed_payload["action_key"] == approve_payload["action_key"]

    decision_event = next(
        event for event in audit_response.json() if event["event_type"] == "teacher.intervention.decision"
    )
    assert decision_event["payload"]["action_key"] == approve_payload["action_key"]
    assert decision_event["payload"]["decision"] == "approve"
    assert decision_event["payload"]["execution_action"]["kind"] == "generate_follow_up"


def test_teacher_intervention_action_contract_rejects_idle_or_invalid_teacher_decisions(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))

    idle_contract_response = client.get(f"/api/learners/{student_id}/intervention-action")
    unavailable_response = client.post(
        f"/api/learners/{student_id}/intervention-action",
        json={"decision": "approve"},
    )

    assert idle_contract_response.status_code == 200
    assert idle_contract_response.json()["proposal_status"] == "unavailable"
    assert idle_contract_response.json()["allowed_decisions"] == []
    assert unavailable_response.status_code == 409
    assert unavailable_response.headers["x-dibble-error-code"] == "teacher_intervention_unavailable"

    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "teacher-action-invalid-decision",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    invalid_response = client.post(
        f"/api/learners/{student_id}/intervention-action",
        json={"decision": "skip"},
    )

    assert invalid_response.status_code == 400
    assert invalid_response.headers["x-dibble-error-code"] == "teacher_intervention_invalid_decision"


def test_learner_workspace_returns_active_generated_content(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    for hints_used, confidence in [(3, 0.62), (2, 0.58)]:
        observe_response = client.post(
            f"/api/learners/{student_id}/observations",
            json={
                "response_time_ms": 21000,
                "hints_used": hints_used,
                "error_count": 0,
                "pause_count": 1,
                "modality_switches": 0,
                "completed": True,
                "confidence": confidence,
                "task_type": "practice",
                "support_level": "high",
                "expected_duration_ms": 18000,
                "learning_session_id": "workspace-lesson-session",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
            },
        )
        assert observe_response.status_code == 200

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "workspace-lesson-session",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    workspace_response = client.get(f"/api/learners/{student_id}/workspace")

    assert generate_response.status_code == 200
    assert workspace_response.status_code == 200

    generation_id = generate_response.json()["generation_id"]
    payload = workspace_response.json()
    assert payload["active_artifact"]["kind"] == "generated_content"
    assert payload["active_artifact"]["resource_id"] == generation_id
    assert payload["generated_content"]["generation_id"] == generation_id
    assert payload["generated_content"]["workflow_summary"]["progression_action"] == "hold_target"
    assert payload["summary"]["current_flow"]["last_generation_id"] == generation_id
    assert payload["continue_action"]["kind"] == "generate_follow_up"
    assert payload["continue_action"]["request_payload"]["source_generation_id"] == generation_id


def test_learner_flow_uses_persisted_workflow_summary_after_restart(app_settings):
    student_id = uuid4()
    app_one = create_app(app_settings)
    app_two = create_app(app_settings)

    with TestClient(app_one) as client_one:
        client_one.put(
            f"/api/learners/{student_id}/profile",
            json=build_profile(student_id, frustration="low", total_load=0.2),
        )
        client_one.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

        for hints_used, confidence in [(3, 0.62), (2, 0.58)]:
            observe_response = client_one.post(
                f"/api/learners/{student_id}/observations",
                json={
                    "response_time_ms": 21000,
                    "hints_used": hints_used,
                    "error_count": 0,
                    "pause_count": 1,
                    "modality_switches": 0,
                    "completed": True,
                    "confidence": confidence,
                    "task_type": "practice",
                    "support_level": "high",
                    "expected_duration_ms": 18000,
                    "learning_session_id": "persisted-flow-session",
                    "target_kc_ids": ["KC-1"],
                    "target_lo_ids": ["LO-1"],
                },
            )
            assert observe_response.status_code == 200

        generate_response = client_one.post(
            "/api/problems/generate",
            json={
                "student_id": str(student_id),
                "learning_session_id": "persisted-flow-session",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
                "curriculum_context": ["Equivalent fractions"],
            },
        )

        assert generate_response.status_code == 200
        generation_id = generate_response.json()["generation_id"]

    with TestClient(app_two) as client_two:
        content_response = client_two.get(f"/api/content/{generation_id}")
        flow_response = client_two.get(f"/api/learners/{student_id}/flow")

    assert content_response.status_code == 200
    assert flow_response.status_code == 200

    content_payload = content_response.json()
    flow_payload = flow_response.json()
    assert content_payload["workflow_summary"]["progression_action"] == "hold_target"
    assert content_payload["workflow_summary"]["next_step"]["content_type"] == "practice_problem"
    assert flow_payload["progression_action"] == "hold_target"
    assert flow_payload["progression_source"] == "workflow_summary"
    assert flow_payload["next_step_source"] == "workflow_summary"
    assert flow_payload["next_step"]["content_type"] == "practice_problem"
    assert flow_payload["next_step"]["target_kc_ids"] == ["KC-1"]
    assert flow_payload["continue_action"]["kind"] == "generate_follow_up"


def test_learner_workspace_returns_active_remediation_session_and_content(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify numerator and denominator"),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            name="Generate equivalent fractions",
            common_misconceptions=[
                {
                    "misconception_id": "fraction-whole-number-bias",
                    "label": "Treats fraction parts like unrelated whole numbers",
                    "description": "The learner compares numerator and denominator separately instead of the whole amount.",
                    "trigger_terms": ["different amounts", "numerator", "denominator", "whole number"],
                    "prerequisite_kc_ids": ["KC-1"],
                    "remediation_hint": "Use one visual model to compare the total amount before naming the parts.",
                }
            ],
        ),
    )

    trigger_response = client.post(
        "/api/remedial/trigger",
        json={
            "student_id": str(student_id),
            "target_kc_id": "KC-2",
            "misconception_description": "The learner compares numerator and denominator separately like whole numbers.",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    workspace_response = client.get(f"/api/learners/{student_id}/workspace")

    assert trigger_response.status_code == 200
    assert workspace_response.status_code == 200

    generation_id = trigger_response.json()["generation_id"]
    remediation_session_id = trigger_response.json()["request_context"]["remediation_session_id"]
    payload = workspace_response.json()
    assert payload["active_artifact"]["kind"] == "remediation_session"
    assert payload["active_artifact"]["resource_id"] == remediation_session_id
    assert payload["active_artifact"]["generation_id"] == generation_id
    assert payload["remediation_session"]["session_id"] == remediation_session_id
    assert payload["generated_content"]["generation_id"] == generation_id
    assert payload["generated_content"]["workflow_summary"]["flow_type"] == "remediation"
    assert payload["continue_action"]["kind"] == "advance_remediation"


def test_learner_workspace_preserves_continue_action_for_remediation_after_restart(app_settings):
    student_id = uuid4()
    app_one = create_app(app_settings)
    app_two = create_app(app_settings)

    with TestClient(app_one) as client_one:
        client_one.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
        client_one.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
        client_one.put(
            "/api/knowledge-components/KC-1",
            json=build_knowledge_component("KC-1", name="Identify numerator and denominator"),
        )
        client_one.put(
            "/api/knowledge-components/KC-2",
            json=build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
            ),
        )
        trigger_response = client_one.post(
            "/api/remedial/trigger",
            json={
                "student_id": str(student_id),
                "target_kc_id": "KC-2",
                "misconception_description": "The learner compares numerator and denominator separately like whole numbers.",
                "curriculum_context": ["Equivalent fractions"],
            },
        )

        assert trigger_response.status_code == 200

    with TestClient(app_two) as client_two:
        workspace_response = client_two.get(f"/api/learners/{student_id}/workspace")

    assert workspace_response.status_code == 200
    payload = workspace_response.json()
    assert payload["continue_action"]["kind"] == "advance_remediation"
    assert payload["continue_action"]["endpoint"].endswith("/advance")


def test_profile_endpoint_returns_extended_profile_metadata(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))

    response = client.get(f"/api/learners/{student_id}/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_metadata"]["student_id"] == str(student_id)
    assert payload["profile_metadata"]["version"] == "2.0"
    assert payload["profile_metadata"]["completeness_score"] > 0.5
    assert payload["affective_state"]["frustration"] == "high"
    assert "working_memory" in payload["cognitive_traits"]


def test_curriculum_resource_round_trip(client):
    resource = build_curriculum_resource()

    put_response = client.put("/api/curriculum/resources/CURR-1", json=resource)
    list_response = client.get("/api/curriculum/resources")

    assert put_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()[0]["resource_id"] == "CURR-1"


def test_profile_persists_across_app_instances(app_settings):
    student_id = uuid4()
    app_one = create_app(app_settings)
    app_two = create_app(app_settings)

    with TestClient(app_one) as client_one:
        response = client_one.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
        assert response.status_code == 200

    with TestClient(app_two) as client_two:
        response = client_two.get(f"/api/learners/{student_id}/profile")
        assert response.status_code == 200
        assert response.json()["profile_metadata"]["student_id"] == str(student_id)
