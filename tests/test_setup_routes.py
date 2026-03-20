from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from dibble.app import create_app
from dibble.config import Settings


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

    def test_status_does_not_rewrite_live_config_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        config_dir = tmp_path / ".dibble"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config.toml"
        original_text = "\n".join(
            [
                "[llm]",
                'api_base = "https://api.moonshot.ai/v1"',
                'api_key = "sk-real"',
                'model = "kimi-k2.5"',
                "",
            ]
        )
        config_path.write_text(original_text)

        client = TestClient(create_app())

        response = client.get("/api/setup/status")

        assert response.status_code == 200
        assert config_path.read_text() == original_text
        assert (config_dir / "config.backup.toml").is_file()


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

    def test_configure_rejects_already_configured_backend(self, tmp_path) -> None:
        client = TestClient(
            create_app(
                Settings(
                    database_path=str(tmp_path / "dibble.db"),
                    llm_api_key="already-set",
                )
            )
        )

        response = client.post("/api/setup/configure", json={"llm_model": "gpt-4o"})

        assert response.status_code == 409
        assert response.json()["code"] == "setup_already_configured"

    def test_configure_rejects_when_runtime_settings_loader_is_configured(
        self, tmp_path
    ) -> None:
        startup_settings = Settings(database_path=str(tmp_path / "dibble.db"))
        runtime_settings = Settings(
            database_path=str(tmp_path / "dibble.db"),
            llm_api_key="live-key",
            llm_model="kimi-k2.5",
        )
        client = TestClient(
            create_app(
                startup_settings,
                settings_loader=lambda: runtime_settings,
            )
        )

        response = client.post("/api/setup/configure", json={"llm_model": "gpt-4o"})

        assert response.status_code == 409
        assert response.json()["code"] == "setup_already_configured"


class TestSetupModels:
    def test_list_models(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from dibble.models.setup import SetupModelCatalogResponse
        from dibble.services.setup_model_catalog import SetupModelCatalogService

        def fake_list_models(self, payload):
            return SetupModelCatalogResponse(
                models=["gpt-4o", "text-embedding-3-small"]
            )

        monkeypatch.setattr(
            SetupModelCatalogService,
            "list_models",
            fake_list_models,
        )

        response = client.post(
            "/api/setup/models",
            json={
                "api_base": "https://api.example.com/v1",
                "api_key": "sk-test",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"models": ["gpt-4o", "text-embedding-3-small"]}
