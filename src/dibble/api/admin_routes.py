from __future__ import annotations

from fastapi import APIRouter

from dibble.api.common import ApiContext
from dibble.models.admin import (
    SystemConfigResponse,
    SystemConfigUpdateRequest,
    SystemConfigUpdateResponse,
)


def build_admin_router(context: ApiContext) -> APIRouter:
    router = APIRouter(
        prefix="/api/admin",
        dependencies=context.deps("admin"),
    )

    @router.get("/config", response_model=SystemConfigResponse)
    def get_system_config() -> SystemConfigResponse:
        return context.services.admin_config_service.get_config()

    @router.put("/config", response_model=SystemConfigUpdateResponse)
    def update_system_config(
        payload: SystemConfigUpdateRequest,
    ) -> SystemConfigUpdateResponse:
        return context.services.admin_config_service.update_config(payload)

    return router
