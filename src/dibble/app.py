from __future__ import annotations

from fastapi import FastAPI

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
    app.include_router(
        build_router(
            services.profile_store,
            services.curriculum_store,
            services.knowledge_component_store,
            services.audit_store,
            services.observation_store,
            services.auth_service,
            services.telemetry_service,
            services.router_plugin,
            services.generation_engine,
            services.content_warmer,
            services.remediation_planner,
            services.socratic_assessment_service,
            services.socratic_session_store,
            services.state_inference_service,
        )
    )
    return app
