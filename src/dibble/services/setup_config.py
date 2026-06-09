from __future__ import annotations

from collections.abc import Callable
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dibble.config import Settings, dibble_dir, write_config_toml
from dibble.models.auth import User
from dibble.models.setup import (
    CreateInitialAdminRequest,
    CreateInitialAdminResponse,
    DeploymentReadiness,
    DeploymentReadinessCheck,
    SetupConfigureRequest,
    SetupConfigureResponse,
    SetupStatus,
)
from dibble.services.auth import hash_credential
from dibble.services.protocols import UserStore
from dibble.services.retrieval.embeddings import (
    embedder_detail,
    embedder_kind,
    local_hash_embedder_disallowed,
)
from dibble.services.runtime_telemetry import log_runtime_event

logger = logging.getLogger(__name__)


class SetupConfigService:
    def __init__(
        self,
        settings: Settings,
        *,
        user_store: UserStore | None = None,
        settings_loader: Callable[[], Settings] | None = None,
    ) -> None:
        self._settings = settings
        self._user_store = user_store
        self._settings_loader = settings_loader or (lambda: settings)

    def _current_settings(self) -> Settings:
        return self._settings_loader()

    def get_status(self) -> SetupStatus:
        s = self._current_settings()
        config_path = dibble_dir() / "config.toml"
        has_admin = self._user_store.count() > 0 if self._user_store else False
        return SetupStatus(
            configured=s.llm_api_key is not None,
            has_llm_key=s.llm_api_key is not None,
            has_embedding_key=s.embedding_api_key is not None,
            has_database=Path(s.database_path).exists(),
            has_admin_user=has_admin,
            llm_api_base=s.llm_api_base,
            llm_model=s.llm_model,
            auth_enabled=s.auth_enabled,
            config_file_exists=config_path.is_file(),
            app_version=s.app_version,
        )

    def get_deployment_readiness(self) -> DeploymentReadiness:
        s = self._current_settings()
        setup_status = self.get_status()
        database_path = Path(s.database_path)
        frontend_dist_path = (
            Path(s.frontend_dist_path) if s.frontend_dist_path else None
        )
        checks = [
            self._database_check(database_path),
            self._llm_check(s),
            self._embedder_check(s),
            self._admin_check(setup_status.has_admin_user),
            self._auth_check(s),
            self._frontend_check(frontend_dist_path),
            self._cloud_library_check(s),
            self._telemetry_check(s),
        ]
        next_steps = self._readiness_next_steps(
            settings=s,
            checks=checks,
            has_admin=setup_status.has_admin_user,
        )
        if any(check.status == "fail" for check in checks):
            status = "not_ready"
        elif not setup_status.configured or not setup_status.has_admin_user:
            status = "setup_required"
        elif any(check.status == "warn" for check in checks):
            status = "degraded"
        else:
            status = "ready"

        return DeploymentReadiness(
            status=status,
            deployment_mode=s.deployment_mode,
            app_version=s.app_version,
            configured=setup_status.configured,
            database_path=str(database_path),
            frontend_dist_path=str(frontend_dist_path) if frontend_dist_path else None,
            auth_enabled=s.auth_enabled,
            has_admin_user=setup_status.has_admin_user,
            cloud_library_enabled=s.cloud_library_enabled,
            cloud_library_endpoint_configured=bool(s.cloud_library_endpoint),
            mock_fallback_enabled=s.llm_allow_mock_fallback,
            telemetry_level=s.telemetry_level,
            checks=checks,
            next_steps=next_steps,
        )

    def write_config(self, request: SetupConfigureRequest) -> SetupConfigureResponse:
        if self._current_settings().llm_api_key is not None:
            raise RuntimeError(
                "Setup configuration is already complete. Use the system configuration endpoint for later changes."
            )
        updates = request.model_dump(exclude_none=True)
        path = write_config_toml(updates)
        log_runtime_event(
            logger,
            logging.INFO,
            "config.write.setup",
            config_path=str(path),
            updated_fields=sorted(updates.keys()),
            llm_model=updates.get("llm_model"),
            llm_api_base=updates.get("llm_api_base"),
        )
        return SetupConfigureResponse(
            status="ok",
            config_path=str(path),
            restart_required=True,
        )

    def create_initial_admin(
        self, request: CreateInitialAdminRequest
    ) -> CreateInitialAdminResponse:
        if self._user_store is None:
            raise RuntimeError("User store is not configured.")
        if self._user_store.count() > 0:
            raise RuntimeError("An admin user already exists.")

        api_key = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        user = User(
            user_id=str(uuid4()),
            display_name=request.display_name,
            role="admin",
            api_key_hash=hash_credential(api_key),
            created_at=now,
            updated_at=now,
        )
        self._user_store.create(user)
        return CreateInitialAdminResponse(
            user_id=user.user_id,
            api_key=api_key,
            display_name=user.display_name,
            role="admin",
        )

    def _database_check(self, database_path: Path) -> DeploymentReadinessCheck:
        parent = database_path.parent if database_path.parent != Path("") else Path(".")
        if not parent.exists():
            return DeploymentReadinessCheck(
                key="database",
                status="fail",
                summary="SQLite parent directory is missing.",
                detail=str(parent),
            )
        if not os.access(parent, os.W_OK):
            return DeploymentReadinessCheck(
                key="database",
                status="fail",
                summary="SQLite parent directory is not writable.",
                detail=str(parent),
            )
        if database_path.exists() and not os.access(database_path, os.W_OK):
            return DeploymentReadinessCheck(
                key="database",
                status="fail",
                summary="SQLite database exists but is not writable.",
                detail=str(database_path),
            )
        return DeploymentReadinessCheck(
            key="database",
            status="pass",
            summary="SQLite persistence is present and writable.",
            detail=str(database_path),
        )

    def _llm_check(self, settings: Settings) -> DeploymentReadinessCheck:
        if settings.llm_api_key:
            return DeploymentReadinessCheck(
                key="llm_provider",
                status="pass",
                summary="Primary LLM provider credentials are configured.",
                detail=settings.llm_model,
            )
        if settings.llm_allow_mock_fallback:
            return DeploymentReadinessCheck(
                key="llm_provider",
                status="warn",
                summary="No LLM key is configured; deterministic mock fallback is active.",
                detail="Good for first-run setup and rehearsal, not for a real pilot session.",
            )
        return DeploymentReadinessCheck(
            key="llm_provider",
            status="fail",
            summary="No LLM key is configured and mock fallback is disabled.",
            detail="Set DIBBLE_LLM_API_KEY and DIBBLE_LLM_MODEL.",
        )

    def _admin_check(self, has_admin: bool) -> DeploymentReadinessCheck:
        if has_admin:
            return DeploymentReadinessCheck(
                key="admin_user",
                status="pass",
                summary="At least one operator/admin user exists.",
            )
        return DeploymentReadinessCheck(
            key="admin_user",
            status="warn",
            summary="No operator/admin user exists yet.",
            detail="Run first-run setup and create the initial admin API key.",
        )

    def _embedder_check(self, settings: Settings) -> DeploymentReadinessCheck:
        kind = embedder_kind(settings)
        detail = embedder_detail(settings)
        if kind == "openai_compatible":
            return DeploymentReadinessCheck(
                key="embedder",
                status="pass",
                summary="A real embedding provider is configured for retrieval.",
                detail=detail,
            )
        if kind == "local_hash":
            if local_hash_embedder_disallowed(settings):
                return DeploymentReadinessCheck(
                    key="embedder",
                    status="fail",
                    summary="Local hash embeddings are active in a real-provider household runtime.",
                    detail=(
                        "Configure DIBBLE_EMBEDDING_API_KEY and DIBBLE_EMBEDDING_MODEL "
                        "before running pilot learners."
                    ),
                )
            if settings.deployment_mode == "local_dev":
                return DeploymentReadinessCheck(
                    key="embedder",
                    status="warn",
                    summary="Local hash embeddings are active.",
                    detail="Acceptable for development and lightweight rehearsal, not for high-trust retrieval quality.",
                )
            return DeploymentReadinessCheck(
                key="embedder",
                status="warn",
                summary="No real embedding provider is configured yet; local hash fallback is active.",
                detail=detail,
            )
        return DeploymentReadinessCheck(
            key="embedder",
            status="fail",
            summary="No embedding provider is configured and local fallback is disabled.",
            detail="Set DIBBLE_EMBEDDING_API_KEY and DIBBLE_EMBEDDING_MODEL, or explicitly allow local fallback only for development.",
        )

    def _auth_check(self, settings: Settings) -> DeploymentReadinessCheck:
        if not settings.auth_enabled:
            return DeploymentReadinessCheck(
                key="auth",
                status="warn",
                summary="Authentication is disabled.",
                detail="Acceptable for local development; enable auth for household pilots.",
            )
        if settings.auth_token_secret:
            return DeploymentReadinessCheck(
                key="auth",
                status="pass",
                summary="Authentication and bearer token issuance are configured.",
            )
        return DeploymentReadinessCheck(
            key="auth",
            status="warn",
            summary="Authentication is enabled, but bearer token issuance has no secret.",
            detail="API-key auth still works; set DIBBLE_AUTH_TOKEN_SECRET for browser token sessions.",
        )

    def _frontend_check(
        self, frontend_dist_path: Path | None
    ) -> DeploymentReadinessCheck:
        if frontend_dist_path is None:
            return DeploymentReadinessCheck(
                key="frontend",
                status="warn",
                summary="No bundled frontend path is configured.",
                detail="Run the Vite dev server separately, or set DIBBLE_FRONTEND_DIST_PATH.",
            )
        index_path = frontend_dist_path / "index.html"
        if not index_path.is_file():
            return DeploymentReadinessCheck(
                key="frontend",
                status="fail",
                summary="Configured frontend dist path does not contain index.html.",
                detail=str(frontend_dist_path),
            )
        return DeploymentReadinessCheck(
            key="frontend",
            status="pass",
            summary="Bundled frontend assets are available from the backend process.",
            detail=str(frontend_dist_path),
        )

    def _cloud_library_check(self, settings: Settings) -> DeploymentReadinessCheck:
        if not settings.cloud_library_enabled:
            return DeploymentReadinessCheck(
                key="cloud_library",
                status="pass",
                summary="Cloud-library remote access is disabled; local library fallback is active.",
                detail="This preserves the household privacy boundary by default.",
            )
        if settings.cloud_library_endpoint:
            return DeploymentReadinessCheck(
                key="cloud_library",
                status="pass",
                summary="Cloud-library remote access is enabled with an endpoint.",
                detail=settings.cloud_library_endpoint,
            )
        return DeploymentReadinessCheck(
            key="cloud_library",
            status="fail",
            summary="Cloud-library remote access is enabled without an endpoint.",
            detail="Set DIBBLE_CLOUD_LIBRARY_ENDPOINT or disable remote access.",
        )

    def _telemetry_check(self, settings: Settings) -> DeploymentReadinessCheck:
        if settings.telemetry_level == "off":
            return DeploymentReadinessCheck(
                key="telemetry",
                status="warn",
                summary="Runtime telemetry is off.",
                detail="Use DIBBLE_TELEMETRY_LEVEL=normal for a controlled pilot.",
            )
        return DeploymentReadinessCheck(
            key="telemetry",
            status="pass",
            summary=f"Runtime telemetry is {settings.telemetry_level}.",
        )

    def _readiness_next_steps(
        self,
        *,
        settings: Settings,
        checks: list[DeploymentReadinessCheck],
        has_admin: bool,
    ) -> list[str]:
        steps: list[str] = []
        check_by_key = {check.key: check for check in checks}
        if not settings.llm_api_key:
            steps.append("Configure a real LLM provider before running pilot learners.")
        if check_by_key["embedder"].status != "pass":
            steps.append(
                "Configure a real embedding provider before trusting retrieval-backed learner sessions."
            )
        if not has_admin:
            steps.append(
                "Create the initial admin/operator account from first-run setup."
            )
        if check_by_key["frontend"].status == "warn":
            steps.append("Use the Vite dev server or provide built frontend assets.")
        if check_by_key["frontend"].status == "fail":
            steps.append(
                "Build the frontend and point DIBBLE_FRONTEND_DIST_PATH at its dist directory."
            )
        if check_by_key["database"].status == "fail":
            steps.append("Fix the persistent database mount or directory permissions.")
        if settings.auth_enabled and not settings.auth_token_secret:
            steps.append(
                "Set DIBBLE_AUTH_TOKEN_SECRET for bearer-token browser sessions."
            )
        if not settings.auth_enabled:
            steps.append("Enable authentication before a real household pilot.")
        if settings.telemetry_level == "off":
            steps.append(
                "Enable normal telemetry for pilot support and readiness review."
            )
        return steps
