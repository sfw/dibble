from __future__ import annotations

from collections.abc import Callable
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dibble.config import Settings, dibble_dir, write_config_toml
from dibble.models.auth import User
from dibble.models.setup import (
    CreateInitialAdminRequest,
    CreateInitialAdminResponse,
    SetupConfigureRequest,
    SetupConfigureResponse,
    SetupStatus,
)
from dibble.services.auth import hash_credential
from dibble.services.protocols import UserStore
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
