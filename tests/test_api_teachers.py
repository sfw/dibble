from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.services.auth import hash_credential
from dibble.models.classroom_membership import (
    ClassroomMembershipRole,
    ClassroomMembershipUpsert,
)
from dibble.services.classroom_membership_store import SQLiteClassroomMembershipStore
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database

from tests.support import (
    assert_machine_readable_error,
    build_classroom,
    build_outcome,
    build_knowledge_component,
    build_profile,
)


def _make_authenticated_app(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    return create_app(settings), db_path


def _seed_api_user(
    db_path: str,
    *,
    api_key: str | None,
    role: str,
    user_id: str,
    learner_id: str | None = None,
    display_name: str | None = None,
    section_ids: list[str] | None = None,
) -> User:
    store = SQLiteUserStore(db_path)
    membership_store = SQLiteClassroomMembershipStore(db_path)
    now = datetime.now(timezone.utc).isoformat()
    user = store.create(
        User(
            user_id=user_id,
            display_name=display_name,
            role=role,
            api_key_hash=hash_credential(api_key) if api_key is not None else None,
            learner_id=learner_id,
            section_ids=section_ids or [],
            created_at=now,
            updated_at=now,
        )
    )
    if role in {"teacher", "learner"} and section_ids:
        membership_store.replace_for_user(
            user_id=user_id,
            role=ClassroomMembershipRole.teacher
            if role == "teacher"
            else ClassroomMembershipRole.learner,
            section_ids=section_ids,
        )
    return user


def test_teacher_classroom_read_model_packages_learner_cards_and_counts(
    client, app_settings
):
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
        "/api/curriculum/outcomes/CURR-2",
        json=build_outcome(
            "CURR-2",
            title="Equivalent Fraction Practice",
            knowledge_component_ids=["KC-2"],
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
        "/api/teachers/sections/CLASS-1",
        json=build_classroom(
            section_id="CLASS-1",
            title="Grade 5 Fractions",
        ),
    )
    client.post(
        "/api/users",
        json={
            "display_name": "Ms. Rivera",
            "role": "teacher",
            "section_ids": ["CLASS-1"],
        },
    )
    client.post(
        "/api/users",
        json={
            "display_name": "Active Learner",
            "role": "learner",
            "learner_id": str(active_student_id),
            "section_ids": ["CLASS-1"],
        },
    )
    client.post(
        "/api/users",
        json={
            "display_name": "Blocked Learner",
            "role": "learner",
            "learner_id": str(blocked_student_id),
            "section_ids": ["CLASS-1"],
        },
    )
    SQLiteClassroomMembershipStore(app_settings.database_path).upsert(
        ClassroomMembershipUpsert(
            classroom_id="CLASS-1",
            user_id="missing-student-id",
            role=ClassroomMembershipRole.learner,
        )
    )
    classroom_response = client.get("/api/teachers/sections/CLASS-1")
    list_response = client.get("/api/teachers/sections")
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
    active_card = next(
        card
        for card in classroom_payload["learners"]
        if card["student_id"] == str(active_student_id)
    )
    blocked_card = next(
        card
        for card in classroom_payload["learners"]
        if card["student_id"] == str(blocked_student_id)
    )

    assert classroom_payload["section_id"] == "CLASS-1"
    assert classroom_payload["course_id"] == "COURSE-1"
    assert classroom_payload["title"] == "Grade 5 Fractions"
    assert classroom_payload["teacher_label"] == "Ms. Rivera"
    assert classroom_payload["learner_count"] == 2
    assert classroom_payload["missing_learner_count"] == 1
    assert classroom_payload["missing_student_ids"] == ["missing-student-id"]
    assert classroom_payload["active_flow_count"] == 1
    assert classroom_payload["intervention_available_count"] == 1
    assert classroom_payload["blocked_progression_count"] == 1
    assert classroom_payload["attention_needed_count"] == 2

    assert active_card["current_flow"]["flow_type"] == "lesson"
    assert active_card["intervention"]["proposal_status"] == "available"
    assert (
        active_card["intervention"]["recommended_action_kind"] == "generate_follow_up"
    )
    assert active_card["curriculum_progression"]["status"] in {
        "active_curriculum_focus",
        "ready_for_next_outcome",
    }
    assert active_card["attention_level"] == "medium"
    assert active_card["triage_section"] == "teacher_action"
    assert "teacher_intervention_available" in active_card["attention_reasons"]
    assert active_card["display_rationale"] is not None
    assert isinstance(active_card["display_rationale"], str)
    assert active_card["current_flow"] == active_summary_payload["current_flow"]
    assert (
        "current learner flow releases the active target"
        in active_card["curriculum_progression"]["rationale"]
    )
    assert (
        active_card["curriculum_progression"]
        == active_summary_payload["curriculum_progression"]
    )

    assert blocked_card["current_flow"]["status"] == "idle"
    assert (
        blocked_card["curriculum_progression"]["status"] == "blocked_on_prerequisites"
    )
    assert (
        blocked_card["curriculum_progression"]["blocked_outcomes"][0]["outcome_id"]
        == "CURR-2"
    )
    assert (
        "stays blocked instead of becoming the next curriculum focus"
        in blocked_card["curriculum_progression"]["blocked_outcomes"][0]["rationale"]
    )
    assert blocked_card["display_rationale"] is not None
    assert blocked_card["attention_level"] == "medium"
    assert blocked_card["triage_section"] == "needs_attention"
    assert "blocked_on_prerequisites" in blocked_card["attention_reasons"]
    assert blocked_card["current_flow"] == blocked_summary_payload["current_flow"]
    assert (
        blocked_card["curriculum_progression"]
        == blocked_summary_payload["curriculum_progression"]
    )

    assert list_payload[0]["section_id"] == "CLASS-1"
    assert list_payload[0]["learner_count"] == 2
    assert list_payload[0]["missing_learner_count"] == 1
    assert list_payload[0]["intervention_available_count"] == 1


def test_teacher_classroom_keeps_active_curriculum_rationale_aligned_with_current_flow(
    client,
    app_settings,
):
    student_id = uuid4()

    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(
            student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.32}
        ),
    )
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify equivalent fractions"),
    )
    client.put(
        "/api/curriculum/outcomes/CURR-1",
        json=build_outcome(
            "CURR-1",
            title="Equivalent Fraction Foundations",
            knowledge_component_ids=["KC-1"],
        ),
    )

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "teacher-classroom-aligned-session",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    client.put(
        "/api/teachers/sections/CLASS-ALIGNED",
        json=build_classroom(
            section_id="CLASS-ALIGNED",
            title="Aligned Flow Classroom",
        ),
    )
    _seed_api_user(
        app_settings.database_path,
        api_key=None,
        role="learner",
        user_id="aligned-learner",
        learner_id=str(student_id),
        section_ids=["CLASS-ALIGNED"],
    )

    classroom_response = client.get("/api/teachers/sections/CLASS-ALIGNED")
    summary_response = client.get(f"/api/learners/{student_id}/summary")

    assert generate_response.status_code == 200
    assert classroom_response.status_code == 200
    assert summary_response.status_code == 200

    learner_card = classroom_response.json()["learners"][0]
    summary_payload = summary_response.json()

    assert learner_card["curriculum_progression"]["status"] == "active_curriculum_focus"
    assert (
        learner_card["curriculum_progression"]["rationale"]
        == learner_card["current_flow"]["rationale"]
    )
    assert (
        learner_card["curriculum_progression"]["current_outcome"]["rationale"]
        == learner_card["current_flow"]["rationale"]
    )
    assert (
        learner_card["curriculum_progression"]
        == summary_payload["curriculum_progression"]
    )
    assert learner_card["current_flow"] == summary_payload["current_flow"]


def test_teacher_classroom_preserves_deferred_target_next_outcome_priority(
    client, app_settings
):
    student_id = uuid4()

    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id),
    )
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify fraction equivalence"),
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
        "/api/knowledge-components/KC-9",
        json=build_knowledge_component(
            "KC-9",
            outcome_id="LO-9",
            name="Recognize unrelated fraction patterns",
        ),
    )
    client.put(
        "/api/curriculum/outcomes/CURR-0",
        json=build_outcome(
            "CURR-0",
            title="Unrelated Fraction Extension",
            knowledge_component_ids=["KC-9"],
        ),
    )
    client.put(
        "/api/curriculum/outcomes/CURR-1",
        json=build_outcome(
            "CURR-1",
            title="Equivalent Fraction Foundations",
            knowledge_component_ids=["KC-1"],
        ),
    )
    client.put(
        "/api/curriculum/outcomes/CURR-2",
        json=build_outcome(
            "CURR-2",
            title="Equivalent Fraction Practice",
            knowledge_component_ids=["KC-2"],
        ),
    )

    generate_response = client.post(
        "/api/problems/generate",
        json={
            "student_id": str(student_id),
            "learning_session_id": "teacher-classroom-deferred-target-session",
            "target_kc_ids": ["KC-2"],
            "target_lo_ids": ["LO-1"],
            "curriculum_context": ["Equivalent fractions"],
        },
    )
    client.put(
        "/api/teachers/sections/CLASS-DEFERRED",
        json=build_classroom(
            section_id="CLASS-DEFERRED",
            title="Deferred Target Classroom",
        ),
    )
    _seed_api_user(
        app_settings.database_path,
        api_key=None,
        role="learner",
        user_id="deferred-learner",
        learner_id=str(student_id),
        section_ids=["CLASS-DEFERRED"],
    )

    classroom_response = client.get("/api/teachers/sections/CLASS-DEFERRED")
    summary_response = client.get(f"/api/learners/{student_id}/summary")

    assert generate_response.status_code == 200
    assert classroom_response.status_code == 200
    assert summary_response.status_code == 200

    learner_card = classroom_response.json()["learners"][0]
    summary_payload = summary_response.json()

    assert (
        learner_card["curriculum_progression"]["current_outcome"]["outcome_id"]
        == "CURR-1"
    )
    assert (
        learner_card["curriculum_progression"]["next_outcome"]["outcome_id"] == "CURR-2"
    )
    assert (
        learner_card["curriculum_progression"]["ready_outcomes"][0]["outcome_id"]
        == "CURR-2"
    )
    assert (
        learner_card["curriculum_progression"]["ready_outcomes"][1]["outcome_id"]
        == "CURR-0"
    )
    assert (
        learner_card["curriculum_progression"]
        == summary_payload["curriculum_progression"]
    )


def test_teacher_classroom_not_found_returns_machine_readable_error(client):
    response = client.get("/api/teachers/sections/missing-classroom")

    assert_machine_readable_error(
        response,
        status_code=404,
        code="section_not_found",
        detail="Section not found.",
    )


def test_teacher_classroom_filters_access_by_teacher_membership(tmp_path):
    app, db_path = _make_authenticated_app(tmp_path)
    _seed_api_user(
        db_path,
        api_key="admin-key",
        role="admin",
        user_id="admin-user",
    )

    with TestClient(app) as client:
        admin_headers = {"X-API-Key": "admin-key"}
        client.put(
            "/api/teachers/sections/CLS-A",
            headers=admin_headers,
            json=build_classroom(section_id="CLS-A", title="Algebra A"),
        )
        client.put(
            "/api/teachers/sections/CLS-B",
            headers=admin_headers,
            json=build_classroom(section_id="CLS-B", title="Geometry B"),
        )
        create_teacher = client.post(
            "/api/users",
            headers=admin_headers,
            json={
                "display_name": "Ms. Smith",
                "role": "teacher",
                "section_ids": ["CLS-A"],
            },
        )
        teacher_headers = {"X-API-Key": create_teacher.json()["credential"]}

        list_response = client.get("/api/teachers/sections", headers=teacher_headers)
        allowed_response = client.get(
            "/api/teachers/sections/CLS-A",
            headers=teacher_headers,
        )
        blocked_response = client.get(
            "/api/teachers/sections/CLS-B",
            headers=teacher_headers,
        )

    assert create_teacher.status_code == 200
    assert list_response.status_code == 200
    assert allowed_response.status_code == 200
    assert_machine_readable_error(
        blocked_response,
        status_code=404,
        code="section_not_found",
        detail="Section not found.",
    )
    assert [classroom["section_id"] for classroom in list_response.json()] == ["CLS-A"]
    assert list_response.json()[0]["teacher_label"] == "Ms. Smith"


def test_teacher_classroom_resolves_learners_from_user_enrollments(client):
    student_id = uuid4()

    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id),
    )
    client.put(
        "/api/teachers/sections/CLASS-ENROLLED",
        json=build_classroom(
            section_id="CLASS-ENROLLED",
            title="Enrollment Driven Classroom",
        ),
    )
    create_learner = client.post(
        "/api/users",
        json={
            "display_name": "Alice Student",
            "role": "learner",
            "learner_id": str(student_id),
            "section_ids": ["CLASS-ENROLLED"],
        },
    )

    classroom_response = client.get("/api/teachers/sections/CLASS-ENROLLED")
    trends_response = client.get("/api/teachers/sections/CLASS-ENROLLED/mastery-trends")

    assert create_learner.status_code == 200
    assert classroom_response.status_code == 200
    assert trends_response.status_code == 200

    classroom_payload = classroom_response.json()
    trends_payload = trends_response.json()

    assert classroom_payload["learner_count"] == 1
    assert classroom_payload["learners"][0]["student_id"] == str(student_id)
    assert trends_payload["learner_count"] == 1
    assert trends_payload["learner_trends"][0]["student_id"] == str(student_id)
