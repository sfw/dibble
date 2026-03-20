from __future__ import annotations

from collections.abc import Callable
import logging
from dataclasses import asdict

from dibble.config import Settings, dibble_dir, write_config_toml
from dibble.models.admin import (
    SystemConfigResponse,
    SystemConfigUpdateRequest,
    SystemConfigUpdateResponse,
    SystemConfigValues,
)
from dibble.services.runtime_telemetry import log_runtime_event

logger = logging.getLogger(__name__)


class AdminConfigService:
    def __init__(
        self,
        settings: Settings,
        *,
        settings_loader: Callable[[], Settings] | None = None,
    ) -> None:
        self._settings = settings
        self._settings_loader = settings_loader or (lambda: settings)

    def _current_settings(self) -> Settings:
        return self._settings_loader()

    def get_config(self) -> SystemConfigResponse:
        settings = self._current_settings()
        config_path = dibble_dir() / "config.toml"
        return SystemConfigResponse(
            config_path=str(config_path),
            config_file_exists=config_path.is_file(),
            values=SystemConfigValues(**asdict(settings)),
        )

    def update_config(
        self, request: SystemConfigUpdateRequest
    ) -> SystemConfigUpdateResponse:
        updates = request.model_dump(exclude_unset=True, exclude_none=True)
        path = write_config_toml(updates)
        log_runtime_event(
            logger,
            logging.INFO,
            "config.write.admin",
            config_path=str(path),
            updated_fields=sorted(updates.keys()),
            llm_model=updates.get("llm_model"),
            llm_api_base=updates.get("llm_api_base"),
        )
        return SystemConfigUpdateResponse(
            status="ok",
            config_path=str(path),
            restart_required=True,
        )
