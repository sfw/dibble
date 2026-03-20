from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.services.auth import hash_credential
from dibble.services.sqlite_connection import create_connection
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database

from tests.support import assert_machine_readable_error, build_section


def _make_app(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    return create_app(settings), db_path


def _seed_admin(db_path: str) -> None:
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id="admin-user",
            display_name="Admin User",
            role="admin",
            api_key_hash=hash_credential("admin-key"),
            section_ids=[],
            created_at=now,
            updated_at=now,
        )
    )


def test_admin_can_manage_courses_and_sections(tmp_path):
    app, db_path = _make_app(tmp_path)
    _seed_admin(db_path)
    student_id = uuid4()

    with TestClient(app) as client:
        headers = {"X-API-Key": "admin-key"}
        upsert_course = client.put(
            "/api/admin/courses/MATH-5",
            headers=headers,
            json={
                "course_id": "MATH-5",
                "title": "Grade 5 Mathematics",
                "subject": "math",
                "grade_band": "5",
                "tags": ["fractions"],
            },
        )
        upsert_section = client.put(
            "/api/admin/sections/SEC-5A",
            headers=headers,
            json=build_section(
                section_id="SEC-5A",
                course_id="MATH-5",
                title="Grade 5A",
            ),
        )
        client.post(
            "/api/users",
            headers=headers,
            json={
                "display_name": "Ms. Rivera",
                "role": "teacher",
                "section_ids": ["SEC-5A"],
            },
        )
        client.post(
            "/api/users",
            headers=headers,
            json={
                "display_name": "Ava Learner",
                "role": "learner",
                "learner_id": str(student_id),
                "section_ids": ["SEC-5A"],
            },
        )
        courses_response = client.get("/api/admin/courses", headers=headers)
        sections_response = client.get("/api/admin/sections", headers=headers)

    assert upsert_course.status_code == 200
    assert upsert_section.status_code == 200
    assert courses_response.status_code == 200
    assert sections_response.status_code == 200

    course_payload = courses_response.json()
    section_payload = sections_response.json()

    assert course_payload == [
        {
            "course_id": "MATH-5",
            "title": "Grade 5 Mathematics",
            "subject": "math",
            "grade_band": "5",
            "curriculum_package_id": None,
            "tags": ["fractions"],
            "updated_at": course_payload[0]["updated_at"],
            "section_count": 1,
        }
    ]
    assert section_payload[0]["section_id"] == "SEC-5A"
    assert section_payload[0]["course_id"] == "MATH-5"
    assert section_payload[0]["course_title"] == "Grade 5 Mathematics"
    assert section_payload[0]["teacher_count"] == 1
    assert section_payload[0]["learner_count"] == 1


def test_admin_section_requires_existing_course(tmp_path):
    app, db_path = _make_app(tmp_path)
    _seed_admin(db_path)

    with TestClient(app) as client:
        response = client.put(
            "/api/admin/sections/SEC-404",
            headers={"X-API-Key": "admin-key"},
            json=build_section(
                section_id="SEC-404",
                course_id="MISSING-COURSE",
                title="Orphan Section",
            ),
        )

    assert_machine_readable_error(
        response,
        status_code=400,
        code="section_course_not_found",
        detail="Course MISSING-COURSE does not exist.",
    )


def test_admin_can_manage_section_memberships(tmp_path):
    app, db_path = _make_app(tmp_path)
    _seed_admin(db_path)
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id="teacher-1",
            display_name="Ms. Rivera",
            role="teacher",
            api_key_hash=hash_credential("teacher-key"),
            section_ids=[],
            created_at=now,
            updated_at=now,
        )
    )
    store.create(
        User(
            user_id="learner-1",
            display_name="Ava Learner",
            role="learner",
            passphrase_hash=hash_credential("correct horse battery staple"),
            learner_id="learner-ava",
            section_ids=[],
            created_at=now,
            updated_at=now,
        )
    )

    with TestClient(app) as client:
        headers = {"X-API-Key": "admin-key"}
        client.put(
            "/api/admin/courses/MATH-5",
            headers=headers,
            json={
                "course_id": "MATH-5",
                "title": "Grade 5 Mathematics",
            },
        )
        client.put(
            "/api/admin/sections/SEC-5A",
            headers=headers,
            json=build_section(
                section_id="SEC-5A",
                course_id="MATH-5",
                title="Grade 5A",
            ),
        )

        update_response = client.put(
            "/api/admin/sections/SEC-5A/memberships",
            headers=headers,
            json={
                "teacher_user_ids": ["teacher-1"],
                "learner_user_ids": ["learner-1"],
            },
        )
        get_response = client.get(
            "/api/admin/sections/SEC-5A/memberships",
            headers=headers,
        )
        teacher_user = client.get("/api/users/teacher-1", headers=headers)
        learner_user = client.get("/api/users/learner-1", headers=headers)

    assert update_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json() == {
        "section_id": "SEC-5A",
        "teachers": [
            {
                "user_id": "teacher-1",
                "display_name": "Ms. Rivera",
            }
        ],
        "learners": [
            {
                "user_id": "learner-1",
                "display_name": "Ava Learner",
            }
        ],
    }
    assert teacher_user.json()["section_ids"] == ["SEC-5A"]
    assert learner_user.json()["section_ids"] == ["SEC-5A"]


def test_admin_section_memberships_validate_user_roles(tmp_path):
    app, db_path = _make_app(tmp_path)
    _seed_admin(db_path)
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id="viewer-1",
            display_name="Observer",
            role="viewer",
            api_key_hash=hash_credential("viewer-key"),
            section_ids=[],
            created_at=now,
            updated_at=now,
        )
    )

    with TestClient(app) as client:
        headers = {"X-API-Key": "admin-key"}
        client.put(
            "/api/admin/courses/MATH-5",
            headers=headers,
            json={
                "course_id": "MATH-5",
                "title": "Grade 5 Mathematics",
            },
        )
        client.put(
            "/api/admin/sections/SEC-5A",
            headers=headers,
            json=build_section(
                section_id="SEC-5A",
                course_id="MATH-5",
                title="Grade 5A",
            ),
        )
        response = client.put(
            "/api/admin/sections/SEC-5A/memberships",
            headers=headers,
            json={
                "teacher_user_ids": ["viewer-1"],
                "learner_user_ids": [],
            },
        )

    assert_machine_readable_error(
        response,
        status_code=400,
        code="section_membership_role_mismatch",
        detail="User viewer-1 must have role teacher, found viewer.",
    )
