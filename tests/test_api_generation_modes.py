from tests.support import build_curriculum_resource, build_profile


def test_worked_examples_endpoint_returns_fading_metadata(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.45, kc_mastery={"KC-1": 0.55}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    response = client.post(
        "/api/worked-examples/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] == "worked_example"
    assert payload["request_context"]["requested_content_type"] == "worked_example"
    assert payload["request_context"]["selected_content_type"] == "worked_example"
    assert payload["request_context"]["selection_mode"] == "explicit"
    assert payload["request_context"]["fading_strategy"] == "completion"
    assert any(block["kind"] == "worked_example" for block in payload["response"]["blocks"])
    assert any(block["kind"] == "instruction" for block in payload["response"]["blocks"])


def test_problem_endpoint_returns_difficulty_band_metadata(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.2}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())

    response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] == "practice_problem"
    assert payload["request_context"]["requested_content_type"] == "practice_problem"
    assert payload["request_context"]["selected_content_type"] == "practice_problem"
    assert payload["request_context"]["selection_mode"] == "explicit"
    assert payload["request_context"]["difficulty_band"] == "support"
    assert any(block["kind"] == "practice" for block in payload["response"]["blocks"])
