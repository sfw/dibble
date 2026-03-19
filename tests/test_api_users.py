from datetime import datetime, timezone

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.models.classroom_membership import ClassroomMembershipRole
from dibble.services.auth import hash_credential
from dibble.services.classroom_membership_store import SQLiteClassroomMembershipStore
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database


def _make_app(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    return create_app(settings), db_path


def _seed_admin(db_path: str) -> None:
    store = SQLiteUserStore(db_path)
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


def test_user_endpoints_derive_sections_from_membership_store(tmp_path):
    app, db_path = _make_app(tmp_path)
    _seed_admin(db_path)
    user_store = SQLiteUserStore(db_path)
    membership_store = SQLiteClassroomMembershipStore(db_path)
    now = datetime.now(timezone.utc).isoformat()
    user_store.create(
        User(
            user_id="teacher-1",
            display_name="Ms. Rivera",
            role="teacher",
            api_key_hash=hash_credential("teacher-key"),
            section_ids=["STALE-SECTION"],
            created_at=now,
            updated_at=now,
        )
    )
    membership_store.replace_for_user(
        user_id="teacher-1",
        role=ClassroomMembershipRole.teacher,
        section_ids=["SEC-5A", "SEC-5B"],
    )

    with TestClient(app) as client:
        headers = {"X-API-Key": "admin-key"}
        list_response = client.get("/api/users", headers=headers)
        get_response = client.get("/api/users/teacher-1", headers=headers)

    assert list_response.status_code == 200
    assert get_response.status_code == 200
    assert list_response.json()[0]["section_ids"] == ["SEC-5A", "SEC-5B"]
    assert get_response.json()["section_ids"] == ["SEC-5A", "SEC-5B"]


def test_updating_user_without_section_ids_does_not_rewrite_memberships(tmp_path):
    app, db_path = _make_app(tmp_path)
    _seed_admin(db_path)
    user_store = SQLiteUserStore(db_path)
    membership_store = SQLiteClassroomMembershipStore(db_path)
    now = datetime.now(timezone.utc).isoformat()
    user_store.create(
        User(
            user_id="teacher-1",
            display_name="Ms. Rivera",
            role="teacher",
            api_key_hash=hash_credential("teacher-key"),
            section_ids=["STALE-SECTION"],
            created_at=now,
            updated_at=now,
        )
    )
    membership_store.replace_for_user(
        user_id="teacher-1",
        role=ClassroomMembershipRole.teacher,
        section_ids=["SEC-5A"],
    )

    with TestClient(app) as client:
        response = client.put(
            "/api/users/teacher-1",
            headers={"X-API-Key": "admin-key"},
            json={"display_name": "Rivera Updated"},
        )

    assert response.status_code == 200
    assert response.json()["section_ids"] == ["SEC-5A"]
    assert membership_store.list_user_section_ids(
        "teacher-1",
        role=ClassroomMembershipRole.teacher,
    ) == ["SEC-5A"]
