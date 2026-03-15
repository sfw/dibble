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
    assert "?" in payload["prompt"]
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
    assert payload["evaluation"]["evidence_strength"] == "demonstrated"
    assert payload["evaluation"]["next_action"] == "advance"
    assert "equivalent" in payload["evaluation"]["matched_terms"]
