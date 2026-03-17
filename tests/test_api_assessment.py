from tests.support import build_curriculum_resource, build_profile


def test_socratic_assessment_starts_with_probe_when_no_learner_response(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    audit_response = client.get("/api/audit/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] is not None
    assert "?" in payload["prompt"]
    assert payload["prompt_style"] == "diagnostic"
    assert payload["steering_action"] == "open_probe"
    assert payload["evaluation"]["evidence_strength"] == "insufficient"
    assert payload["evaluation"]["next_action"] == "ask_probe"
    assert payload["evaluation"]["evidence_score"] == 0.0
    assert payload["summary"]["status"] == "in_progress"
    assert payload["summary"]["latest_prompt_style"] == "diagnostic"
    assert payload["summary"]["latest_next_action"] == "ask_probe"
    assert payload["summary"]["next_step"]["content_type"] == "assessment_probe"
    assert payload["summary"]["continue_action"]["kind"] == "continue_socratic"
    assert payload["summary"]["continue_action"]["endpoint"] == "/api/assessments/socratic"
    assert payload["generation_metadata"]["prompt_template_name"] is not None
    assert payload["generated_blocks"]
    event_types = [event["event_type"] for event in audit_response.json()]
    assert "assessment.socratic" in event_types


def test_socratic_assessment_session_not_found_returns_machine_readable_error(client):
    response = client.get("/api/assessments/socratic/missing-session")

    assert response.status_code == 404
    assert response.headers["x-dibble-error-code"] == "socratic_session_not_found"


def test_socratic_assessment_detects_grounded_reasoning_in_learner_response(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "learner_response": "Equivalent fractions are the same amount because 1/2 and 2/4 cover equal space on the model.",
            "learner_confidence": 0.7,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["prompt_style"] == "transfer_check"
    assert payload["steering_action"] == "verify_transfer"
    assert payload["evaluation"]["evidence_strength"] == "demonstrated"
    assert payload["evaluation"]["next_action"] == "advance"
    assert payload["evaluation"]["evidence_score"] >= 0.62
    assert payload["summary"]["status"] == "ready_for_follow_up"
    assert payload["summary"]["latest_next_action"] == "advance"
    assert payload["summary"]["next_step"]["content_type"] == "practice_problem"
    assert payload["summary"]["next_step"]["target_stage"] == "transfer"
    assert payload["summary"]["continue_action"]["kind"] == "generate_follow_up"
    assert payload["summary"]["continue_action"]["request_payload"]["requested_content_type"] == "practice_problem"
    assert "equivalent" in payload["evaluation"]["matched_terms"]


def test_socratic_assessment_session_persists_across_turns(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    first_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    session_id = first_response.json()["session_id"]

    second_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "session_id": session_id,
            "learner_response": "Equivalent fractions are the same amount because the model shows equal space.",
            "learner_confidence": 0.7,
        },
    )
    session_response = client.get(f"/api/assessments/socratic/{session_id}")

    assert second_response.status_code == 200
    assert session_response.status_code == 200

    second_payload = second_response.json()
    session_payload = session_response.json()
    assert second_payload["session_id"] == session_id
    assert second_payload["prompt_style"] == "transfer_check"
    assert second_payload["steering_action"] == "verify_transfer"
    assert second_payload["summary"]["status"] == "ready_for_follow_up"
    assert second_payload["summary"]["latest_steering_action"] == "verify_transfer"
    assert second_payload["summary"]["next_step"]["content_type"] == "practice_problem"
    assert len(second_payload["conversation_history"]) >= 2
    assert len(session_payload["turns"]) == 2
    assert session_payload["turns"][1]["learner_response"] is not None
    assert session_payload["turns"][0]["steering_action"] == "open_probe"
    assert session_payload["summary"]["turn_count"] == 2
    assert session_payload["summary"]["latest_prompt_style"] == "transfer_check"
    assert session_payload["summary"]["latest_next_action"] == "advance"
    assert session_payload["summary"]["continue_action"]["kind"] == "generate_follow_up"
    assert session_payload["summary"]["continue_action"] == second_payload["summary"]["continue_action"]

    third_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "session_id": session_id,
        },
    )

    assert third_response.status_code == 200
    assert third_response.json()["prompt_style"] == "transfer_check"


def test_socratic_assessment_updates_profile_and_unblocks_stretch_routing(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(
            student_id,
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.9},
            engagement="high",
            confidence_calibration=0.3,
            help_seeking="high",
            self_monitoring=0.35,
        ),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    before_response = client.post(
        "/api/router/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "explanation",
        },
    )
    assessment_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "learner_response": "Equivalent fractions are the same amount because the model covers equal space.",
            "learner_confidence": 0.9,
        },
    )
    profile_response = client.get(f"/api/learners/{student_id}/profile")
    after_response = client.post(
        "/api/router/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "explanation",
        },
    )

    assert before_response.status_code == 200
    assert assessment_response.status_code == 200
    assert profile_response.status_code == 200
    assert after_response.status_code == 200

    before_payload = before_response.json()
    assessment_payload = assessment_response.json()
    profile_payload = profile_response.json()
    after_payload = after_response.json()
    assert before_payload["intervention_type"] == "reteach"
    assert assessment_payload["evaluation"]["evidence_strength"] == "demonstrated"
    assert profile_payload["knowledge_state"]["kc_mastery"]["KC-1"] >= 0.85
    assert profile_payload["metacognitive_state"]["confidence_calibration"] > 0.45
    assert profile_payload["metacognitive_state"]["help_seeking"] in {"none", "low", "medium"}
    assert after_payload["intervention_type"] == "stretch"


def test_socratic_assessment_invalidates_matching_predictive_cache_entries(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id, frustration="low", total_load=0.2))
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    client.post(
        "/api/worked-examples/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-invalidate-assessment",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    first_assessment_probe_response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-invalidate-assessment",
            "target_kc_ids": ["KC-1"],
            "intent": "assessment",
            "requested_content_type": "assessment_probe",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    assessment_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-invalidate-assessment",
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
            "learner_response": "They are the same amount because the model shows equal space.",
            "learner_confidence": 0.75,
        },
    )
    second_assessment_probe_response = client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "session-invalidate-assessment",
            "target_kc_ids": ["KC-1"],
            "intent": "assessment",
            "requested_content_type": "assessment_probe",
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    audit_response = client.get("/api/audit/events")

    assert first_assessment_probe_response.status_code == 200
    assert assessment_response.status_code == 200
    assert second_assessment_probe_response.status_code == 200
    assert first_assessment_probe_response.json()["quality"]["cache_hit"] is True
    assert second_assessment_probe_response.json()["quality"]["cache_hit"] is False

    summary_event = next(
        event
        for event in audit_response.json()
        if event["event_type"] == "learning.run.summary" and event["payload"]["trigger_event_type"] == "assessment.socratic"
    )
    progress_event = next(event for event in audit_response.json() if event["event_type"] == "learning.progress.profile")
    invalidation_event = next(
        event
        for event in audit_response.json()
        if event["event_type"] == "content.cache.invalidate" and event["payload"]["trigger_event_type"] == "assessment.socratic"
    )
    assert progress_event["payload"]["source_run_summary_event_id"] == summary_event["event_id"]
    assert invalidation_event["payload"]["expired_entries"] >= 1


def test_socratic_assessment_propagates_mastery_to_prerequisites_and_parent_lo(client, student_id):
    from tests.support import build_knowledge_component

    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(
            student_id,
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.42, "KC-2": 0.78},
            engagement="high",
            confidence_calibration=0.3,
            help_seeking="high",
            self_monitoring=0.35,
        ),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.put("/api/knowledge-components/KC-1", json=build_knowledge_component("KC-1", parent_lo_id="LO-1"))
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component("KC-2", parent_lo_id="LO-1", prerequisite_kc_ids=["KC-1"]),
    )

    assessment_response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-2"],
            "curriculum_context": ["Equivalent fractions"],
            "learner_response": "Equivalent fractions are the same amount because 1/2 and 2/4 cover equal space on the model.",
            "learner_confidence": 0.88,
        },
    )
    profile_response = client.get(f"/api/learners/{student_id}/profile")
    audit_response = client.get("/api/audit/events")

    assert assessment_response.status_code == 200
    assert profile_response.status_code == 200
    assert audit_response.status_code == 200

    profile_payload = profile_response.json()
    assessment_event = next(
        event for event in audit_response.json() if event["event_type"] == "assessment.socratic"
    )
    assert profile_payload["knowledge_state"]["kc_mastery"]["KC-1"] > 0.42
    assert profile_payload["knowledge_state"]["lo_mastery"]["LO-1"] > 0.6
    assert assessment_event["payload"]["steering_action"] == "verify_transfer"
    assert assessment_event["payload"]["propagated_kc_mastery"]["KC-1"] > 0.42
    assert assessment_event["payload"]["propagated_lo_mastery"]["LO-1"] > 0.6
