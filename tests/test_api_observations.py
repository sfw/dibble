from tests.support import build_profile


def test_observation_endpoint_updates_inferred_state_and_profile(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="none", total_load=0.2))

    observe_response = client.post(
        f"/api/learners/{student_id}/observations",
        json={
            "response_time_ms": 30000,
            "hints_used": 3,
            "error_count": 3,
            "pause_count": 4,
            "modality_switches": 2,
            "completed": False,
            "confidence": 0.2,
            "task_type": "assessment",
            "support_level": "low",
            "expected_duration_ms": 18000,
            "learning_session_id": "learn-session-1",
            "generation_id": "gen-123",
            "observed_content_type": "assessment_probe",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
        },
    )
    state_response = client.get(f"/api/learners/{student_id}/state")
    profile_response = client.get(f"/api/learners/{student_id}/profile")
    audit_response = client.get("/api/audit/events")

    assert observe_response.status_code == 200
    assert state_response.status_code == 200
    assert profile_response.status_code == 200
    assert audit_response.status_code == 200

    observed = observe_response.json()
    state = state_response.json()
    profile = profile_response.json()
    audit_events = audit_response.json()

    assert observed["student_id"] == str(student_id)
    assert observed["observation_count"] == 1
    assert observed["affective_state"]["frustration"] in {"medium", "high"}
    assert observed["cognitive_load"]["total_load"] >= 0.5
    assert observed["metacognitive_state"]["help_seeking"] in {"medium", "high"}
    assert state["observation_count"] == 1
    assert profile["affective_state"]["frustration"] == observed["affective_state"]["frustration"]
    assert profile["cognitive_load"]["total_load"] == observed["cognitive_load"]["total_load"]
    assert profile["metacognitive_state"]["confidence_calibration"] == observed["metacognitive_state"]["confidence_calibration"]
    assert audit_events[0]["event_type"] == "learner.observe"
    assert "confidence_calibration" in audit_events[0]["payload"]
    assert audit_events[0]["payload"]["task_type"] == "assessment"
    assert audit_events[0]["payload"]["support_level"] == "low"
    assert audit_events[0]["payload"]["learning_session_id"] == "learn-session-1"
    assert audit_events[0]["payload"]["generation_id"] == "gen-123"
    assert audit_events[0]["payload"]["observed_content_type"] == "assessment_probe"
    assert audit_events[0]["payload"]["target_kc_ids"] == ["KC-1"]
    assert audit_events[0]["payload"]["target_lo_ids"] == ["LO-1"]
