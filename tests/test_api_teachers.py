from uuid import uuid4

from tests.support import (
    assert_machine_readable_error,
    build_classroom,
    build_curriculum_resource,
    build_knowledge_component,
    build_profile,
)


def test_teacher_classroom_read_model_packages_learner_cards_and_counts(client):
    active_student_id = uuid4()
    blocked_student_id = uuid4()

    client.put(
        f"/api/learners/{active_student_id}/profile",
        json=build_profile(
            active_student_id,
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.86, "KC-2": 0.72},
        ),
    )
    client.put(
        f"/api/learners/{blocked_student_id}/profile",
        json=build_profile(
            blocked_student_id,
            frustration="medium",
            total_load=0.45,
            kc_mastery={"KC-1": 0.2, "KC-2": 0.12},
        ),
    )
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component(
            "KC-1",
            name="Recognize equivalent fractions",
        ),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            name="Generate equivalent fractions",
        ),
    )
    client.put(
        "/api/curriculum/resources/CURR-2",
        json=build_curriculum_resource(
            resource_id="CURR-2",
            title="Equivalent Fraction Practice",
            knowledge_component_ids=["KC-2"],
            learning_objective_ids=["LO-1"],
        ),
    )

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(active_student_id),
            "learning_session_id": "teacher-classroom-session",
            "target_kc_ids": ["KC-2"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    upsert_classroom_response = client.put(
        "/api/teachers/classrooms/CLASS-1",
        json=build_classroom(
            classroom_id="CLASS-1",
            title="Grade 5 Fractions",
            teacher_label="Ms. Rivera",
            student_ids=[str(active_student_id), str(blocked_student_id), "missing-student-id"],
        ),
    )
    classroom_response = client.get("/api/teachers/classrooms/CLASS-1")
    list_response = client.get("/api/teachers/classrooms")
    active_summary_response = client.get(f"/api/learners/{active_student_id}/summary")
    blocked_summary_response = client.get(f"/api/learners/{blocked_student_id}/summary")

    assert generate_response.status_code == 200
    assert upsert_classroom_response.status_code == 200
    assert classroom_response.status_code == 200
    assert list_response.status_code == 200
    assert active_summary_response.status_code == 200
    assert blocked_summary_response.status_code == 200

    classroom_payload = classroom_response.json()
    list_payload = list_response.json()
    active_summary_payload = active_summary_response.json()
    blocked_summary_payload = blocked_summary_response.json()
    active_card = next(card for card in classroom_payload["learners"] if card["student_id"] == str(active_student_id))
    blocked_card = next(card for card in classroom_payload["learners"] if card["student_id"] == str(blocked_student_id))

    assert classroom_payload["classroom_id"] == "CLASS-1"
    assert classroom_payload["title"] == "Grade 5 Fractions"
    assert classroom_payload["learner_count"] == 2
    assert classroom_payload["missing_learner_count"] == 1
    assert classroom_payload["missing_student_ids"] == ["missing-student-id"]
    assert classroom_payload["active_flow_count"] == 1
    assert classroom_payload["intervention_available_count"] == 1
    assert classroom_payload["blocked_progression_count"] == 1
    assert classroom_payload["attention_needed_count"] == 2

    assert active_card["current_flow"]["flow_type"] == "lesson"
    assert active_card["intervention"]["proposal_status"] == "available"
    assert active_card["intervention"]["recommended_action_kind"] == "generate_follow_up"
    assert active_card["curriculum_progression"]["status"] in {"active_curriculum_focus", "ready_for_next_resource"}
    assert active_card["attention_level"] == "medium"
    assert "teacher_intervention_available" in active_card["attention_reasons"]
    assert active_card["current_flow"] == active_summary_payload["current_flow"]
    assert active_card["curriculum_progression"] == active_summary_payload["curriculum_progression"]

    assert blocked_card["current_flow"]["status"] == "idle"
    assert blocked_card["curriculum_progression"]["status"] == "blocked_on_prerequisites"
    assert blocked_card["curriculum_progression"]["blocked_resources"][0]["resource_id"] == "CURR-2"
    assert blocked_card["attention_level"] == "medium"
    assert "blocked_on_prerequisites" in blocked_card["attention_reasons"]
    assert blocked_card["current_flow"] == blocked_summary_payload["current_flow"]
    assert blocked_card["curriculum_progression"] == blocked_summary_payload["curriculum_progression"]

    assert list_payload[0]["classroom_id"] == "CLASS-1"
    assert list_payload[0]["learner_count"] == 2
    assert list_payload[0]["missing_learner_count"] == 1
    assert list_payload[0]["intervention_available_count"] == 1


def test_teacher_classroom_not_found_returns_machine_readable_error(client):
    response = client.get("/api/teachers/classrooms/missing-classroom")

    assert_machine_readable_error(
        response,
        status_code=404,
        code="classroom_not_found",
        detail="Classroom not found.",
    )
