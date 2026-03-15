from tests.api_support import parse_sse_events
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
    assert payload["content_type"] == "remedial_micro_module"
    assert payload["response"]["route"]["intervention_type"] == "step_back"
    assert payload["quality"]["validation_passed"] is True
    assert payload["request_context"]["target_kc_ids"] == ["KC-1", "KC-2"]
    assert payload["request_context"]["prerequisite_kc_ids"] == ["KC-1"]
    assert payload["request_context"]["misconception_signals"][0]["kc_id"] == "KC-1"
    assert "prerequisite knowledge components" in payload["request_context"]["remediation_rationale"]

    audit_response = client.get("/api/audit/events")
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["event_type"] == "remediation.trigger"
    assert audit_response.json()[0]["payload"]["misconception_signal_count"] >= 1


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
    assert events[0]["event_type"] == "content.generate"
    assert events[1]["event_type"] == "adaptive.decide"
    assert events[0]["payload"]["quality_score"] > 0
    assert events[1]["payload"]["intervention_type"] == "targeted_practice"


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
    assert payload["total_events"] == 2
    assert payload["decision_events"] == 1
    assert payload["generation_events"] == 1
    assert payload["fallback_generations"] == 1
    assert payload["validation_issue_events"] == 1
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
