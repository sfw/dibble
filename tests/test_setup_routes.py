from __future__ import annotations

from fastapi.testclient import TestClient


class TestSetupStatus:
    def test_returns_status(self, client: TestClient) -> None:
        response = client.get("/api/setup/status")
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "has_llm_key" in data
        assert "app_version" in data

    def test_unconfigured_by_default(self, client: TestClient) -> None:
        response = client.get("/api/setup/status")
        data = response.json()
        assert data["configured"] is False
        assert data["has_llm_key"] is False


class TestHealthIncludesConfigured:
    def test_health_has_configured_field(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "configured" in data


class TestSetupConfigure:
    def test_configure_writes_config(
        self, client: TestClient, tmp_path: object
    ) -> None:
        response = client.post(
            "/api/setup/configure",
            json={"llm_api_key": "sk-test", "llm_model": "gpt-4o"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["restart_required"] is True
        assert "config_path" in data

    def test_configure_empty_body(self, client: TestClient) -> None:
        response = client.post("/api/setup/configure", json={})
        assert response.status_code == 200
