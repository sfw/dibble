from __future__ import annotations

from fastapi import APIRouter

from dibble.api.assessment_routes import build_assessment_router
from dibble.api.auth_routes import build_auth_router
from dibble.api.common import ApiContext, ApiServices
from dibble.api.content_routes import build_content_router
from dibble.api.curriculum_routes import build_curriculum_router
from dibble.api.learner_routes import build_learner_router
from dibble.api.observability_routes import build_observability_router


def build_router(services: ApiServices) -> APIRouter:
    context = ApiContext(services=services)
    router = APIRouter()

    @router.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    router.include_router(build_auth_router(context))
    router.include_router(build_learner_router(context))
    router.include_router(build_curriculum_router(context))
    router.include_router(build_content_router(context))
    router.include_router(build_assessment_router(context))
    router.include_router(build_observability_router(context))
    return router
