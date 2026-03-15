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
    assert payload["evaluation"]["evidence_strength"] == "insufficient"
    assert payload["evaluation"]["next_action"] == "ask_probe"
    assert payload["evaluation"]["evidence_score"] == 0.0
    assert payload["generation_metadata"]["prompt_template_name"] is not None
    assert payload["generated_blocks"]
    assert audit_response.json()[0]["event_type"] == "assessment.socratic"


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
    assert payload["evaluation"]["evidence_strength"] == "demonstrated"
    assert payload["evaluation"]["next_action"] == "advance"
    assert payload["evaluation"]["evidence_score"] >= 0.62
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
    assert len(second_payload["conversation_history"]) >= 2
    assert len(session_payload["turns"]) == 2
    assert session_payload["turns"][1]["learner_response"] is not None

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
