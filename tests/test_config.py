from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from dibble.config import (
    _flatten_toml,
    _load_toml_config,
    _unflatten_to_toml,
    get_settings,
    write_config_toml,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_defaults_no_toml_no_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no TOML and no env vars, database_path resolves to ~/.dibble/dibble.db."""
        # Clear all DIBBLE_ env vars
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        settings = get_settings(config_path=tmp_path / "nonexistent.toml")
        assert settings.database_path.endswith(".dibble/dibble.db")
        assert settings.app_name == "Dibble Adaptive Platform"
        assert settings.llm_api_base == "https://api.openai.com/v1"
        assert settings.auth_enabled is False
        assert settings.telemetry_level == "off"

    def test_default_database_path_is_absolute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)
        settings = get_settings(config_path=tmp_path / "nonexistent.toml")
        assert Path(settings.database_path).is_absolute()


# ---------------------------------------------------------------------------
# TOML loading
# ---------------------------------------------------------------------------


class TestTomlLoading:
    def test_toml_overrides_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[llm]
model = "gpt-4o"
api_key = "sk-test-123"
timeout_seconds = 45.0
""",
        )
        settings = get_settings(config_path=path)
        assert settings.llm_model == "gpt-4o"
        assert settings.llm_api_key == "sk-test-123"
        assert settings.llm_timeout_seconds == 45.0

    def test_toml_plugins_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[plugins]
router = "my.custom.router:build"
retriever = "my.custom.retriever:build"
""",
        )
        settings = get_settings(config_path=path)
        assert settings.router_plugin == "my.custom.router:build"
        assert settings.retriever_plugin == "my.custom.retriever:build"
        # Unset plugins keep defaults
        assert settings.provider_plugin == "dibble.plugins.defaults.provider:build"

    def test_toml_auth_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[auth]
enabled = true
token_secret = "my-secret"
""",
        )
        settings = get_settings(config_path=path)
        assert settings.auth_enabled is True
        assert settings.auth_token_secret == "my-secret"

    def test_toml_secondary_llm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[llm.secondary]
api_base = "https://api.anthropic.com/v1"
model = "claude-sonnet"
timeout_seconds = 30.0
""",
        )
        settings = get_settings(config_path=path)
        assert settings.llm_secondary_api_base == "https://api.anthropic.com/v1"
        assert settings.llm_secondary_model == "claude-sonnet"
        assert settings.llm_secondary_timeout_seconds == 30.0

    def test_toml_cache_and_performance(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[cache]
generation_cache_ttl_seconds = 7200

[performance]
predictive_warm_inline_process_limit = 5
""",
        )
        settings = get_settings(config_path=path)
        assert settings.generation_cache_ttl_seconds == 7200
        assert settings.predictive_warm_inline_process_limit == 5

    def test_toml_telemetry_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[telemetry]
level = "debug"
""",
        )
        settings = get_settings(config_path=path)
        assert settings.telemetry_level == "debug"

    def test_toml_top_level_database_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(tmp_path, 'database_path = "/opt/dibble/data.db"')
        settings = get_settings(config_path=path)
        assert settings.database_path == "/opt/dibble/data.db"

    def test_toml_top_level_frontend_dist_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(tmp_path, 'frontend_dist_path = "~/dibble-dist"')
        settings = get_settings(config_path=path)
        assert settings.frontend_dist_path is not None
        assert "~" not in settings.frontend_dist_path
        assert settings.frontend_dist_path.endswith("/dibble-dist")

    def test_toml_tilde_expansion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(tmp_path, 'database_path = "~/data/test.db"')
        settings = get_settings(config_path=path)
        assert "~" not in settings.database_path
        assert settings.database_path.endswith("/data/test.db")
        assert Path(settings.database_path).is_absolute()

    def test_missing_toml_file_returns_empty(self, tmp_path: Path) -> None:
        result = _load_toml_config(tmp_path / "does-not-exist.toml")
        assert result == {}

    def test_malformed_toml_raises(self, tmp_path: Path) -> None:
        path = _write_toml(tmp_path, "this is not [valid toml =")
        with pytest.raises(Exception):
            _load_toml_config(path)

    def test_invalid_telemetry_level_raises(self, tmp_path: Path) -> None:
        path = _write_toml(
            tmp_path,
            """
[telemetry]
level = "verbose"
""",
        )
        with pytest.raises(ValueError, match="telemetry_level"):
            get_settings(config_path=path)

    def test_load_restores_backup_when_live_config_has_placeholder_key(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = _write_toml(
            tmp_path,
            """
[llm]
api_key = "sk-test"
model = "gpt-4o"
""",
        )
        backup_path = tmp_path / "config.backup.toml"
        backup_path.write_text(
            """
[llm]
api_key = "sk-real"
model = "kimi-k2.5"
"""
        )

        with caplog.at_level("WARNING"):
            loaded = _load_toml_config(path)

        assert loaded["llm_api_key"] == "sk-real"
        assert loaded["llm_model"] == "kimi-k2.5"
        assert "restoring backup" in caplog.text
        assert 'api_key = "sk-real"' in path.read_text()

    def test_load_writes_backup_for_non_placeholder_config(
        self, tmp_path: Path
    ) -> None:
        path = _write_toml(
            tmp_path,
            """
[llm]
api_key = "sk-real"
model = "kimi-k2.5"
""",
        )

        loaded = _load_toml_config(path)

        assert loaded["llm_api_key"] == "sk-real"
        backup_path = tmp_path / "config.backup.toml"
        assert backup_path.is_file()
        assert 'api_key = "sk-real"' in backup_path.read_text()


# ---------------------------------------------------------------------------
# Env overrides TOML
# ---------------------------------------------------------------------------


class TestEnvOverridesToml:
    def test_env_wins_over_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[llm]
model = "from-toml"
api_key = "toml-key"
""",
        )
        monkeypatch.setenv("DIBBLE_LLM_MODEL", "from-env")
        settings = get_settings(config_path=path)
        assert settings.llm_model == "from-env"
        # Non-overridden TOML value still applies
        assert settings.llm_api_key == "toml-key"

    def test_env_bool_wins_over_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[auth]
enabled = true
""",
        )
        monkeypatch.setenv("DIBBLE_AUTH_ENABLED", "false")
        settings = get_settings(config_path=path)
        assert settings.auth_enabled is False

    def test_env_int_wins_over_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[auth]
token_ttl_seconds = 1800
""",
        )
        monkeypatch.setenv("DIBBLE_AUTH_TOKEN_TTL_SECONDS", "900")
        settings = get_settings(config_path=path)
        assert settings.auth_token_ttl_seconds == 900


# ---------------------------------------------------------------------------
# Embedding API key fallback
# ---------------------------------------------------------------------------


class TestEmbeddingFallback:
    def test_embedding_key_falls_back_to_llm_key_from_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[llm]
api_key = "llm-key-123"
""",
        )
        settings = get_settings(config_path=path)
        assert settings.embedding_api_key == "llm-key-123"

    def test_embedding_key_explicit_overrides_llm_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[llm]
api_key = "llm-key"

[embedding]
api_key = "embed-key"
""",
        )
        settings = get_settings(config_path=path)
        assert settings.embedding_api_key == "embed-key"

    def test_embedding_key_falls_back_to_llm_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        monkeypatch.setenv("DIBBLE_LLM_API_KEY", "env-llm-key")
        settings = get_settings(config_path=tmp_path / "nonexistent.toml")
        # env sets llm_api_key; embedding should not inherit automatically
        # because DIBBLE_EMBEDDING_API_KEY is not set — but the fallback logic
        # checks merged llm_api_key
        assert settings.embedding_api_key == "env-llm-key"


# ---------------------------------------------------------------------------
# config_path=None skips TOML
# ---------------------------------------------------------------------------


class TestConfigPathNone:
    def test_config_path_none_skips_toml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        settings = get_settings(config_path=None)
        assert settings.app_name == "Dibble Adaptive Platform"


# ---------------------------------------------------------------------------
# Flatten logic
# ---------------------------------------------------------------------------


class TestFlatten:
    def test_flatten_all_sections(self) -> None:
        raw = {
            "database_path": "/tmp/test.db",
            "plugins": {"router": "a:b"},
            "llm": {
                "model": "gpt-4",
                "secondary": {"model": "claude"},
            },
            "prompts": {"library_version": "2.0"},
            "embedding": {"dimensions": 512},
            "auth": {"enabled": True},
            "telemetry": {"level": "normal"},
            "cache": {"generation_cache_ttl_seconds": 999},
            "performance": {"predictive_warm_inline_process_limit": 10},
        }
        flat = _flatten_toml(raw)
        assert flat["database_path"] == "/tmp/test.db"
        assert flat["router_plugin"] == "a:b"
        assert flat["llm_model"] == "gpt-4"
        assert flat["llm_secondary_model"] == "claude"
        assert flat["prompt_library_version"] == "2.0"
        assert flat["embedding_dimensions"] == 512
        assert flat["auth_enabled"] is True
        assert flat["telemetry_level"] == "normal"
        assert flat["generation_cache_ttl_seconds"] == 999
        assert flat["predictive_warm_inline_process_limit"] == 10


# ---------------------------------------------------------------------------
# Permission warning
# ---------------------------------------------------------------------------


class TestPermissions:
    @pytest.mark.skipif(
        os.name == "nt", reason="POSIX permissions not applicable on Windows"
    )
    def test_world_readable_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = _write_toml(tmp_path, '[llm]\nmodel = "test"')
        path.chmod(0o644)  # world-readable
        with caplog.at_level("WARNING"):
            _load_toml_config(path)
        assert "world-readable" in caplog.text


# ---------------------------------------------------------------------------
# Prompts section
# ---------------------------------------------------------------------------


class TestPromptsSection:
    def test_prompts_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in list(os.environ):
            if key.startswith("DIBBLE_"):
                monkeypatch.delenv(key)

        path = _write_toml(
            tmp_path,
            """
[prompts]
library_version = "2.0"
experiment_enabled = true
adaptive_selection_enabled = true
""",
        )
        settings = get_settings(config_path=path)
        assert settings.prompt_library_version == "2.0"
        assert settings.prompt_experiment_enabled is True
        assert settings.prompt_adaptive_selection_enabled is True


# ---------------------------------------------------------------------------
# Unflatten (inverse of flatten)
# ---------------------------------------------------------------------------


class TestUnflatten:
    def test_llm_fields(self) -> None:
        flat = {"llm_api_key": "sk-123", "llm_model": "gpt-4o"}
        result = _unflatten_to_toml(flat)
        assert result == {"llm": {"api_key": "sk-123", "model": "gpt-4o"}}

    def test_plugin_fields(self) -> None:
        flat = {"router_plugin": "my.router:build"}
        result = _unflatten_to_toml(flat)
        assert result == {"plugins": {"router": "my.router:build"}}

    def test_secondary_llm(self) -> None:
        flat = {"llm_secondary_model": "claude", "llm_secondary_api_base": "https://x"}
        result = _unflatten_to_toml(flat)
        assert result == {
            "llm": {"secondary": {"model": "claude", "api_base": "https://x"}}
        }

    def test_top_level_field(self) -> None:
        flat = {"database_path": "/tmp/db"}
        result = _unflatten_to_toml(flat)
        assert result == {"database_path": "/tmp/db"}

    def test_auth_fields_unflatten(self) -> None:
        flat = {"auth_enabled": True, "auth_token_secret": "secret"}
        result = _unflatten_to_toml(flat)
        assert result == {"auth": {"enabled": True, "token_secret": "secret"}}

    def test_telemetry_fields_unflatten(self) -> None:
        flat = {"telemetry_level": "debug"}
        result = _unflatten_to_toml(flat)
        assert result == {"telemetry": {"level": "debug"}}

    def test_round_trip_flatten_unflatten(self) -> None:
        raw = {
            "database_path": "/tmp/test.db",
            "plugins": {"router": "a:b"},
            "llm": {"model": "gpt-4", "api_key": "sk-x"},
            "embedding": {"dimensions": 512},
            "auth": {"enabled": True},
        }
        flat = _flatten_toml(raw)
        reconstructed = _unflatten_to_toml(flat)
        # Re-flatten to verify equivalence
        assert _flatten_toml(reconstructed) == flat


# ---------------------------------------------------------------------------
# Write config TOML
# ---------------------------------------------------------------------------


class TestWriteConfigToml:
    def test_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        result = write_config_toml({"llm_api_key": "sk-test"}, path=path)
        assert result == path
        assert path.is_file()
        # Verify readable
        settings = get_settings(config_path=path)
        assert settings.llm_api_key == "sk-test"

    def test_merges_existing(self, tmp_path: Path) -> None:
        path = _write_toml(tmp_path, '[llm]\nmodel = "gpt-4o"\n')
        write_config_toml({"llm_api_key": "sk-new"}, path=path)
        settings = get_settings(config_path=path)
        assert settings.llm_model == "gpt-4o"
        assert settings.llm_api_key == "sk-new"

    @pytest.mark.skipif(
        os.name == "nt", reason="POSIX permissions not applicable on Windows"
    )
    def test_sets_permissions(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        write_config_toml({"llm_api_key": "sk-test"}, path=path)
        mode = path.stat().st_mode
        assert not (mode & stat.S_IROTH)
        assert not (mode & stat.S_IWOTH)
        assert not (mode & stat.S_IRGRP)

    def test_overwrites_value(self, tmp_path: Path) -> None:
        path = _write_toml(tmp_path, '[llm]\napi_key = "old"\n')
        write_config_toml({"llm_api_key": "new"}, path=path)
        settings = get_settings(config_path=path)
        assert settings.llm_api_key == "new"
