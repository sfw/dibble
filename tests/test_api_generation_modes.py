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


def test_generation_modes_use_persisted_calibration_profiles(client, student_id, app_settings):
    from dibble.services.audit_store import SQLiteAuditStore

    audit_store = SQLiteAuditStore(app_settings.database_path)
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.3, kc_mastery={"KC-1": 0.2}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    audit_store.append(
        event_type="learning.calibration.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.84,
            "average_run_confidence": 0.78,
            "matched_run_count": 4,
            "matched_session_count": 2,
            "positive_run_rate": 0.75,
            "negative_run_rate": 0.0,
            "profile_signal": "positive",
        },
    )

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
    assert payload["request_context"]["difficulty_band"] == "on_grade"
    assert payload["request_context"]["mode_calibration"]["source"] == "profile"
    assert payload["request_context"]["mode_calibration"]["support_bias"] == 1
    assert payload["request_context"]["mode_calibration_applied"] is True


def test_generation_modes_use_persisted_progress_profiles(client, student_id, app_settings):
    from dibble.services.audit_store import SQLiteAuditStore

    audit_store = SQLiteAuditStore(app_settings.database_path)
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.3, kc_mastery={"KC-1": 0.2}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.74,
            "average_run_confidence": 0.8,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "positive_run_rate": 0.5,
            "negative_run_rate": 0.0,
            "recent_average_run_outcome_score": 0.81,
            "prior_average_run_outcome_score": 0.65,
            "progress_delta": 0.16,
            "progress_signal": "improving",
        },
    )

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
    assert payload["request_context"]["difficulty_band"] == "on_grade"
    assert payload["request_context"]["mode_calibration"]["source"] == "progress_profile"
    assert payload["request_context"]["mode_calibration"]["progress_signal"] == "improving"
    assert payload["request_context"]["mode_calibration"]["support_bias"] == 1
    assert payload["request_context"]["mode_calibration_applied"] is True
