from __future__ import annotations

import tomllib
from pathlib import Path

from dibble.config import Settings
from dibble.models.admin import SystemConfigUpdateRequest
from dibble.services.admin_config import AdminConfigService


def test_get_config_returns_current_settings(tmp_path: Path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "dibble.db"),
        llm_api_base="https://api.moonshot.ai/v1",
        llm_api_key="sk-test",
        llm_model="kimi-k2.5",
        auth_enabled=True,
    )

    service = AdminConfigService(settings)
    config = service.get_config()

    assert config.config_path.endswith(".dibble/config.toml")
    assert config.values.llm_api_base == "https://api.moonshot.ai/v1"
    assert config.values.llm_model == "kimi-k2.5"
    assert config.values.auth_enabled is True


def _make_update_request(**overrides):
    """Build a SystemConfigUpdateRequest with sensible defaults."""
    defaults = dict(
        app_name="Dibble Adaptive Platform",
        app_version="0.3.0",
        database_path="/tmp/dibble.db",
        router_plugin="dibble.plugins.defaults.router:build",
        retriever_plugin="dibble.plugins.defaults.retriever:build",
        provider_plugin="dibble.plugins.defaults.provider:build",
        validator_plugin="dibble.plugins.defaults.validator:build",
        llm_api_base="https://api.openai.com/v1",
        llm_timeout_seconds=20.0,
        llm_allow_mock_fallback=True,
        llm_circuit_breaker_threshold=2,
        llm_circuit_breaker_cooldown_seconds=30.0,
        llm_selection_strategy="ordered",
        prompt_library_version="1.0",
        prompt_experiment_enabled=False,
        prompt_adaptive_selection_enabled=False,
        embedding_api_base="https://api.openai.com/v1",
        embedding_dimensions=256,
        embedding_timeout_seconds=15.0,
        embedding_allow_local_fallback=True,
        auth_enabled=False,
        auth_token_issuer="dibble",
        auth_token_ttl_seconds=3600,
        auth_refresh_ttl_seconds=604800,
        generation_cache_ttl_seconds=3600,
        predictive_warm_inline_process_limit=2,
        llm_debug_prompts_enabled=False,
        telemetry_level="off",
    )
    defaults.update(overrides)
    return SystemConfigUpdateRequest(**defaults)


def test_update_config_writes_provided_values(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[llm]",
                'api_base = "https://api.openai.com/v1"',
                'api_key = "sk-old"',
                'model = "gpt-4o"',
                "[embedding]",
                'api_key = "embed-old"',
                'model = "text-embedding-3-small"',
            ]
        )
        + "\n"
    )

    import dibble.services.admin_config as mod

    original = mod.write_config_toml

    def patched_write(updates: dict, **kw: object) -> Path:
        return original(updates, path=config_path)

    monkeypatch.setattr(mod, "write_config_toml", patched_write)

    service = AdminConfigService(Settings(database_path=str(tmp_path / "dibble.db")))
    response = service.update_config(
        _make_update_request(
            database_path=str(tmp_path / "dibble.db"),
            llm_api_base="https://api.moonshot.ai/v1",
            llm_api_key="sk-new",
            llm_model="kimi-k2.5",
            llm_allow_mock_fallback=False,
        )
    )

    assert response.status == "ok"

    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    assert raw["llm"]["api_key"] == "sk-new"
    assert raw["llm"]["model"] == "kimi-k2.5"
    assert raw["llm"]["api_base"] == "https://api.moonshot.ai/v1"


def test_update_config_preserves_existing_when_none(tmp_path: Path, monkeypatch) -> None:
    """None-valued optional fields must NOT delete existing TOML keys."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[llm]",
                'api_base = "https://api.openai.com/v1"',
                'api_key = "sk-real-key"',
                'model = "gpt-4o"',
                "[embedding]",
                'api_key = "embed-key"',
                'model = "text-embedding-3-small"',
            ]
        )
        + "\n"
    )

    import dibble.services.admin_config as mod

    original = mod.write_config_toml

    def patched_write(updates: dict, **kw: object) -> Path:
        return original(updates, path=config_path)

    monkeypatch.setattr(mod, "write_config_toml", patched_write)

    service = AdminConfigService(Settings(database_path=str(tmp_path / "dibble.db")))
    # Send update with None for optional fields — they should be preserved
    response = service.update_config(
        _make_update_request(
            database_path=str(tmp_path / "dibble.db"),
            llm_api_key=None,
            llm_model=None,
            embedding_api_key=None,
            embedding_model=None,
        )
    )

    assert response.status == "ok"

    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    # Existing values must survive a None update
    assert raw["llm"]["api_key"] == "sk-real-key"
    assert raw["llm"]["model"] == "gpt-4o"
    assert raw["embedding"]["api_key"] == "embed-key"
    assert raw["embedding"]["model"] == "text-embedding-3-small"


def test_update_config_does_not_persist_unrelated_runtime_values(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[llm]",
                'api_key = "toml-key"',
                'model = "toml-model"',
            ]
        )
        + "\n"
    )

    import dibble.services.admin_config as mod

    original = mod.write_config_toml

    def patched_write(updates: dict, **kw: object) -> Path:
        return original(updates, path=config_path)

    monkeypatch.setattr(mod, "write_config_toml", patched_write)

    service = AdminConfigService(
        Settings(
            database_path=str(tmp_path / "dibble.db"),
            llm_api_key="env-key",
            llm_model="env-model",
        )
    )
    response = service.update_config(SystemConfigUpdateRequest(auth_enabled=True))

    assert response.status == "ok"

    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    assert raw["llm"]["api_key"] == "toml-key"
    assert raw["llm"]["model"] == "toml-model"
    assert raw["auth"]["enabled"] is True
