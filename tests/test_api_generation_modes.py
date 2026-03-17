from tests.support import build_curriculum_resource, build_knowledge_component, build_profile


def test_worked_examples_endpoint_returns_fading_metadata(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.45, kc_mastery={"KC-1": 0.55}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component(
            "KC-1",
            name="Generate equivalent fractions",
            nearby_kc_ids=["KC-2"],
        ),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            name="Compare equivalent fractions",
        ),
    )

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
    assert payload["request_context"]["worked_example_release_stage"] == "completion_then_justify"
    assert payload["request_context"]["worked_example_learner_release_intensity"] == "guided_release"
    assert payload["request_context"]["worked_example_visible_step_roles"] == ["setup", "worked step"]
    assert payload["request_context"]["worked_example_hidden_step_role"] == "target completion"
    assert "setup: establish the representation" in payload["request_context"]["worked_example_step_outline"][0]
    assert "target completion:" in payload["request_context"]["worked_example_learner_release"]
    assert "Generate equivalent fractions" in payload["request_context"]["worked_example_transfer_move"]
    assert payload["request_context"]["worked_example_transfer_plan"]["preserve"]
    assert payload["request_context"]["worked_example_transfer_plan"]["change"]
    assert any(block["kind"] == "worked_example" for block in payload["response"]["blocks"])
    assert any(block["kind"] == "instruction" for block in payload["response"]["blocks"])


def test_problem_endpoint_returns_difficulty_band_metadata(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.2}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component(
            "KC-1",
            name="Generate equivalent fractions",
            common_misconceptions=[
                {
                    "misconception_id": "fraction-whole-number-bias",
                    "label": "Whole-number bias",
                    "description": "The learner compares the numerator and denominator separately like whole numbers.",
                    "trigger_terms": ["numerator", "denominator"],
                    "remediation_hint": "Compare the whole amount before comparing the parts.",
                }
            ],
        ),
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
    assert payload["content_type"] == "practice_problem"
    assert payload["request_context"]["requested_content_type"] == "practice_problem"
    assert payload["request_context"]["selected_content_type"] == "practice_problem"
    assert payload["request_context"]["selection_mode"] == "explicit"
    assert payload["request_context"]["difficulty_band"] == "support"
    assert payload["request_context"]["practice_distractor_family"] == "misconception_mirror_pair"
    assert payload["request_context"]["practice_distractor_support_intensity"] == "explicit"
    assert "Whole-number bias" in payload["request_context"]["practice_distractor_focus"]
    assert payload["request_context"]["practice_distractor_blueprint"][0]["slot"] == "misconception_mirror"
    assert "repair_cue" in payload["request_context"]["practice_distractor_blueprint"][0]
    assert "misconception_mirror" in payload["request_context"]["practice_distractor_slots"][0]
    assert "avoids Whole-number bias" in payload["request_context"]["practice_answer_check_focus"]
    assert payload["request_context"]["practice_distractor_misconception_ids"] == ["fraction-whole-number-bias"]
    assert (
        payload["request_context"]["practice_distractor_remediation_hint"]
        == "Compare the whole amount before comparing the parts."
    )
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


def test_warmed_generation_reuses_hydrated_target_kc_hints(client, student_id):
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.2}, engagement="medium"),
    )
    client.put("/api/curriculum/resources/CURR-1", json=build_curriculum_resource())
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component(
            "KC-1",
            name="Generate equivalent fractions",
            common_misconceptions=[
                {
                    "misconception_id": "fraction-whole-number-bias",
                    "label": "Whole-number bias",
                    "description": "The learner compares the numerator and denominator separately like whole numbers.",
                    "trigger_terms": ["numerator", "denominator"],
                    "remediation_hint": "Compare the whole amount before comparing the parts.",
                }
            ],
        ),
    )

    warm_response = client.post(
        "/api/content/warm",
        json={
            "requests": [
                {
                    "student_id": str(student_id),
                    "target_kc_ids": ["KC-1"],
                    "intent": "practice",
                    "requested_content_type": "practice_problem",
                    "curriculum_context": ["Equivalent fractions"],
                }
            ]
        },
    )
    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )

    assert warm_response.status_code == 200
    assert generate_response.status_code == 200
    payload = generate_response.json()
    assert payload["quality"]["cache_hit"] is True
    assert "Whole-number bias" in payload["request_context"]["practice_distractor_focus"]
