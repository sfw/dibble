from tests.support import build_profile


def test_decide_endpoint_exposes_router_calibration_summary(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(
            student_id,
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.25},
            engagement="medium",
        ),
    )

    response = client.post(
        "/api/router/decide",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intervention_type"] == "targeted_practice"
    assert payload["calibration"]["signal"] == "insufficient"
    assert payload["calibration"]["source"] == "insufficient"
    assert payload["calibration"]["matched_run_count"] == 0
    assert payload["calibration"]["progress_signal"] == "insufficient"
