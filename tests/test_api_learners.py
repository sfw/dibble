from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app

from tests.support import (
    assert_machine_readable_error,
    build_curriculum_resource,
    build_knowledge_component,
    build_profile,
)


EXPECTED_CONTINUE_ACTION_KEYS = {
    "kind",
    "display_label",
    "method",
    "endpoint",
    "resource_id",
    "generation_id",
    "learning_session_id",
    "content_type",
    "target_stage",
    "target_kc_ids",
    "request_payload",
    "rationale",
}


def assert_continue_action_contract(
    payload: dict[str, object],
    *,
    expected_kind: str | None = None,
    expected_endpoint: str | None = None,
) -> None:
    assert set(payload.keys()) == EXPECTED_CONTINUE_ACTION_KEYS
    assert payload["kind"] in {"idle", "generate_follow_up", "advance_remediation", "continue_socratic"}
    assert payload["display_label"] is None or isinstance(payload["display_label"], str)
    if expected_kind is not None:
        assert payload["kind"] == expected_kind
    if payload["kind"] == "idle":
        assert payload["method"] is None
        assert payload["endpoint"] is None
        assert payload["request_payload"] == {}
    else:
        assert payload["method"] == "POST"
        assert isinstance(payload["endpoint"], str) and payload["endpoint"]
        assert isinstance(payload["request_payload"], dict)
    if expected_endpoint is not None:
        assert payload["endpoint"] == expected_endpoint


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
    assert summary_response.json()["curriculum_progression"]["status"] == "no_curriculum_map"
    assert profile_response.json()["profile_metadata"]["student_id"] == str(student_id)
    assert str(student_id) in list_response.json()


def test_learner_workspace_returns_machine_readable_not_found_error(client, student_id):
    response = client.get(f"/api/learners/{student_id}/workspace")

    assert_machine_readable_error(
        response,
        status_code=404,
        code="learner_profile_not_found",
        detail="Learner profile not found.",
    )


def test_learner_progression_returns_machine_readable_not_found_error(client, student_id):
    response = client.get(f"/api/learners/{student_id}/progression")

    assert_machine_readable_error(
        response,
        status_code=404,
        code="learner_profile_not_found",
        detail="Learner profile not found.",
    )


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


def test_learner_progression_endpoint_exposes_backend_owned_curriculum_focus(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(
            student_id,
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.86, "KC-2": 0.42, "KC-3": 0.15},
        ),
    )
    client.put(
        "/api/curriculum/resources/CURR-1",
        json=build_curriculum_resource(
            resource_id="CURR-1",
            title="Fraction Visual Foundations",
            knowledge_component_ids=["KC-1"],
        ),
    )
    client.put(
        "/api/curriculum/resources/CURR-2",
        json=build_curriculum_resource(
            resource_id="CURR-2",
            title="Equivalent Fraction Practice",
            knowledge_component_ids=["KC-2"],
        ),
    )
    client.put(
        "/api/curriculum/resources/CURR-3",
        json=build_curriculum_resource(
            resource_id="CURR-3",
            title="Compare Fraction Families",
            knowledge_component_ids=["KC-3"],
            learning_objective_ids=["LO-2"],
        ),
    )
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify fraction equivalence"),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            parent_lo_id="LO-1",
            name="Generate equivalent fractions",
        ),
    )
    client.put(
        "/api/knowledge-components/KC-3",
        json=build_knowledge_component(
            "KC-3",
            prerequisite_kc_ids=["KC-2"],
            parent_lo_id="LO-2",
            name="Compare fraction families",
        ),
    )

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "progression-session-1",
            "target_kc_ids": ["KC-2"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    progression_response = client.get(f"/api/learners/{student_id}/progression")
    summary_response = client.get(f"/api/learners/{student_id}/summary")

    assert generate_response.status_code == 200
    assert progression_response.status_code == 200
    assert summary_response.status_code == 200

    progression_payload = progression_response.json()
    summary_payload = summary_response.json()
    assert progression_payload["status"] == "active_curriculum_focus"
    assert progression_payload["flow_type"] == "lesson"
    assert progression_payload["current_stage"] == "repair"
    assert progression_payload["stage_display_label"] == "Building foundations"
    assert progression_payload["progression_action"] == "rebuild_prerequisite_first"
    assert progression_payload["active_target_kc_ids"] == ["KC-1"]
    assert progression_payload["resource_count"] == 3
    assert progression_payload["mastered_resource_count"] == 0
    assert progression_payload["active_resource_count"] == 1
    assert progression_payload["blocked_resource_count"] == 1
    assert progression_payload["current_resource"]["resource_id"] == "CURR-1"
    assert progression_payload["current_resource"]["state"] == "active"
    assert progression_payload["current_resource"]["current_flow_aligned"] is True
    assert progression_payload["rationale"] == summary_payload["current_flow"]["rationale"]
    assert progression_payload["current_resource"]["rationale"] == summary_payload["current_flow"]["rationale"]
    assert progression_payload["next_resource"]["resource_id"] == "CURR-2"
    assert progression_payload["next_resource"]["state"] == "ready"
    assert "current learner flow releases the active target" in progression_payload["next_resource"]["rationale"]
    assert progression_payload["blocked_resources"][0]["resource_id"] == "CURR-3"
    assert progression_payload["blocked_resources"][0]["blocked_prerequisite_kc_ids"] == ["KC-2"]
    assert "stays blocked instead of becoming the next curriculum focus" in progression_payload["blocked_resources"][0][
        "rationale"
    ]
    assert summary_payload["curriculum_progression"] == progression_payload


def test_continue_action_contract_stays_consistent_across_lesson_surfaces(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "continue-contract-lesson-session",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    flow_response = client.get(f"/api/learners/{student_id}/flow")
    summary_response = client.get(f"/api/learners/{student_id}/summary")
    workspace_response = client.get(f"/api/learners/{student_id}/workspace")
    history_response = client.get(f"/api/learners/{student_id}/history/generations")
    intervention_response = client.get(f"/api/learners/{student_id}/intervention-action")

    assert generate_response.status_code == 200
    assert flow_response.status_code == 200
    assert summary_response.status_code == 200
    assert workspace_response.status_code == 200
    assert history_response.status_code == 200
    assert intervention_response.status_code == 200

    generation_payload = generate_response.json()
    flow_payload = flow_response.json()
    summary_payload = summary_response.json()
    workspace_payload = workspace_response.json()
    history_payload = history_response.json()
    intervention_payload = intervention_response.json()

    lesson_continue_action = generation_payload["workflow_summary"]["continue_action"]
    history_entry = next(entry for entry in history_payload if entry["generation_id"] == generation_payload["generation_id"])

    assert_continue_action_contract(
        lesson_continue_action,
        expected_kind="generate_follow_up",
        expected_endpoint="/api/content/generate",
    )
    assert lesson_continue_action["display_label"] == "Continue your lesson"
    assert flow_payload["continue_action"] == lesson_continue_action
    assert summary_payload["current_flow"]["continue_action"] == lesson_continue_action
    assert workspace_payload["continue_action"] == lesson_continue_action
    assert workspace_payload["generated_content"]["workflow_summary"]["continue_action"] == lesson_continue_action
    assert history_entry["continue_action"] == lesson_continue_action
    assert generation_payload["workflow_summary"]["rationale"] == generation_payload["workflow_summary"]["next_step"]["rationale"]
    assert flow_payload["rationale"] == generation_payload["workflow_summary"]["rationale"]
    assert summary_payload["current_flow"]["rationale"] == generation_payload["workflow_summary"]["rationale"]
    assert workspace_payload["summary"]["current_flow"]["rationale"] == generation_payload["workflow_summary"]["rationale"]
    assert history_entry["rationale"] == generation_payload["workflow_summary"]["rationale"]
    assert lesson_continue_action["rationale"] == generation_payload["workflow_summary"]["rationale"]
    assert intervention_payload["proposed_action"] == lesson_continue_action
    assert intervention_payload["available_options"][0]["option_id"] == "recommended"
    assert intervention_payload["available_options"][0]["continue_action"] == lesson_continue_action
    assert intervention_payload["allowed_decisions"] == ["approve", "select_option", "defer", "escalate_human"]


def test_learner_progression_prefers_deferred_target_resource_over_unrelated_ready_resource(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put(
        "/api/curriculum/resources/CURR-0",
        json=build_curriculum_resource(
            resource_id="CURR-0",
            title="Unrelated Fraction Extension",
            knowledge_component_ids=["KC-9"],
            learning_objective_ids=["LO-9"],
        ),
    )
    client.put(
        "/api/curriculum/resources/CURR-1",
        json=build_curriculum_resource(
            resource_id="CURR-1",
            title="Equivalent Fraction Foundations",
            knowledge_component_ids=["KC-1"],
        ),
    )
    client.put(
        "/api/curriculum/resources/CURR-2",
        json=build_curriculum_resource(
            resource_id="CURR-2",
            title="Equivalent Fraction Practice",
            knowledge_component_ids=["KC-2"],
        ),
    )
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify fraction equivalence"),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            parent_lo_id="LO-1",
            name="Generate equivalent fractions",
        ),
    )
    client.put(
        "/api/knowledge-components/KC-9",
        json=build_knowledge_component(
            "KC-9",
            parent_lo_id="LO-9",
            name="Recognize unrelated fraction patterns",
        ),
    )

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "progression-deferred-target-session",
            "target_kc_ids": ["KC-2"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    flow_response = client.get(f"/api/learners/{student_id}/flow")
    summary_response = client.get(f"/api/learners/{student_id}/summary")
    progression_response = client.get(f"/api/learners/{student_id}/progression")

    assert generate_response.status_code == 200
    assert flow_response.status_code == 200
    assert summary_response.status_code == 200
    assert progression_response.status_code == 200

    flow_payload = flow_response.json()
    summary_payload = summary_response.json()
    progression_payload = progression_response.json()
    assert flow_payload["deferred_target_kc_ids"] == ["KC-2"]
    assert flow_payload["transfer_target_kc_ids"] == ["KC-2"]
    assert summary_payload["current_flow"]["deferred_target_kc_ids"] == ["KC-2"]
    assert progression_payload["status"] == "active_curriculum_focus"
    assert progression_payload["current_resource"]["resource_id"] == "CURR-1"
    assert progression_payload["next_resource"]["resource_id"] == "CURR-2"
    assert progression_payload["ready_resources"][0]["resource_id"] == "CURR-2"
    assert progression_payload["ready_resources"][1]["resource_id"] == "CURR-0"
    assert "deferred return target" in progression_payload["next_resource"]["rationale"]
    assert "releases the active target" in progression_payload["next_resource"]["rationale"]


def test_learner_progression_blocked_rationale_names_prerequisite_scores_and_blocking_resource(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, kc_mastery={"KC-1": 0.2, "KC-2": 0.12}),
    )
    client.put(
        "/api/curriculum/resources/CURR-1",
        json=build_curriculum_resource(
            resource_id="CURR-1",
            title="Equivalent Fraction Foundations",
            knowledge_component_ids=["KC-1"],
        ),
    )
    client.put(
        "/api/curriculum/resources/CURR-2",
        json=build_curriculum_resource(
            resource_id="CURR-2",
            title="Equivalent Fraction Practice",
            knowledge_component_ids=["KC-2"],
        ),
    )
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Recognize equivalent fractions"),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            parent_lo_id="LO-1",
            name="Generate equivalent fractions",
        ),
    )

    progression_response = client.get(f"/api/learners/{student_id}/progression")

    assert progression_response.status_code == 200
    blocked_resource = progression_response.json()["blocked_resources"][0]
    assert blocked_resource["resource_id"] == "CURR-2"
    assert "Recognize equivalent fractions (0.20/0.65)" in blocked_resource["rationale"]
    assert "Equivalent Fraction Foundations" in blocked_resource["rationale"]


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
    assert flow_payload["rationale"] == trigger_response.json()["workflow_summary"]["rationale"]
    assert "Current repair step:" in flow_payload["rationale"]
    assert summary_payload["current_flow"]["flow_type"] == "remediation"
    assert summary_payload["current_flow"]["current_phase"] == "repair"
    assert summary_payload["current_flow"]["continue_action"]["kind"] == "advance_remediation"
    assert summary_payload["current_flow"]["rationale"] == flow_payload["rationale"]


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
    remediation_session_response = client.get(
        f"/api/remedial/sessions/{remediation_response.json()['request_context']['remediation_session_id']}"
    )

    assert lesson_response.status_code == 200
    assert socratic_response.status_code == 200
    assert remediation_response.status_code == 200
    assert generations_response.status_code == 200
    assert socratic_history_response.status_code == 200
    assert remediation_history_response.status_code == 200
    assert remediation_session_response.status_code == 200

    generations_payload = generations_response.json()
    socratic_history_payload = socratic_history_response.json()
    remediation_history_payload = remediation_history_response.json()
    remediation_session_payload = remediation_session_response.json()
    lesson_history_entry = next(
        entry for entry in generations_payload if entry["generation_id"] == lesson_response.json()["generation_id"]
    )
    remediation_generation_entry = next(
        entry for entry in generations_payload if entry["generation_id"] == remediation_response.json()["generation_id"]
    )

    assert generations_payload[0]["flow_type"] == "remediation"
    assert generations_payload[0]["generation_id"] == remediation_response.json()["generation_id"]
    assert generations_payload[0]["continue_action"]["kind"] == "advance_remediation"
    assert generations_payload[0]["content_type"] == "remedial_micro_module"
    assert generations_payload[0]["intervention_type"] is not None
    assert any(entry["generation_id"] == lesson_response.json()["generation_id"] for entry in generations_payload)
    assert_continue_action_contract(lesson_history_entry["continue_action"])
    assert lesson_history_entry["continue_action"] == lesson_response.json()["workflow_summary"]["continue_action"]
    assert_continue_action_contract(remediation_generation_entry["continue_action"])

    assert socratic_history_payload[0]["session_id"] == socratic_response.json()["session_id"]
    assert socratic_history_payload[0]["status"] == "ready_for_follow_up"
    assert socratic_history_payload[0]["latest_steering_action"] == "verify_transfer"
    assert socratic_history_payload[0]["continue_action"]["kind"] == "generate_follow_up"
    assert_continue_action_contract(socratic_history_payload[0]["continue_action"])
    assert socratic_history_payload[0]["rationale"] == socratic_response.json()["summary"]["rationale"]
    assert socratic_history_payload[0]["rationale"] == socratic_response.json()["summary"]["next_step"]["rationale"]
    assert "testing transfer instead of adding another support step" in socratic_history_payload[0]["rationale"]
    assert socratic_history_payload[0]["continue_action"] == socratic_response.json()["summary"]["continue_action"]

    assert remediation_history_payload[0]["session_id"] == remediation_response.json()["request_context"]["remediation_session_id"]
    assert remediation_history_payload[0]["target_kc_id"] == "KC-2"
    assert remediation_history_payload[0]["status"] == "in_progress"
    assert remediation_history_payload[0]["current_phase"] == "repair"
    assert remediation_history_payload[0]["continue_action"]["kind"] == "advance_remediation"
    assert_continue_action_contract(remediation_history_payload[0]["continue_action"])
    assert remediation_history_payload[0]["continue_action"] == remediation_session_payload["summary"]["continue_action"]
    assert remediation_generation_entry["continue_action"]["kind"] == remediation_session_payload["summary"]["continue_action"]["kind"]
    assert remediation_generation_entry["continue_action"]["method"] == remediation_session_payload["summary"]["continue_action"]["method"]
    assert remediation_generation_entry["continue_action"]["endpoint"] == remediation_session_payload["summary"]["continue_action"]["endpoint"]
    assert remediation_generation_entry["continue_action"]["content_type"] == remediation_session_payload["summary"]["continue_action"]["content_type"]
    assert remediation_generation_entry["continue_action"]["target_stage"] == remediation_session_payload["summary"]["continue_action"]["target_stage"]
    assert remediation_generation_entry["continue_action"]["target_kc_ids"] == remediation_session_payload["summary"]["continue_action"]["target_kc_ids"]


def test_socratic_rationale_stays_aligned_across_flow_workspace_history_and_intervention(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    socratic_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "learning_session_id": "socratic-parity-session",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "learner_response": "Equivalent fractions are the same amount because 1/2 and 2/4 cover equal space on the model.",
            "learner_confidence": 0.72,
        },
    )
    flow_response = client.get(f"/api/learners/{student_id}/flow")
    summary_response = client.get(f"/api/learners/{student_id}/summary")
    workspace_response = client.get(f"/api/learners/{student_id}/workspace")
    history_response = client.get(f"/api/learners/{student_id}/history/socratic-sessions")
    intervention_response = client.get(f"/api/learners/{student_id}/intervention-action")

    assert socratic_response.status_code == 200
    assert flow_response.status_code == 200
    assert summary_response.status_code == 200
    assert workspace_response.status_code == 200
    assert history_response.status_code == 200
    assert intervention_response.status_code == 200

    socratic_payload = socratic_response.json()
    flow_payload = flow_response.json()
    summary_payload = summary_response.json()
    workspace_payload = workspace_response.json()
    history_payload = history_response.json()
    intervention_payload = intervention_response.json()

    canonical_rationale = socratic_payload["summary"]["rationale"]

    assert socratic_payload["summary"]["rationale"] == socratic_payload["summary"]["next_step"]["rationale"]
    assert flow_payload["flow_type"] == "socratic_assessment"
    assert flow_payload["rationale"] == canonical_rationale
    assert summary_payload["current_flow"]["rationale"] == canonical_rationale
    assert workspace_payload["summary"]["current_flow"]["rationale"] == canonical_rationale
    assert workspace_payload["active_artifact"]["rationale"] == canonical_rationale
    assert workspace_payload["socratic_session"]["summary"]["rationale"] == canonical_rationale
    assert history_payload[0]["rationale"] == canonical_rationale
    assert intervention_payload["rationale"] == canonical_rationale
    assert intervention_payload["proposed_action"]["rationale"] == canonical_rationale
    assert intervention_payload["available_options"][0]["rationale"] == canonical_rationale
    assert intervention_payload["available_options"][0]["continue_action"] == socratic_payload["summary"]["continue_action"]
    assert "testing transfer instead of adding another support step" in canonical_rationale


def test_learner_history_endpoints_return_machine_readable_not_found_error(client, student_id):
    generations_response = client.get(f"/api/learners/{student_id}/history/generations")
    socratic_history_response = client.get(f"/api/learners/{student_id}/history/socratic-sessions")
    remediation_history_response = client.get(f"/api/learners/{student_id}/history/remediation-sessions")

    assert_machine_readable_error(
        generations_response,
        status_code=404,
        code="learner_profile_not_found",
        detail="Learner profile not found.",
    )
    assert_machine_readable_error(
        socratic_history_response,
        status_code=404,
        code="learner_profile_not_found",
        detail="Learner profile not found.",
    )
    assert_machine_readable_error(
        remediation_history_response,
        status_code=404,
        code="learner_profile_not_found",
        detail="Learner profile not found.",
    )


def test_held_remediation_generation_history_stays_aligned_with_session_summary(client, student_id):
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
                    "trigger_terms": ["numerator", "denominator", "whole number", "fraction"],
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
            "misconception_description": "The learner compares numerator and denominator like whole numbers.",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    remediation_session_id = trigger_response.json()["request_context"]["remediation_session_id"]

    repair_response = client.post(
        f"/api/remedial/sessions/{remediation_session_id}/advance",
        json={},
    )
    assert repair_response.status_code == 200

    observe_response = client.post(
        f"/api/learners/{student_id}/observations",
        json={
            "response_time_ms": 32000,
            "hints_used": 4,
            "error_count": 3,
            "pause_count": 3,
            "modality_switches": 0,
            "completed": False,
            "confidence": 0.2,
            "task_type": "remediation",
            "support_level": "high",
            "expected_duration_ms": 18000,
            "learning_session_id": remediation_session_id,
            "generation_id": repair_response.json()["content"]["generation_id"],
            "observed_content_type": "remedial_micro_module",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
        },
    )
    assert observe_response.status_code == 200

    held_response = client.post(
        f"/api/remedial/sessions/{remediation_session_id}/advance",
        json={},
    )
    generations_response = client.get(f"/api/learners/{student_id}/history/generations")
    remediation_session_response = client.get(f"/api/remedial/sessions/{remediation_session_id}")
    workspace_response = client.get(f"/api/learners/{student_id}/workspace")

    assert held_response.status_code == 200
    assert generations_response.status_code == 200
    assert remediation_session_response.status_code == 200
    assert workspace_response.status_code == 200

    held_generation_id = held_response.json()["content"]["generation_id"]
    remediation_generation_entry = next(
        entry for entry in generations_response.json() if entry["generation_id"] == held_generation_id
    )
    session_summary = remediation_session_response.json()["summary"]
    workspace_payload = workspace_response.json()

    assert remediation_generation_entry["target_stage"] == "repair"
    assert remediation_generation_entry["next_step"] == session_summary["next_step"]
    assert remediation_generation_entry["continue_action"]["kind"] == session_summary["continue_action"]["kind"]
    assert remediation_generation_entry["continue_action"]["target_stage"] == session_summary["continue_action"]["target_stage"]
    assert remediation_generation_entry["continue_action"]["target_kc_ids"] == session_summary["continue_action"]["target_kc_ids"]
    assert remediation_generation_entry["rationale"] == session_summary["next_step"]["rationale"]
    assert remediation_generation_entry["continue_action"]["rationale"] == session_summary["continue_action"]["rationale"]
    assert workspace_payload["generated_content"]["workflow_summary"]["next_step"] == session_summary["next_step"]
    assert workspace_payload["continue_action"]["target_stage"] == session_summary["continue_action"]["target_stage"]
    assert workspace_payload["continue_action"]["target_kc_ids"] == session_summary["continue_action"]["target_kc_ids"]
    assert workspace_payload["generated_content"]["workflow_summary"]["rationale"] == session_summary["next_step"]["rationale"]
    assert workspace_payload["summary"]["current_flow"]["rationale"] == session_summary["next_step"]["rationale"]
    assert workspace_payload["continue_action"]["rationale"] == session_summary["continue_action"]["rationale"]


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
    assert contract_payload["allowed_decisions"] == ["approve", "select_option", "defer", "escalate_human"]
    assert contract_payload["proposed_action"]["kind"] == "generate_follow_up"
    assert contract_payload["proposed_action"]["endpoint"] == "/api/content/generate"
    assert contract_payload["available_options"][0]["option_id"] == "recommended"
    assert contract_payload["available_options"][0]["is_recommended"] is True
    assert {option["option_id"] for option in contract_payload["available_options"]} >= {
        "recommended",
        "worked_example_support_reset",
        "practice_problem_same_target",
    }

    assert approve_payload["latest_decision"]["decision"] == "approve"
    assert approve_payload["latest_decision"]["status"] == "approved"
    assert approve_payload["latest_decision"]["selected_option_id"] == "recommended"
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
    assert decision_event["payload"]["selected_option_id"] == "recommended"
    assert decision_event["payload"]["execution_action"]["kind"] == "generate_follow_up"


def test_teacher_intervention_action_contract_supports_backend_owned_option_selection(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "teacher-action-select-option",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    contract_response = client.get(f"/api/learners/{student_id}/intervention-action")
    select_response = client.post(
        f"/api/learners/{student_id}/intervention-action",
        json={
            "decision": "select_option",
            "option_id": "worked_example_support_reset",
            "note": "Reset with a modeled example first.",
        },
    )

    assert contract_response.status_code == 200
    assert select_response.status_code == 200

    contract_payload = contract_response.json()
    select_payload = select_response.json()
    selected_option = next(
        option for option in contract_payload["available_options"] if option["option_id"] == "worked_example_support_reset"
    )

    assert select_payload["latest_decision"]["decision"] == "select_option"
    assert select_payload["latest_decision"]["status"] == "option_selected"
    assert select_payload["latest_decision"]["selected_option_id"] == "worked_example_support_reset"
    assert select_payload["latest_decision"]["execution_action"] == selected_option["continue_action"]
    assert select_payload["latest_decision"]["execution_action"]["content_type"] == "worked_example"
    assert select_payload["latest_decision"]["execution_action"]["request_payload"]["requested_content_type"] == (
        "worked_example"
    )
    assert select_payload["latest_decision"]["execution_action"]["request_payload"]["intent"] == "explanation"


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
    assert_machine_readable_error(
        unavailable_response,
        status_code=409,
        code="teacher_intervention_unavailable",
        detail="No teacher-approvable intervention is available.",
    )

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
    missing_option_response = client.post(
        f"/api/learners/{student_id}/intervention-action",
        json={"decision": "select_option"},
    )
    unknown_option_response = client.post(
        f"/api/learners/{student_id}/intervention-action",
        json={"decision": "select_option", "option_id": "not-a-real-option"},
    )

    assert_machine_readable_error(
        invalid_response,
        status_code=400,
        code="teacher_intervention_invalid_decision",
        detail="Unsupported teacher intervention decision.",
    )
    assert_machine_readable_error(
        missing_option_response,
        status_code=400,
        code="teacher_intervention_invalid_decision",
        detail="Selecting an intervention option requires option_id.",
    )
    assert_machine_readable_error(
        unknown_option_response,
        status_code=400,
        code="teacher_intervention_option_not_found",
        detail="Teacher intervention option is not available.",
    )


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
    assert payload["affective_support"]["kind"] == "break_suggestion"
    assert payload["affective_support"]["title"] == "It's okay to take a break"
    assert payload["remediation_session"]["session_id"] == remediation_session_id
    assert payload["generated_content"]["generation_id"] == generation_id
    assert payload["generated_content"]["workflow_summary"]["flow_type"] == "remediation"
    assert payload["continue_action"]["kind"] == "advance_remediation"


def test_learner_workspace_returns_engagement_encouragement_when_frustration_is_low(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", engagement="high", total_load=0.2),
    )

    workspace_response = client.get(f"/api/learners/{student_id}/workspace")

    assert workspace_response.status_code == 200
    payload = workspace_response.json()
    assert payload["affective_support"]["kind"] == "encouragement"
    assert payload["affective_support"]["title"] == "You're on a roll!"


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


def test_learner_workspace_keeps_completed_remediation_follow_up_aligned_with_latest_generation(client, student_id):
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
                    "trigger_terms": ["numerator", "denominator", "whole number", "fraction"],
                    "prerequisite_kc_ids": ["KC-1"],
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
    remediation_session_id = trigger_response.json()["request_context"]["remediation_session_id"]

    repair_response = client.post(f"/api/remedial/sessions/{remediation_session_id}/advance", json={})
    return_response = client.post(f"/api/remedial/sessions/{remediation_session_id}/advance", json={})
    workspace_response = client.get(f"/api/learners/{student_id}/workspace")

    assert trigger_response.status_code == 200
    assert repair_response.status_code == 200
    assert return_response.status_code == 200
    assert workspace_response.status_code == 200

    payload = workspace_response.json()
    continue_action = payload["continue_action"]
    workflow_continue_action = payload["generated_content"]["workflow_summary"]["continue_action"]

    assert payload["active_artifact"]["kind"] == "remediation_session"
    assert continue_action == workflow_continue_action
    assert continue_action["kind"] == "generate_follow_up"
    assert continue_action["generation_id"] == return_response.json()["content"]["generation_id"]
    assert continue_action["learning_session_id"] == remediation_session_id
    assert continue_action["request_payload"]["learning_session_id"] == remediation_session_id
    assert continue_action["request_payload"]["source_generation_id"] == return_response.json()["content"]["generation_id"]


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
