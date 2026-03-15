from uuid import uuid4

from dibble.app import create_app

from tests.support import build_curriculum_resource, build_profile


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
