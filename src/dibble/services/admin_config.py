from __future__ import annotations

from dataclasses import asdict

from dibble.config import Settings, dibble_dir, write_config_toml
from dibble.models.admin import (
    SystemConfigResponse,
    SystemConfigUpdateRequest,
    SystemConfigUpdateResponse,
    SystemConfigValues,
)


class AdminConfigService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_config(self) -> SystemConfigResponse:
        config_path = dibble_dir() / "config.toml"
        return SystemConfigResponse(
            config_path=str(config_path),
            config_file_exists=config_path.is_file(),
            values=SystemConfigValues(**asdict(self._settings)),
        )

    def update_config(
        self, request: SystemConfigUpdateRequest
    ) -> SystemConfigUpdateResponse:
        path = write_config_toml(request.model_dump())
        return SystemConfigUpdateResponse(
            status="ok",
            config_path=str(path),
            restart_required=True,
        )
