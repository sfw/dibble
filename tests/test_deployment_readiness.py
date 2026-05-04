from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from scripts.container_healthcheck import readiness_is_acceptable


def _frontend_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "frontend-dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><title>Dibble</title><div id="root"></div>'
    )
    (assets / "app.js").write_text("console.log('dibble')")
    return dist


def test_ready_reports_setup_required_for_first_run(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            Settings(
                database_path=str(tmp_path / "dibble.db"),
                deployment_mode="household_container",
            )
        )
    )

    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "setup_required"
    assert data["deployment_mode"] == "household_container"
    assert data["configured"] is False
    assert data["has_admin_user"] is False
    assert any(check["key"] == "database" for check in data["checks"])
    assert (
        "Configure a real LLM provider before running pilot learners."
        in data["next_steps"]
    )
    assert readiness_is_acceptable(data) is False


def test_ready_reports_ready_for_configured_household_runtime(tmp_path: Path) -> None:
    dist = _frontend_dist(tmp_path)
    client = TestClient(
        create_app(
            Settings(
                database_path=str(tmp_path / "data" / "dibble.db"),
                deployment_mode="household_container",
                frontend_dist_path=str(dist),
                llm_api_key="sk-real",
                llm_model="gpt-4o",
                auth_enabled=True,
                auth_token_secret="secret",
                telemetry_level="normal",
            )
        )
    )
    admin = client.post("/api/setup/admin", json={"display_name": "Operator"})

    response = client.get("/ready")

    assert admin.status_code == 200
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["configured"] is True
    assert data["has_admin_user"] is True
    assert data["frontend_dist_path"] == str(dist)
    assert {check["status"] for check in data["checks"]} == {"pass"}
    assert readiness_is_acceptable(data) is True


def test_backend_serves_bundled_frontend_when_dist_path_is_configured(
    tmp_path: Path,
) -> None:
    dist = _frontend_dist(tmp_path)
    client = TestClient(
        create_app(
            Settings(
                database_path=str(tmp_path / "dibble.db"),
                frontend_dist_path=str(dist),
            )
        )
    )

    root = client.get("/")
    spa_route = client.get("/parent")
    asset = client.get("/assets/app.js")
    api = client.get("/api/setup/status")

    assert root.status_code == 200
    assert "Dibble" in root.text
    assert spa_route.status_code == 200
    assert "Dibble" in spa_route.text
    assert asset.status_code == 200
    assert "console.log" in asset.text
    assert api.status_code == 200
    assert "configured" in api.json()
