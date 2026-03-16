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
    assert summary_response.json()["engagement"] == "medium"
    assert summary_response.json()["frustration"] == "high"
    assert summary_response.json()["confidence_calibration"] == 0.5
    assert summary_response.json()["calibration"]["source"] == "insufficient"
    assert summary_response.json()["progress"]["source"] == "insufficient"
    assert summary_response.json()["strategy"]["source"] == "insufficient"
    assert summary_response.json()["recent_activity"]["generation_count"] == 0
    assert profile_response.json()["profile_metadata"]["student_id"] == str(student_id)
    assert str(student_id) in list_response.json()


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
    assert payload["recent_activity"]["generation_count"] == 1
    assert payload["recent_activity"]["last_generation_id"] == "summary-gen-1"
    assert payload["recent_activity"]["last_learning_session_id"] == "summary-session-1"


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
