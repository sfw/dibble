from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import HTTPException

from dibble.api.common import build_api_error_response
from dibble.api.routes import build_router
from dibble.bootstrap import build_application_services
from dibble.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    services = build_application_services(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Foundational revised-spec backend for adaptive learner profiling and content generation.",
    )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_, exc: HTTPException):
        return build_api_error_response(exc)

    app.include_router(build_router(services))
    return app
