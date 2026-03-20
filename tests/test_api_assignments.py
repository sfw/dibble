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


def _make_authenticated_app(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    return create_app(settings), db_path


def _seed_user(
    db_path: str,
    *,
    api_key: str,
    role: str,
    user_id: str,
) -> None:
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id=user_id,
            role=role,
            api_key_hash=hash_credential(api_key),
            created_at=now,
            updated_at=now,
        )
    )


def test_assignment_routes_use_authenticated_principal_id_for_teacher_identity(
    tmp_path,
):
    app, db_path = _make_authenticated_app(tmp_path)
    _seed_user(
        db_path,
        api_key="teacher-key",
        role="teacher",
        user_id="teacher-user-1",
    )

    with TestClient(app) as client:
        headers = {"X-API-Key": "teacher-key"}
        student_id = str(uuid4())
        create_response = client.post(
            "/api/assignments",
            headers=headers,
            json={
                "student_id": student_id,
                "section_id": "CLS-A",
                "title": "Equivalent Fractions Practice",
            },
        )
        list_response = client.get("/api/teachers/assignments", headers=headers)

    assert create_response.status_code == 201
    assert create_response.json()["teacher_id"] == "teacher-user-1"
    assert list_response.status_code == 200
    assert [item["teacher_id"] for item in list_response.json()["items"]] == [
        "teacher-user-1"
    ]
