from fastapi.testclient import TestClient

from tests.api_support import parse_sse_events
from dibble.app import create_app
from dibble.config import Settings
from tests.support import build_curriculum_resource, build_knowledge_component, build_profile


def test_generation_uses_grounding_and_step_back_route(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "remediation",
            "learner_prompt": "Use a calm tone.",
            "curriculum_context": ["Grade 5 fractions", "Equivalent fractions"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"]["route"]["intervention_type"] == "step_back"
    assert payload["response"]["route"]["delivery_mode"] == "generated"
    assert payload["response"]["grounding"][0]["resource_id"] == "CURR-1"
    assert payload["response"]["validation_issues"] == []
    assert payload["generation_id"] is not None
    assert payload["quality"]["validation_passed"] is True
    assert payload["quality"]["cache_hit"] is False
    assert payload["quality"]["prompt_template_name"] is not None
    assert payload["quality"]["prompt_template_version"] == "1.0"
    assert payload["quality"]["prompt_template_variant"] == "baseline"


def test_generation_endpoint_returns_generated_content_and_cache_hit(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    request_payload = {
        "student_id": str(student_id),
        "target_kc_ids": ["KC-1"],
        "intent": "remediation",
        "curriculum_context": ["Equivalent fractions"],
    }

    first_response = client.post("/api/content/generate", json=request_payload)
    second_response = client.post("/api/content/generate", json=request_payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()
    assert first_payload["quality"]["cache_hit"] is False
    assert second_payload["quality"]["cache_hit"] is True
    assert first_payload["generation_id"] == second_payload["generation_id"]
    assert second_payload["response"]["generation_metadata"]["cache_hit"] is True


def test_generation_cache_ignores_learning_session_id(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    first_response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-a",
            "target_kc_ids": ["KC-1"],
            "intent": "remediation",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    second_response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-b",
            "target_kc_ids": ["KC-1"],
            "intent": "remediation",
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()
    assert first_payload["generation_id"] == second_payload["generation_id"]
    assert second_payload["quality"]["cache_hit"] is True
    assert first_payload["request_context"]["learning_session_id"] == "session-a"
    assert second_payload["request_context"]["learning_session_id"] == "session-b"


def test_content_warm_endpoint_primes_generation_cache(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    request_payload = {
        "student_id": str(student_id),
        "target_kc_ids": ["KC-1"],
        "intent": "remediation",
        "curriculum_context": ["Equivalent fractions"],
    }

    warm_response = client.post("/api/content/warm", json={"requests": [request_payload]})
    generated_response = client.post("/api/content/generate", json=request_payload)

    assert warm_response.status_code == 200
    assert generated_response.status_code == 200
    assert warm_response.json()["total_requests"] == 1
    assert generated_response.json()["quality"]["cache_hit"] is True


def test_generation_cache_reuses_predictive_warm_entries_for_real_requests(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    warm_response = client.post(
        "/api/content/warm",
        json={
            "requests": [
                {
                    "student_id": str(student_id),
                    "learning_session_id": "session-predictive",
                    "target_kc_ids": ["KC-1"],
                    "intent": "practice",
                    "requested_content_type": "practice_problem",
                    "curriculum_context": ["Equivalent fractions"],
                    "predictive_warm": True,
                    "warm_reason": "Test predictive reuse",
                    "source_generation_id": "gen-source",
                }
            ]
        },
    )
    generated_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-predictive",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert warm_response.status_code == 200
    assert generated_response.status_code == 200
    payload = generated_response.json()
    assert payload["quality"]["cache_hit"] is True
    assert payload["request_context"].get("is_predictive_warm") is None
    assert payload["request_context"].get("source_generation_id") is None


def test_generation_endpoint_predictively_warms_follow_up_content(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    worked_example_response = client.post(
        "/api/worked-examples/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-worked-example",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    problem_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-worked-example",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    assessment_probe_response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-worked-example",
            "target_kc_ids": ["KC-1"],
            "intent": "assessment",
            "requested_content_type": "assessment_probe",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    audit_response = client.get("/api/audit/events")

    assert worked_example_response.status_code == 200
    assert problem_response.status_code == 200
    assert assessment_probe_response.status_code == 200
    assert problem_response.json()["quality"]["cache_hit"] is True
    assert assessment_probe_response.json()["quality"]["cache_hit"] is True

    predictive_event = next(
        event
        for event in audit_response.json()
        if event["event_type"] == "content.warm.predictive"
        and event["payload"]["predicted_content_types"] == ["practice_problem", "assessment_probe"]
    )
    assert predictive_event["payload"]["source_generation_id"] == worked_example_response.json()["generation_id"]
    assert predictive_event["payload"]["predicted_request_count"] == 2
    assert predictive_event["payload"]["predicted_content_types"] == ["practice_problem", "assessment_probe"]


def test_predictive_warm_process_endpoint_drains_pending_queue(tmp_path, student_id):
    settings = Settings(
        database_path=str(tmp_path / "predictive-warm-process-api.db"),
        predictive_warm_inline_process_limit=0,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
        client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

        worked_example_response = client.post(
            "/api/worked-examples/generate",
            json={
                "student_id": str(student_id),
                "learning_session_id": "session-queued-predictive",
                "target_kc_ids": ["KC-1"],
                "curriculum_context": ["Equivalent fractions"],
            },
        )
        process_response = client.post("/api/content/warm/process", json={"limit": 10})
        problem_response = client.post(
            "/api/problems/generate",
            json={
                "student_id": str(student_id),
                "learning_session_id": "session-queued-predictive",
                "target_kc_ids": ["KC-1"],
                "curriculum_context": ["Equivalent fractions"],
            },
        )

        assert worked_example_response.status_code == 200
        assert process_response.status_code == 200
        assert problem_response.status_code == 200
        assert process_response.json()["completed_tasks"] >= 1
        assert process_response.json()["pending_tasks"] == 0
        assert problem_response.json()["quality"]["cache_hit"] is True


def test_negative_practice_generation_predictively_warms_worked_example(client, student_id, app_settings):
    from dibble.services.audit_store import SQLiteAuditStore

    audit_store = SQLiteAuditStore(app_settings.database_path)
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.45}),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.44,
            "average_run_confidence": 0.8,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "positive_run_rate": 0.0,
            "negative_run_rate": 0.75,
            "recent_average_run_outcome_score": 0.38,
            "prior_average_run_outcome_score": 0.56,
            "progress_delta": -0.18,
            "progress_signal": "declining",
        },
    )

    practice_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-negative-practice",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    worked_example_response = client.post(
        "/api/worked-examples/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-negative-practice",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    audit_response = client.get("/api/audit/events")

    assert practice_response.status_code == 200
    assert worked_example_response.status_code == 200
    assert worked_example_response.json()["quality"]["cache_hit"] is True
    predictive_event = next(
        event
        for event in audit_response.json()
        if event["event_type"] == "content.warm.predictive"
        and event["payload"]["source_generation_id"] == practice_response.json()["generation_id"]
    )
    assert predictive_event["payload"]["predicted_content_types"] == ["worked_example"]


def test_remedial_trigger_returns_remedial_generated_content(client, student_id):
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

    response = client.post(
        "/api/remedial/trigger",
        json={
            "student_id": str(student_id),
            "target_kc_id": "KC-2",
            "misconception_description": "The learner thinks 1/2 and 2/4 are different amounts.",
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    signals = payload["request_context"]["misconception_signals"]
    prerequisite_signal = next(signal for signal in signals if signal["category"] == "prerequisite_gap")
    catalog_signal = next(signal for signal in signals if signal.get("misconception_id") == "fraction-whole-number-bias")
    assert payload["content_type"] == "remedial_micro_module"
    assert payload["response"]["route"]["intervention_type"] == "step_back"
    assert payload["quality"]["validation_passed"] is True
    assert payload["request_context"]["target_kc_ids"] == ["KC-1", "KC-2"]
    assert payload["request_context"]["prerequisite_kc_ids"] == ["KC-1"]
    assert payload["request_context"]["remediation_session_id"] is not None
    assert prerequisite_signal["kc_id"] == "KC-1"
    assert catalog_signal["source"] == "catalog"
    assert "prerequisite knowledge components" in payload["request_context"]["remediation_rationale"]
    assert payload["request_context"]["remediation_blueprint"]["trigger"] == "misconception_detected"
    assert payload["request_context"]["remediation_blueprint"]["primary_misconception_id"] == "fraction-whole-number-bias"
    assert [step["phase"] for step in payload["request_context"]["remediation_blueprint"]["steps"]] == [
        "step_back",
        "repair",
        "return",
    ]
    assert payload["request_context"]["remediation_workflow"]["executed_phase"] == "step_back"
    assert payload["request_context"]["remediation_workflow"]["next_phase"] == "repair"
    assert payload["request_context"]["remediation_workflow"]["completed_step_count"] == 1

    audit_response = client.get("/api/audit/events")
    assert audit_response.status_code == 200
    remediation_event = next(
        event for event in audit_response.json() if event["event_type"] == "remediation.trigger"
    )
    assert remediation_event["payload"]["remediation_session_id"] == payload["request_context"]["remediation_session_id"]
    assert remediation_event["payload"]["misconception_signal_count"] >= 1
    assert remediation_event["payload"]["remediation_blueprint"]["primary_misconception_id"] == (
        "fraction-whole-number-bias"
    )


def test_remedial_trigger_records_and_reuses_misconception_profiles(client, student_id):
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

    first_response = client.post(
        "/api/remedial/trigger",
        json={
            "student_id": str(student_id),
            "target_kc_id": "KC-2",
            "misconception_description": "The learner compares numerator and denominator like whole numbers.",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    second_response = client.post(
        "/api/remedial/trigger",
        json={
            "student_id": str(student_id),
            "target_kc_id": "KC-2",
            "misconception_description": "The learner is still focused on numerator counts instead of the whole fraction amount.",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    audit_response = client.get("/api/audit/events")

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    second_signals = second_response.json()["request_context"]["misconception_signals"]
    assert any(signal["source"] == "profile" for signal in second_signals)
    profile_event = next(
        event for event in audit_response.json() if event["event_type"] == "learning.misconception.profile"
    )
    assert profile_event["payload"]["target_kc_id"] == "KC-2"
    assert profile_event["payload"]["matched_signal_count"] >= 1


def test_remediation_session_endpoints_advance_multi_step_workflow(client, student_id):
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
    assert trigger_response.status_code == 200

    remediation_session_id = trigger_response.json()["request_context"]["remediation_session_id"]
    session_response = client.get(f"/api/remedial/sessions/{remediation_session_id}")
    assert session_response.status_code == 200
    session_payload = session_response.json()
    assert session_payload["current_step_index"] == 1
    assert [step["status"] for step in session_payload["steps"]] == ["completed", "active", "pending"]

    repair_response = client.post(
        f"/api/remedial/sessions/{remediation_session_id}/advance",
        json={},
    )
    assert repair_response.status_code == 200
    repair_payload = repair_response.json()
    assert repair_payload["executed_phase"] == "repair"
    assert repair_payload["content"]["content_type"] == "remedial_micro_module"
    assert repair_payload["session"]["current_step_index"] == 2
    assert [step["status"] for step in repair_payload["session"]["steps"]] == ["completed", "completed", "active"]
    assert repair_payload["content"]["request_context"]["remediation_workflow"]["next_phase"] == "return"

    return_response = client.post(
        f"/api/remedial/sessions/{remediation_session_id}/advance",
        json={"learner_prompt": "Fade support a bit."},
    )
    assert return_response.status_code == 200
    return_payload = return_response.json()
    assert return_payload["executed_phase"] == "return"
    assert return_payload["content"]["content_type"] == "practice_problem"
    assert return_payload["session"]["current_step_index"] is None
    assert [step["status"] for step in return_payload["session"]["steps"]] == [
        "completed",
        "completed",
        "completed",
    ]
    assert return_payload["content"]["request_context"]["remediation_workflow"]["status"] == "complete"
    assert return_payload["content"]["request_context"]["remediation_workflow"]["next_phase"] is None

    completed_response = client.post(
        f"/api/remedial/sessions/{remediation_session_id}/advance",
        json={},
    )
    assert completed_response.status_code == 409


def test_explanations_and_problems_endpoints_specialize_generation(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    explanation_response = client.post(
        "/api/explanations/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    problem_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert explanation_response.status_code == 200
    assert problem_response.status_code == 200

    explanation_payload = explanation_response.json()
    problem_payload = problem_response.json()
    assert explanation_payload["content_type"] == "micro_explanation"
    assert problem_payload["content_type"] == "practice_problem"
    assert any(block["kind"] == "practice" for block in problem_payload["response"]["blocks"])


def test_generation_endpoint_auto_selects_worked_example_when_metacognitive_signals_require_modeling(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(
            student_id,
            frustration="low",
            total_load=0.35,
            kc_mastery={"KC-1": 0.58},
            engagement="medium",
            confidence_calibration=0.3,
            help_seeking="high",
        ),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "explanation",
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] == "worked_example"
    assert payload["request_context"]["selection_mode"] == "adaptive"
    assert payload["request_context"]["requested_content_type"] is None
    assert payload["request_context"]["selected_content_type"] == "worked_example"
    assert "selection_rationale" in payload["request_context"]
    assert any(block["kind"] == "worked_example" for block in payload["response"]["blocks"])


def test_decide_endpoint_returns_router_decision(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.25}, engagement="medium"),
    )

    response = client.post(
        "/api/router/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        },
    )

    assert response.status_code == 200
    assert response.json()["intervention_type"] == "targeted_practice"


def test_content_endpoints_write_audit_events(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.25}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    decide_response = client.post(
        "/api/router/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        },
    )
    generate_response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "remediation",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    audit_response = client.get("/api/audit/events")

    assert decide_response.status_code == 200
    assert generate_response.status_code == 200
    assert audit_response.status_code == 200

    events = audit_response.json()
    assert events[0]["event_type"] == "content.warm.predictive"
    assert events[1]["event_type"] == "content.generate"
    assert events[2]["event_type"] == "adaptive.decide"
    assert events[1]["payload"]["quality_score"] > 0
    assert events[2]["payload"]["intervention_type"] == "targeted_practice"
    assert events[0]["payload"]["predicted_request_count"] >= 1


def test_metrics_endpoint_summarizes_generation_activity(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))

    client.post(
        "/api/router/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        },
    )
    client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["UNMATCHED-KC"],
            "intent": "explanation",
            "curriculum_context": ["Unmatched concept"],
        },
    )

    response = client.get("/api/observability/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_events"] == 3
    assert payload["decision_events"] == 1
    assert payload["generation_events"] == 1
    assert payload["fallback_generations"] == 1
    assert payload["validation_issue_events"] == 1
    assert payload["predictive_warm_events"] == 1
    assert payload["predictive_warm_requests"] == 2
    assert payload["prompt_template_usages"][0]["template_name"] is not None
    assert payload["prompt_template_usages"][0]["event_count"] == 1


def test_stream_generation_endpoint_emits_sse_events_and_audits(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    with client.stream(
        "POST",
        "/api/llm/stream",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "remediation",
            "curriculum_context": ["Equivalent fractions"],
        },
    ) as response:
        body = b"".join(response.iter_raw()).decode("utf-8")
        content_type = response.headers["content-type"]

    audit_response = client.get("/api/audit/events")

    assert response.status_code == 200
    assert content_type.startswith("text/event-stream")

    events = parse_sse_events(body)
    assert events[0]["event"] == "start"
    assert any(event["event"] == "delta" for event in events)
    assert events[-1]["event"] == "complete"
    assert events[-1]["data"]["response"]["route"]["delivery_mode"] == "generated"
    assert events[-1]["data"]["response"]["grounding"][0]["resource_id"] == "CURR-1"

    audit_events = audit_response.json()
    assert audit_events[0]["event_type"] == "content.generate.stream"
    assert audit_events[0]["payload"]["generated_block_count"] == 2


def test_generation_falls_back_when_no_curriculum_grounding(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.3, kc_mastery={"KC-9": 0.6}, engagement="low"),
    )

    response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["UNMATCHED-KC"],
            "intent": "explanation",
            "curriculum_context": ["Unmatched concept"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"]["route"]["delivery_mode"] == "static_fallback"
    assert payload["response"]["validation_issues"] == [
        "No curriculum grounding was found; fallback or human review is recommended."
    ]
