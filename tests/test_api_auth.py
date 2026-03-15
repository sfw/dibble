from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings

from tests.support import build_profile


def test_auth_can_protect_api_endpoints(tmp_path, student_id):
    settings = Settings(
        database_path=str(tmp_path / "dibble-auth.db"),
        auth_enabled=True,
        auth_principals=("secret-key:admin-user:admin",),
    )
    app = create_app(settings)

    with TestClient(app) as client:
        health_response = client.get("/health")
        unauthorized = client.get("/api/learners")
        authorized = client.put(
            f"/api/learners/{student_id}/profile",
            headers={"X-API-Key": "secret-key"},
            json=build_profile(student_id),
        )
        audit_response = client.get("/api/audit/events", headers={"X-API-Key": "secret-key"})

    assert health_response.status_code == 200
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["event_type"] == "auth.request"
    assert audit_response.json()[0]["status"] == "denied"


def test_auth_exposes_identity_and_rbac(tmp_path, student_id):
    settings = Settings(
        database_path=str(tmp_path / "dibble-rbac.db"),
        auth_enabled=True,
        auth_principals=(
            "viewer-key:viewer-user:viewer",
            "editor-key:editor-user:editor",
            "admin-key:admin-user:admin",
        ),
    )
    app = create_app(settings)

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
        forbidden_audit = client.get("/api/audit/events", headers={"X-API-Key": "editor-key"})
        allowed_audit = client.get("/api/audit/events", headers={"X-API-Key": "admin-key"})

    assert me_response.status_code == 200
    assert me_response.json()["principal_id"] == "viewer-user"
    assert me_response.json()["role"] == "viewer"
    assert forbidden_write.status_code == 403
    assert allowed_write.status_code == 200
    assert forbidden_audit.status_code == 403
    assert allowed_audit.status_code == 200


def test_auth_can_issue_and_accept_bearer_tokens(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "dibble-token.db"),
        auth_enabled=True,
        auth_principals=("editor-key:editor-user:editor",),
        auth_token_secret="super-secret",
        auth_token_ttl_seconds=900,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token_response = client.post("/api/auth/token", headers={"X-API-Key": "editor-key"})
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
        )

    assert token_response.status_code == 200
    assert token_response.json()["token_type"] == "bearer"
    assert token_response.json()["identity"]["principal_id"] == "editor-user"
    assert me_response.status_code == 200
    assert me_response.json()["auth_scheme"] == "bearer"
    assert me_response.json()["principal_id"] == "editor-user"


def test_refresh_rotates_tokens_and_old_refresh_token_stops_working(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "dibble-refresh.db"),
        auth_enabled=True,
        auth_principals=("editor-key:editor-user:editor",),
        auth_token_secret="super-secret",
        auth_token_ttl_seconds=900,
        auth_refresh_ttl_seconds=1800,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        issued = client.post("/api/auth/token", headers={"X-API-Key": "editor-key"}).json()
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
    assert stale_refresh.status_code == 401


def test_revocation_invalidates_existing_bearer_session(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "dibble-revoke.db"),
        auth_enabled=True,
        auth_principals=("editor-key:editor-user:editor",),
        auth_token_secret="super-secret",
        auth_token_ttl_seconds=900,
        auth_refresh_ttl_seconds=1800,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        issued = client.post("/api/auth/token", headers={"X-API-Key": "editor-key"}).json()
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
    assert me_response.status_code == 401
