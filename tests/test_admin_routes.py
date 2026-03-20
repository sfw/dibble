from __future__ import annotations

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

from tests.support import assert_machine_readable_error


def _seed_user(db_path: str, *, api_key: str, role: str) -> None:
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id=str(uuid4()),
            display_name=f"{role.title()} User",
            role=role,
            api_key_hash=hash_credential(api_key),
            created_at=now,
            updated_at=now,
        )
    )


def _make_client(tmp_path) -> tuple[TestClient, str]:
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    app = create_app(
        Settings(
            database_path=db_path,
            auth_enabled=True,
            auth_token_secret="super-secret",
            llm_api_key="sk-test",
            llm_model="gpt-4o",
        )
    )
    return TestClient(app), db_path


def test_admin_config_requires_admin_role(tmp_path) -> None:
    client, db_path = _make_client(tmp_path)
    _seed_user(db_path, api_key="viewer-key", role="viewer")

    with client:
        response = client.get(
            "/api/admin/config",
            headers={"X-API-Key": "viewer-key"},
        )

    assert_machine_readable_error(
        response,
        status_code=403,
        code="auth_insufficient_role",
        detail="Your role does not allow access to this endpoint.",
    )


def test_admin_can_read_and_write_config(tmp_path, monkeypatch) -> None:
    client, db_path = _make_client(tmp_path)
    _seed_user(db_path, api_key="admin-key", role="admin")
    config_path = tmp_path / "config.toml"

    import dibble.services.admin_config as mod

    original = mod.write_config_toml

    def patched_write(updates: dict, **kw: object):
        return original(updates, path=config_path)

    monkeypatch.setattr(mod, "write_config_toml", patched_write)

    with client:
        read_response = client.get(
            "/api/admin/config",
            headers={"X-API-Key": "admin-key"},
        )
        write_response = client.put(
            "/api/admin/config",
            headers={"X-API-Key": "admin-key"},
            json={
                **read_response.json()["values"],
                "llm_model": "kimi-k2.5",
            },
        )

    assert read_response.status_code == 200
    assert read_response.json()["values"]["llm_model"] == "gpt-4o"
    assert write_response.status_code == 200
    assert write_response.json()["restart_required"] is True
