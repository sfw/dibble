from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    database_path: str = "dibble.db"
    app_name: str = "Dibble Adaptive Platform"
    app_version: str = "0.3.0"
    router_plugin: str = "dibble.plugins.defaults.router:build"
    retriever_plugin: str = "dibble.plugins.defaults.retriever:build"
    provider_plugin: str = "dibble.plugins.defaults.provider:build"
    validator_plugin: str = "dibble.plugins.defaults.validator:build"
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 20.0
    llm_allow_mock_fallback: bool = True
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int = 256
    embedding_timeout_seconds: float = 15.0
    embedding_allow_local_fallback: bool = True
    auth_enabled: bool = False
    auth_api_keys: tuple[str, ...] = ()
    auth_principals: tuple[str, ...] = ()
    auth_header_name: str = "X-API-Key"


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    return default


def _get_csv_env(name: str) -> tuple[str, ...]:
    value = os.getenv(name, "")
    return tuple(part.strip() for part in value.split(",") if part.strip())


def get_settings() -> Settings:
    return Settings(
        database_path=os.getenv("DIBBLE_DATABASE_PATH", "dibble.db"),
        router_plugin=os.getenv("DIBBLE_ROUTER_PLUGIN", "dibble.plugins.defaults.router:build"),
        retriever_plugin=os.getenv("DIBBLE_RETRIEVER_PLUGIN", "dibble.plugins.defaults.retriever:build"),
        provider_plugin=os.getenv("DIBBLE_PROVIDER_PLUGIN", "dibble.plugins.defaults.provider:build"),
        validator_plugin=os.getenv("DIBBLE_VALIDATOR_PLUGIN", "dibble.plugins.defaults.validator:build"),
        llm_api_base=os.getenv("DIBBLE_LLM_API_BASE", "https://api.openai.com/v1"),
        llm_api_key=os.getenv("DIBBLE_LLM_API_KEY"),
        llm_model=os.getenv("DIBBLE_LLM_MODEL"),
        llm_timeout_seconds=float(os.getenv("DIBBLE_LLM_TIMEOUT_SECONDS", "20.0")),
        llm_allow_mock_fallback=_get_bool_env("DIBBLE_LLM_ALLOW_MOCK_FALLBACK", True),
        embedding_api_base=os.getenv("DIBBLE_EMBEDDING_API_BASE", "https://api.openai.com/v1"),
        embedding_api_key=os.getenv("DIBBLE_EMBEDDING_API_KEY") or os.getenv("DIBBLE_LLM_API_KEY"),
        embedding_model=os.getenv("DIBBLE_EMBEDDING_MODEL"),
        embedding_dimensions=int(os.getenv("DIBBLE_EMBEDDING_DIMENSIONS", "256")),
        embedding_timeout_seconds=float(os.getenv("DIBBLE_EMBEDDING_TIMEOUT_SECONDS", "15.0")),
        embedding_allow_local_fallback=_get_bool_env("DIBBLE_EMBEDDING_ALLOW_LOCAL_FALLBACK", True),
        auth_enabled=_get_bool_env("DIBBLE_AUTH_ENABLED", False),
        auth_api_keys=_get_csv_env("DIBBLE_AUTH_API_KEYS"),
        auth_principals=_get_csv_env("DIBBLE_AUTH_PRINCIPALS"),
        auth_header_name=os.getenv("DIBBLE_AUTH_HEADER_NAME", "X-API-Key"),
    )
