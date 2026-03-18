from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from dibble.config import Settings
from dibble.models.setup import CreateInitialAdminRequest, SetupConfigureRequest
from dibble.services.auth import hash_credential
from dibble.services.setup_config import SetupConfigService
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database


def _make_service(
    tmp_path: Path,
    *,
    llm_api_key: str | None = None,
    with_db: bool = False,
) -> tuple[SetupConfigService, SQLiteUserStore]:
    db_path = str(tmp_path / "dibble.db")
    if with_db:
        ensure_database(db_path)
    settings = Settings(
        database_path=db_path,
        llm_api_key=llm_api_key,
    )
    user_store = SQLiteUserStore(db_path) if with_db else SQLiteUserStore(db_path)
    if with_db:
        service = SetupConfigService(settings, user_store=user_store)
    else:
        service = SetupConfigService(settings)
    return service, user_store


class TestGetStatus:
    def test_unconfigured(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "nonexistent.db")
        ensure_database(db_path)
        settings = Settings(database_path=db_path)
        user_store = SQLiteUserStore(db_path)
        service = SetupConfigService(settings, user_store=user_store)
        status = service.get_status()
        assert status.configured is False
        assert status.has_llm_key is False
        assert status.has_admin_user is False

    def test_configured(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "dibble.db")
        ensure_database(db_path)
        Path(db_path).touch()
        settings = Settings(
            database_path=db_path,
            llm_api_key="sk-test-123",
        )
        user_store = SQLiteUserStore(db_path)
        service = SetupConfigService(settings, user_store=user_store)
        status = service.get_status()
        assert status.configured is True
        assert status.has_llm_key is True
        assert status.has_database is True
        assert status.has_admin_user is False
        assert status.llm_api_base == "https://api.openai.com/v1"
        assert status.app_version == settings.app_version

    def test_embedding_key_reported(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "dibble.db")
        ensure_database(db_path)
        settings = Settings(
            database_path=db_path,
            embedding_api_key="embed-key",
        )
        service = SetupConfigService(settings, user_store=SQLiteUserStore(db_path))
        status = service.get_status()
        assert status.has_embedding_key is True


class TestWriteConfig:
    def test_writes_toml(self, tmp_path: Path, monkeypatch: object) -> None:
        config_path = tmp_path / ".dibble" / "config.toml"
        config_path.parent.mkdir(parents=True)

        settings = Settings()
        service = SetupConfigService(settings)

        import dibble.services.setup_config as mod

        original = mod.write_config_toml

        def patched_write(updates: dict, **kw: object) -> Path:
            return original(updates, path=config_path)

        mod.write_config_toml = patched_write  # type: ignore[assignment]
        try:
            request = SetupConfigureRequest(
                llm_api_key="sk-new",
                llm_model="gpt-4o",
            )
            response = service.write_config(request)
            assert response.status == "ok"
            assert response.restart_required is True

            with config_path.open("rb") as fh:
                raw = tomllib.load(fh)
            assert raw["llm"]["api_key"] == "sk-new"
            assert raw["llm"]["model"] == "gpt-4o"
        finally:
            mod.write_config_toml = original  # type: ignore[assignment]

    def test_excludes_none_fields(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.toml"

        settings = Settings()
        service = SetupConfigService(settings)

        import dibble.services.setup_config as mod

        original = mod.write_config_toml

        def patched_write(updates: dict, **kw: object) -> Path:
            return original(updates, path=config_path)

        mod.write_config_toml = patched_write  # type: ignore[assignment]
        try:
            request = SetupConfigureRequest(llm_api_key="sk-only")
            service.write_config(request)

            with config_path.open("rb") as fh:
                raw = tomllib.load(fh)
            assert raw == {"llm": {"api_key": "sk-only"}}
        finally:
            mod.write_config_toml = original  # type: ignore[assignment]


class TestCreateInitialAdmin:
    def test_creates_admin(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "dibble.db")
        ensure_database(db_path)
        user_store = SQLiteUserStore(db_path)
        service = SetupConfigService(
            Settings(database_path=db_path), user_store=user_store
        )

        result = service.create_initial_admin(
            CreateInitialAdminRequest(display_name="Root Admin")
        )
        assert result.role == "admin"
        assert result.display_name == "Root Admin"
        assert result.api_key  # plaintext key returned

        # Verify the user was persisted
        user = user_store.get(result.user_id)
        assert user is not None
        assert user.role == "admin"
        assert user.api_key_hash == hash_credential(result.api_key)

        # Verify status reflects admin exists
        status = service.get_status()
        assert status.has_admin_user is True

    def test_rejects_second_admin(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "dibble.db")
        ensure_database(db_path)
        user_store = SQLiteUserStore(db_path)
        service = SetupConfigService(
            Settings(database_path=db_path), user_store=user_store
        )

        service.create_initial_admin(CreateInitialAdminRequest())
        with pytest.raises(RuntimeError, match="already exists"):
            service.create_initial_admin(CreateInitialAdminRequest())
