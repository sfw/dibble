from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from dibble.api.common import build_api_error_response
from dibble.api.routes import build_router
from dibble.bootstrap import build_application_services
from dibble.config import Settings, get_settings
from dibble.services.runtime_telemetry import (
    RuntimeTelemetryMiddleware,
    setup_runtime_telemetry,
)


def create_app(
    settings: Settings | None = None,
    *,
    settings_loader: Callable[[], Settings] | None = None,
) -> FastAPI:
    if settings is None:
        settings_loader = settings_loader or get_settings
        settings = settings_loader()
    elif settings_loader is None:

        def _current_settings() -> Settings:
            return settings

        settings_loader = _current_settings
    setup_runtime_telemetry(settings)
    services = build_application_services(settings, settings_loader=settings_loader)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Foundational revised-spec backend for adaptive learner profiling and content generation.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RuntimeTelemetryMiddleware, settings=settings)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_, exc: HTTPException):
        return build_api_error_response(exc)

    app.include_router(build_router(services))
    _mount_static_frontend(app, settings)
    return app


def _mount_static_frontend(app: FastAPI, settings: Settings) -> None:
    if not settings.frontend_dist_path:
        return
    dist_path = Path(settings.frontend_dist_path)
    index_path = dist_path / "index.html"
    if not index_path.is_file():
        return

    reserved_prefixes = {"api"}
    reserved_paths = {
        "docs",
        "health",
        "openapi.json",
        "ready",
        "redoc",
    }

    @app.get("/", include_in_schema=False)
    async def serve_frontend_root():
        return FileResponse(index_path)

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def serve_frontend(frontend_path: str):
        first_segment = frontend_path.split("/", 1)[0]
        if first_segment in reserved_prefixes or frontend_path in reserved_paths:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (dist_path / frontend_path).resolve()
        try:
            candidate.relative_to(dist_path.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)
