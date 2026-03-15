from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app

from tests.support import build_curriculum_resource, build_profile


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
    assert summary_response.json()["frustration"] == "high"
    assert profile_response.json()["profile_metadata"]["student_id"] == str(student_id)
    assert str(student_id) in list_response.json()


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
