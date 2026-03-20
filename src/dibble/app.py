from __future__ import annotations

import logging
from time import monotonic

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from dibble.api.common import build_api_error_response
from dibble.api.routes import build_router
from dibble.bootstrap import build_application_services
from dibble.config import Settings, get_settings
from dibble.services.runtime_telemetry import (
    bind_runtime_telemetry,
    duration_ms,
    extract_request_payload,
    log_runtime_event,
    request_summary,
    reset_runtime_telemetry,
    resolve_request_session_id,
    response_summary,
    scrub_payload,
    setup_runtime_telemetry,
    telemetry_debug_enabled,
)

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_runtime_telemetry(settings)
    services = build_application_services(settings)

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

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_, exc: HTTPException):
        return build_api_error_response(exc)

    @app.middleware("http")
    async def attach_runtime_telemetry(request, call_next):
        body, payload = await extract_request_payload(request)
        del body
        session_id = resolve_request_session_id(request, payload)
        tokens = bind_runtime_telemetry(
            session_id=session_id,
            telemetry_level=settings.telemetry_level,
        )
        started_at = monotonic()
        try:
            log_runtime_event(
                logger,
                logging.INFO,
                "request.started",
                **request_summary(request),
            )
            if telemetry_debug_enabled():
                log_runtime_event(
                    logger,
                    logging.DEBUG,
                    "request.payload",
                    payload=scrub_payload(payload),
                )
            response = await call_next(request)
            log_runtime_event(
                logger,
                logging.INFO,
                "request.completed",
                **request_summary(request),
                **response_summary(
                    status_code=response.status_code,
                    duration_ms=duration_ms(started_at),
                    content_type=response.headers.get("content-type"),
                ),
            )
            return response
        except Exception:
            log_runtime_event(
                logger,
                logging.ERROR,
                "request.failed",
                **request_summary(request),
                duration_ms=duration_ms(started_at),
            )
            logger.exception("Unhandled application exception")
            raise
        finally:
            reset_runtime_telemetry(tokens)

    app.include_router(build_router(services))
    return app
