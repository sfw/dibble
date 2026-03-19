from __future__ import annotations

from fastapi import APIRouter, Depends

from dibble.api.common import ApiContext, api_error
from dibble.models.setup import (
    CreateInitialAdminRequest,
    CreateInitialAdminResponse,
    SetupConfigureRequest,
    SetupConfigureResponse,
    SetupModelCatalogRequest,
    SetupModelCatalogResponse,
    SetupStatus,
)


def build_setup_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api/setup")

    @router.get("/status", response_model=SetupStatus)
    def get_setup_status() -> SetupStatus:
        return context.services.setup_config_service.get_status()

    def _admin_guard() -> list[Depends]:
        if context.services.auth_service.enabled:
            return context.deps("admin")
        return []

    @router.post(
        "/configure",
        response_model=SetupConfigureResponse,
        dependencies=_admin_guard(),
    )
    def configure(payload: SetupConfigureRequest) -> SetupConfigureResponse:
        return context.services.setup_config_service.write_config(payload)

    @router.post(
        "/models",
        response_model=SetupModelCatalogResponse,
        dependencies=_admin_guard(),
    )
    def list_models(
        payload: SetupModelCatalogRequest,
    ) -> SetupModelCatalogResponse:
        return context.services.setup_model_catalog_service.list_models(payload)

    @router.post("/admin", response_model=CreateInitialAdminResponse)
    def create_initial_admin(
        payload: CreateInitialAdminRequest,
    ) -> CreateInitialAdminResponse:
        try:
            return context.services.setup_config_service.create_initial_admin(payload)
        except RuntimeError as exc:
            raise api_error(
                status_code=409,
                detail=str(exc),
                code="setup_admin_exists",
            ) from exc

    return router
