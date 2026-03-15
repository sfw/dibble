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
    assert payload["prompt_style"] == "diagnostic"
    assert payload["evaluation"]["evidence_strength"] == "demonstrated"
    assert payload["evaluation"]["next_action"] == "advance"
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
    assert second_payload["prompt_style"] == "diagnostic"
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
