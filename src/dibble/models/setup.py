from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SetupStatus(BaseModel):
    configured: bool
    has_llm_key: bool
    has_embedding_key: bool
    has_database: bool
    has_admin_user: bool
    llm_api_base: str
    llm_model: str | None
    auth_enabled: bool
    config_file_exists: bool
    app_version: str


class DeploymentReadinessCheck(BaseModel):
    key: str
    status: Literal["pass", "warn", "fail"]
    summary: str
    detail: str | None = None


class DeploymentReadiness(BaseModel):
    status: Literal["ready", "setup_required", "degraded", "not_ready"]
    deployment_mode: str
    app_version: str
    configured: bool
    database_path: str
    frontend_dist_path: str | None = None
    auth_enabled: bool
    has_admin_user: bool
    cloud_library_enabled: bool
    cloud_library_endpoint_configured: bool
    mock_fallback_enabled: bool
    telemetry_level: str
    checks: list[DeploymentReadinessCheck] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class SetupConfigureRequest(BaseModel):
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    embedding_api_base: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    database_path: str | None = None


class SetupConfigureResponse(BaseModel):
    status: Literal["ok"]
    config_path: str
    restart_required: bool


class CreateInitialAdminRequest(BaseModel):
    display_name: str | None = None


class CreateInitialAdminResponse(BaseModel):
    user_id: str
    api_key: str
    display_name: str | None = None
    role: str


class SetupModelCatalogRequest(BaseModel):
    api_base: str
    api_key: str


class SetupModelCatalogResponse(BaseModel):
    models: list[str]
