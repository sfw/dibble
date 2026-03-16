from dibble.services.audit_store import SQLiteAuditStore

from tests.support import build_profile


def test_observation_endpoint_updates_inferred_state_and_profile(client, student_id, app_settings):
    audit_store = SQLiteAuditStore(app_settings.database_path)
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="none", total_load=0.2))
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "assessment",
            "generation_id": "gen-123",
            "learning_session_id": "learn-session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "content_type": "assessment_probe",
            "prompt_template_name": "assessment_probe.causal_probe",
            "prompt_template_variant": "causal_probe",
            "quality_score": 0.8,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "gen-123",
            "learning_session_id": "learn-session-1",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "evidence_strength": "insufficient",
            "evidence_score": 0.22,
            "profile_update_applied": False,
        },
    )

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
    learner_observe_event = next(event for event in audit_events if event["event_type"] == "learner.observe")
    summary_event = next(event for event in audit_events if event["event_type"] == "learning.run.summary")
    profile_event = next(event for event in audit_events if event["event_type"] == "learning.calibration.profile")

    assert observed["student_id"] == str(student_id)
    assert observed["observation_count"] == 1
    assert observed["affective_state"]["frustration"] in {"medium", "high"}
    assert observed["cognitive_load"]["total_load"] >= 0.5
    assert observed["metacognitive_state"]["help_seeking"] in {"medium", "high"}
    assert observed["metacognitive_state"]["confidence_calibration"] < 0.8
    assert state["observation_count"] == 1
    assert profile["affective_state"]["frustration"] == observed["affective_state"]["frustration"]
    assert profile["cognitive_load"]["total_load"] == observed["cognitive_load"]["total_load"]
    assert profile["metacognitive_state"]["confidence_calibration"] == observed["metacognitive_state"]["confidence_calibration"]
    assert "processing_speed" in profile["cognitive_traits"]
    assert "confidence_calibration" in learner_observe_event["payload"]
    assert "processing_speed" in learner_observe_event["payload"]["updated_cognitive_traits"]
    assert learner_observe_event["payload"]["task_type"] == "assessment"
    assert learner_observe_event["payload"]["support_level"] == "low"
    assert learner_observe_event["payload"]["learning_session_id"] == "learn-session-1"
    assert learner_observe_event["payload"]["generation_id"] == "gen-123"
    assert learner_observe_event["payload"]["observed_content_type"] == "assessment_probe"
    assert learner_observe_event["payload"]["target_kc_ids"] == ["KC-1"]
    assert learner_observe_event["payload"]["target_lo_ids"] == ["LO-1"]
    assert learner_observe_event["payload"]["state_calibration_signal"] == "negative"
    assert learner_observe_event["payload"]["state_calibration_applied"] is True
    assert learner_observe_event["payload"]["state_calibration_run_count"] >= 1
    assert summary_event["payload"]["generation_id"] == "gen-123"
    assert summary_event["payload"]["trigger_event_type"] == "learner.observe"
    assert summary_event["payload"]["run_summary_score"] is not None
    assert profile_event["payload"]["source_run_summary_event_id"] == summary_event["event_id"]
    assert profile_event["payload"]["matched_run_count"] >= 1
