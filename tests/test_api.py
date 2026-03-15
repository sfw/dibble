import json
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings

from tests.support import build_curriculum_resource, build_profile


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for record in body.strip().split("\n\n"):
        if not record.strip():
            continue
        event_name = ""
        data = ""
        for line in record.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                data = line.removeprefix("data: ")
        events.append({"event": event_name, "data": json.loads(data)})
    return events


def test_healthcheck(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_profile_round_trip_and_summary(client, student_id):
    put_response = client.put(f"/api/v1/profiles/{student_id}", json=build_profile(student_id))
    summary_response = client.get(f"/api/v1/profiles/{student_id}/summary")
    list_response = client.get("/api/v1/profiles")

    assert put_response.status_code == 200
    assert summary_response.status_code == 200
    assert summary_response.json()["kc_count"] == 2
    assert summary_response.json()["frustration"] == "high"
    assert str(student_id) in list_response.json()


def test_curriculum_resource_round_trip(client):
    resource = build_curriculum_resource()

    put_response = client.put("/api/v1/curriculum/resources/CURR-1", json=resource)
    list_response = client.get("/api/v1/curriculum/resources")

    assert put_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()[0]["resource_id"] == "CURR-1"


def test_generation_uses_grounding_and_step_back_route(client, student_id):
    client.put(f"/api/v1/profiles/{student_id}", json=build_profile(student_id))
    client.put("/api/v1/curriculum/resources/CURR-1", json=build_curriculum_resource())

    response = client.post(
        "/api/v1/adaptive/generate",
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
    assert payload["route"]["intervention_type"] == "step_back"
    assert payload["route"]["delivery_mode"] == "generated"
    assert payload["grounding"][0]["resource_id"] == "CURR-1"
    assert payload["validation_issues"] == []


def test_decide_endpoint_returns_router_decision(client, student_id):
    client.put(
        f"/api/v1/profiles/{student_id}",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.25}, engagement="medium"),
    )

    response = client.post(
        "/api/v1/adaptive/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        },
    )

    assert response.status_code == 200
    assert response.json()["intervention_type"] == "targeted_practice"


def test_adaptive_endpoints_write_audit_events(client, student_id):
    client.put(
        f"/api/v1/profiles/{student_id}",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.25}, engagement="medium"),
    )
    client.put("/api/v1/curriculum/resources/CURR-1", json=build_curriculum_resource())

    decide_response = client.post(
        "/api/v1/adaptive/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        },
    )
    generate_response = client.post(
        "/api/v1/adaptive/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "remediation",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    audit_response = client.get("/api/v1/audit/events")

    assert decide_response.status_code == 200
    assert generate_response.status_code == 200
    assert audit_response.status_code == 200

    events = audit_response.json()
    assert events[0]["event_type"] == "adaptive.generate"
    assert events[1]["event_type"] == "adaptive.decide"
    assert events[0]["payload"]["grounding_count"] == 1
    assert events[1]["payload"]["intervention_type"] == "targeted_practice"


def test_metrics_endpoint_summarizes_generation_activity(client, student_id):
    client.put(f"/api/v1/profiles/{student_id}", json=build_profile(student_id))

    client.post(
        "/api/v1/adaptive/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        },
    )
    client.post(
        "/api/v1/adaptive/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["UNMATCHED-KC"],
            "intent": "explanation",
            "curriculum_context": ["Unmatched concept"],
        },
    )

    response = client.get("/api/v1/observability/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_events"] == 2
    assert payload["decision_events"] == 1
    assert payload["generation_events"] == 1
    assert payload["fallback_generations"] == 1
    assert payload["validation_issue_events"] == 1


def test_stream_generation_endpoint_emits_sse_events_and_audits(client, student_id):
    client.put(f"/api/v1/profiles/{student_id}", json=build_profile(student_id))
    client.put("/api/v1/curriculum/resources/CURR-1", json=build_curriculum_resource())

    with client.stream(
        "POST",
        "/api/v1/adaptive/generate/stream",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "remediation",
            "curriculum_context": ["Equivalent fractions"],
        },
    ) as response:
        body = b"".join(response.iter_raw()).decode("utf-8")
        content_type = response.headers["content-type"]

    audit_response = client.get("/api/v1/audit/events")

    assert response.status_code == 200
    assert content_type.startswith("text/event-stream")

    events = _parse_sse_events(body)
    assert events[0]["event"] == "start"
    assert any(event["event"] == "delta" for event in events)
    assert events[-1]["event"] == "complete"
    assert events[-1]["data"]["response"]["route"]["delivery_mode"] == "generated"
    assert events[-1]["data"]["response"]["grounding"][0]["resource_id"] == "CURR-1"

    audit_events = audit_response.json()
    assert audit_events[0]["event_type"] == "adaptive.generate.stream"
    assert audit_events[0]["payload"]["generated_block_count"] == 2


def test_auth_can_protect_api_endpoints(tmp_path, student_id):
    settings = Settings(
        database_path=str(tmp_path / "dibble-auth.db"),
        auth_enabled=True,
        auth_api_keys=("secret-key",),
    )
    app = create_app(settings)

    with TestClient(app) as client:
        health_response = client.get("/health")
        unauthorized = client.get("/api/v1/profiles")
        authorized = client.put(
            f"/api/v1/profiles/{student_id}",
            headers={"X-API-Key": "secret-key"},
            json=build_profile(student_id),
        )
        audit_response = client.get("/api/v1/audit/events", headers={"X-API-Key": "secret-key"})

    assert health_response.status_code == 200
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["event_type"] == "auth.request"
    assert audit_response.json()[0]["status"] == "denied"


def test_generation_falls_back_when_no_curriculum_grounding(client, student_id):
    client.put(
        f"/api/v1/profiles/{student_id}",
        json=build_profile(student_id, frustration="low", total_load=0.3, kc_mastery={"KC-9": 0.6}, engagement="low"),
    )

    response = client.post(
        "/api/v1/adaptive/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["UNMATCHED-KC"],
            "intent": "explanation",
            "curriculum_context": ["Unmatched concept"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"]["delivery_mode"] == "static_fallback"
    assert payload["validation_issues"] == [
        "No curriculum grounding was found; fallback or human review is recommended."
    ]


def test_profile_persists_across_app_instances(app_settings):
    student_id = uuid4()
    app_one = create_app(app_settings)
    app_two = create_app(app_settings)

    from fastapi.testclient import TestClient

    with TestClient(app_one) as client_one:
        response = client_one.put(f"/api/v1/profiles/{student_id}", json=build_profile(student_id))
        assert response.status_code == 200

    with TestClient(app_two) as client_two:
        response = client_two.get(f"/api/v1/profiles/{student_id}")
        assert response.status_code == 200
        assert response.json()["student_id"] == str(student_id)
