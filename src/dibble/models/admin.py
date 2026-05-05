from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SystemConfigValues(BaseModel):
    app_name: str
    app_version: str
    database_path: str
    router_plugin: str
    retriever_plugin: str
    provider_plugin: str
    validator_plugin: str
    llm_api_base: str
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None
    llm_thinking_enabled: bool | None = None
    llm_response_format_json: bool
    llm_allow_mock_fallback: bool
    llm_secondary_api_base: str | None = None
    llm_secondary_api_key: str | None = None
    llm_secondary_model: str | None = None
    llm_secondary_timeout_seconds: float | None = None
    llm_circuit_breaker_threshold: int
    llm_circuit_breaker_cooldown_seconds: float
    llm_retry_backoff_seconds: float
    llm_retry_attempts: int
    llm_selection_strategy: str
    prompt_library_version: str
    prompt_experiment_enabled: bool
    prompt_adaptive_selection_enabled: bool
    prompt_variant_override: str | None = None
    embedding_api_base: str
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int
    embedding_timeout_seconds: float
    embedding_allow_local_fallback: bool
    auth_enabled: bool
    auth_token_secret: str | None = None
    auth_token_issuer: str
    auth_token_ttl_seconds: int
    auth_refresh_ttl_seconds: int
    generation_cache_ttl_seconds: int
    predictive_warm_inline_process_limit: int
    llm_debug_prompts_enabled: bool
    telemetry_level: Literal["off", "normal", "debug"]


class SystemConfigResponse(BaseModel):
    config_path: str
    config_file_exists: bool
    values: SystemConfigValues


class SystemConfigUpdateRequest(BaseModel):
    app_name: str | None = None
    app_version: str | None = None
    database_path: str | None = None
    router_plugin: str | None = None
    retriever_plugin: str | None = None
    provider_plugin: str | None = None
    validator_plugin: str | None = None
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float | None = None
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None
    llm_thinking_enabled: bool | None = None
    llm_response_format_json: bool | None = None
    llm_allow_mock_fallback: bool | None = None
    llm_secondary_api_base: str | None = None
    llm_secondary_api_key: str | None = None
    llm_secondary_model: str | None = None
    llm_secondary_timeout_seconds: float | None = None
    llm_circuit_breaker_threshold: int | None = None
    llm_circuit_breaker_cooldown_seconds: float | None = None
    llm_retry_backoff_seconds: float | None = None
    llm_retry_attempts: int | None = None
    llm_selection_strategy: str | None = None
    prompt_library_version: str | None = None
    prompt_experiment_enabled: bool | None = None
    prompt_adaptive_selection_enabled: bool | None = None
    prompt_variant_override: str | None = None
    embedding_api_base: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    embedding_timeout_seconds: float | None = None
    embedding_allow_local_fallback: bool | None = None
    auth_enabled: bool | None = None
    auth_token_secret: str | None = None
    auth_token_issuer: str | None = None
    auth_token_ttl_seconds: int | None = None
    auth_refresh_ttl_seconds: int | None = None
    generation_cache_ttl_seconds: int | None = None
    predictive_warm_inline_process_limit: int | None = None
    llm_debug_prompts_enabled: bool | None = None
    telemetry_level: Literal["off", "normal", "debug"] | None = None


class SystemConfigUpdateResponse(BaseModel):
    status: Literal["ok"]
    config_path: str
    restart_required: bool
