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

from tests.support import assert_machine_readable_error, build_profile


def _seed_user(
    db_path: str,
    *,
    api_key: str,
    role: str,
    user_id: str | None = None,
    learner_id: str | None = None,
    display_name: str | None = None,
    section_ids: list[str] | None = None,
) -> User:
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    user = User(
        user_id=user_id or str(uuid4()),
        display_name=display_name,
        role=role,
        api_key_hash=hash_credential(api_key),
        learner_id=learner_id,
        section_ids=section_ids or [],
        created_at=now,
        updated_at=now,
    )
    return store.create(user)


def _make_app(tmp_path, *, token_secret=None, token_ttl=None, refresh_ttl=None):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    settings = Settings(
        database_path=db_path,
        auth_enabled=True,
        auth_token_secret=token_secret,
        auth_token_ttl_seconds=token_ttl or 3600,
        auth_refresh_ttl_seconds=refresh_ttl or 604800,
    )
    return create_app(settings), db_path


def test_auth_can_protect_api_endpoints(tmp_path, student_id):
    app, db_path = _make_app(tmp_path)
    _seed_user(db_path, api_key="secret-key", role="admin")

    with TestClient(app) as client:
        health_response = client.get("/health")
        unauthorized = client.get("/api/learners")
        authorized = client.put(
            f"/api/learners/{student_id}/profile",
            headers={"X-API-Key": "secret-key"},
            json=build_profile(student_id),
        )
        audit_response = client.get(
            "/api/audit/events", headers={"X-API-Key": "secret-key"}
        )

    assert health_response.status_code == 200
    assert_machine_readable_error(
        unauthorized,
        status_code=401,
        code="auth_invalid_credentials",
        detail="A credential is required for this endpoint.",
    )
    assert unauthorized.headers["www-authenticate"] == "Bearer"
    assert authorized.status_code == 200
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["event_type"] == "auth.request"
    assert audit_response.json()[0]["status"] == "denied"


def test_auth_exposes_identity_and_rbac(tmp_path, student_id):
    app, db_path = _make_app(tmp_path)
    _seed_user(db_path, api_key="viewer-key", role="viewer", user_id="viewer-user")
    _seed_user(db_path, api_key="editor-key", role="editor", user_id="editor-user")
    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-user")

    with TestClient(app) as client:
        me_response = client.get("/api/auth/me", headers={"X-API-Key": "viewer-key"})
        forbidden_write = client.put(
            f"/api/learners/{student_id}/profile",
            headers={"X-API-Key": "viewer-key"},
            json=build_profile(student_id),
        )
        allowed_write = client.put(
            f"/api/learners/{student_id}/profile",
            headers={"X-API-Key": "editor-key"},
            json=build_profile(student_id),
        )
        forbidden_audit = client.get(
            "/api/audit/events", headers={"X-API-Key": "editor-key"}
        )
        allowed_audit = client.get(
            "/api/audit/events", headers={"X-API-Key": "admin-key"}
        )

    assert me_response.status_code == 200
    assert me_response.json()["principal_id"] == "viewer-user"
    assert me_response.json()["role"] == "viewer"
    assert_machine_readable_error(
        forbidden_write,
        status_code=403,
        code="auth_insufficient_role",
        detail="Your role does not allow access to this endpoint.",
    )
    assert allowed_write.status_code == 200
    assert_machine_readable_error(
        forbidden_audit,
        status_code=403,
        code="auth_insufficient_role",
        detail="Your role does not allow access to this endpoint.",
    )
    assert allowed_audit.status_code == 200


def test_auth_can_issue_and_accept_bearer_tokens(tmp_path):
    app, db_path = _make_app(tmp_path, token_secret="super-secret", token_ttl=900)
    _seed_user(db_path, api_key="editor-key", role="editor", user_id="editor-user")

    with TestClient(app) as client:
        token_response = client.post(
            "/api/auth/token", headers={"X-API-Key": "editor-key"}
        )
        me_response = client.get(
            "/api/auth/me",
            headers={
                "Authorization": f"Bearer {token_response.json()['access_token']}"
            },
        )

    assert token_response.status_code == 200
    assert token_response.json()["token_type"] == "bearer"
    assert token_response.json()["identity"]["principal_id"] == "editor-user"
    assert me_response.status_code == 200
    assert me_response.json()["auth_scheme"] == "bearer"
    assert me_response.json()["principal_id"] == "editor-user"


def test_auth_token_endpoint_returns_503_without_token_secret(tmp_path):
    app, db_path = _make_app(tmp_path, token_secret=None)
    _seed_user(db_path, api_key="editor-key", role="editor", user_id="editor-user")

    with TestClient(app) as client:
        response = client.post("/api/auth/token", headers={"X-API-Key": "editor-key"})

    assert_machine_readable_error(
        response,
        status_code=503,
        code="auth_token_unavailable",
        detail="Bearer token issuance requires DIBBLE_AUTH_TOKEN_SECRET.",
    )


def test_bearer_token_forbidden_response_preserves_identity_and_error_contract(
    tmp_path, student_id
):
    app, db_path = _make_app(tmp_path, token_secret="super-secret", token_ttl=900)
    _seed_user(db_path, api_key="viewer-key", role="viewer", user_id="viewer-user")
    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-user")

    with TestClient(app) as client:
        viewer_token = client.post(
            "/api/auth/token", headers={"X-API-Key": "viewer-key"}
        ).json()["access_token"]
        forbidden_write = client.put(
            f"/api/learners/{student_id}/profile",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json=build_profile(student_id),
        )
        audit_response = client.get(
            "/api/audit/events", headers={"X-API-Key": "admin-key"}
        )

    assert_machine_readable_error(
        forbidden_write,
        status_code=403,
        code="auth_insufficient_role",
        detail="Your role does not allow access to this endpoint.",
    )
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["event_type"] == "auth.request"
    assert audit_response.json()[0]["status"] == "forbidden"
    assert audit_response.json()[0]["payload"]["principal_id"] == "viewer-user"
    assert audit_response.json()[0]["payload"]["role"] == "viewer"


def test_refresh_rotates_tokens_and_old_refresh_token_stops_working(tmp_path):
    app, db_path = _make_app(
        tmp_path, token_secret="super-secret", token_ttl=900, refresh_ttl=1800
    )
    _seed_user(db_path, api_key="editor-key", role="editor", user_id="editor-user")

    with TestClient(app) as client:
        issued = client.post(
            "/api/auth/token", headers={"X-API-Key": "editor-key"}
        ).json()
        refreshed = client.post(
            "/api/auth/token/refresh",
            json={"refresh_token": issued["refresh_token"]},
        )
        stale_refresh = client.post(
            "/api/auth/token/refresh",
            json={"refresh_token": issued["refresh_token"]},
        )

    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != issued["refresh_token"]
    assert_machine_readable_error(
        stale_refresh,
        status_code=401,
        code="auth_refresh_failed",
        detail="Refresh token is no longer active.",
    )
    assert stale_refresh.headers["www-authenticate"] == "Bearer"


def test_revocation_invalidates_existing_bearer_session(tmp_path):
    app, db_path = _make_app(
        tmp_path, token_secret="super-secret", token_ttl=900, refresh_ttl=1800
    )
    _seed_user(db_path, api_key="editor-key", role="editor", user_id="editor-user")

    with TestClient(app) as client:
        issued = client.post(
            "/api/auth/token", headers={"X-API-Key": "editor-key"}
        ).json()
        revoke = client.post(
            "/api/auth/token/revoke",
            headers={"Authorization": f"Bearer {issued['access_token']}"},
            json={},
        )
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {issued['access_token']}"},
        )

    assert revoke.status_code == 200
    assert_machine_readable_error(
        me_response,
        status_code=401,
        code="auth_invalid_credentials",
        detail="Session has been revoked.",
    )
    assert me_response.headers["www-authenticate"] == "Bearer"


def test_learner_principal_carries_entity_binding(tmp_path, student_id):
    app, db_path = _make_app(tmp_path)
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-1",
        learner_id=str(student_id),
        display_name="Alice Student",
    )
    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-user")

    with TestClient(app) as client:
        me_response = client.get("/api/auth/me", headers={"X-API-Key": "learner-key"})

    assert me_response.status_code == 200
    identity = me_response.json()
    assert identity["principal_id"] == "learner-1"
    assert identity["role"] == "learner"
    assert identity["learner_id"] == str(student_id)
    assert identity["display_name"] == "Alice Student"


def test_teacher_principal_carries_display_binding(tmp_path):
    app, db_path = _make_app(tmp_path)
    _seed_user(
        db_path,
        api_key="teacher-key",
        role="teacher",
        user_id="teacher-1",
        display_name="Ms. Smith",
        section_ids=["CLS-A", "CLS-B"],
    )
    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-user")

    with TestClient(app) as client:
        me_response = client.get("/api/auth/me", headers={"X-API-Key": "teacher-key"})

    assert me_response.status_code == 200
    identity = me_response.json()
    assert identity["principal_id"] == "teacher-1"
    assert identity["role"] == "teacher"
    assert identity["display_name"] == "Ms. Smith"
    assert identity["learner_id"] is None


def test_learner_role_can_read_but_not_write(tmp_path, student_id):
    app, db_path = _make_app(tmp_path)
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-1",
        learner_id=str(student_id),
        display_name="Alice",
    )
    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-user")

    with TestClient(app) as client:
        read_response = client.get(
            "/api/learners", headers={"X-API-Key": "learner-key"}
        )
        write_response = client.put(
            f"/api/learners/{student_id}/profile",
            headers={"X-API-Key": "learner-key"},
            json=build_profile(student_id),
        )

    assert read_response.status_code == 200
    assert_machine_readable_error(
        write_response,
        status_code=403,
        code="auth_insufficient_role",
    )


def test_teacher_role_can_read_and_write(tmp_path, student_id):
    app, db_path = _make_app(tmp_path)
    _seed_user(
        db_path,
        api_key="teacher-key",
        role="teacher",
        user_id="teacher-1",
        display_name="Ms. Smith",
        section_ids=["CLS-A"],
    )

    with TestClient(app) as client:
        read_response = client.get(
            "/api/learners", headers={"X-API-Key": "teacher-key"}
        )
        write_response = client.put(
            f"/api/learners/{student_id}/profile",
            headers={"X-API-Key": "teacher-key"},
            json=build_profile(student_id),
        )

    assert read_response.status_code == 200
    assert write_response.status_code == 200


def test_bearer_token_preserves_entity_bindings(tmp_path, student_id):
    app, db_path = _make_app(tmp_path, token_secret="super-secret", token_ttl=900)
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-1",
        learner_id=str(student_id),
        display_name="Alice Student",
    )

    with TestClient(app) as client:
        token_response = client.post(
            "/api/auth/token", headers={"X-API-Key": "learner-key"}
        )
        access_token = token_response.json()["access_token"]
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert token_response.status_code == 200
    token_identity = token_response.json()["identity"]
    assert token_identity["learner_id"] == str(student_id)
    assert token_identity["display_name"] == "Alice Student"

    assert me_response.status_code == 200
    me_identity = me_response.json()
    assert me_identity["learner_id"] == str(student_id)
    assert me_identity["display_name"] == "Alice Student"
    assert me_identity["auth_scheme"] == "bearer"


def test_refresh_preserves_entity_bindings(tmp_path, student_id):
    app, db_path = _make_app(tmp_path, token_secret="super-secret", token_ttl=900)
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-1",
        learner_id=str(student_id),
        display_name="Alice",
    )

    with TestClient(app) as client:
        issued = client.post(
            "/api/auth/token", headers={"X-API-Key": "learner-key"}
        ).json()
        refreshed = client.post(
            "/api/auth/token/refresh",
            json={"refresh_token": issued["refresh_token"]},
        )

    assert refreshed.status_code == 200
    refreshed_identity = refreshed.json()["identity"]
    assert refreshed_identity["learner_id"] == str(student_id)
    assert refreshed_identity["display_name"] == "Alice"


def test_existing_roles_still_work_without_entity_binding(tmp_path, student_id):
    app, db_path = _make_app(tmp_path)
    _seed_user(db_path, api_key="viewer-key", role="viewer", user_id="viewer-user")
    _seed_user(db_path, api_key="editor-key", role="editor", user_id="editor-user")
    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-user")

    with TestClient(app) as client:
        viewer_me = client.get(
            "/api/auth/me", headers={"X-API-Key": "viewer-key"}
        ).json()
        editor_me = client.get(
            "/api/auth/me", headers={"X-API-Key": "editor-key"}
        ).json()
        admin_me = client.get("/api/auth/me", headers={"X-API-Key": "admin-key"}).json()

    assert viewer_me["role"] == "viewer"
    assert viewer_me["learner_id"] is None
    assert editor_me["role"] == "editor"
    assert admin_me["role"] == "admin"
