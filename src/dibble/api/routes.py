from __future__ import annotations

from fastapi import APIRouter

from dibble.api.assessment_routes import build_assessment_router
from dibble.api.assignment_routes import build_assignment_router
from dibble.api.auth_routes import build_auth_router
from dibble.api.common import ApiContext, ApiServices
from dibble.api.content_routes import build_content_router
from dibble.api.curriculum_routes import build_curriculum_router
from dibble.api.learner_routes import build_learner_router
from dibble.api.observability_routes import build_observability_router
from dibble.api.setup_routes import build_setup_router
from dibble.api.teacher_routes import build_teacher_router
from dibble.api.user_routes import build_user_router


def build_router(services: ApiServices) -> APIRouter:
    context = ApiContext(services=services)
    router = APIRouter()

    @router.get("/health")
    def healthcheck() -> dict[str, object]:
        setup_status = context.services.setup_config_service.get_status()
        return {"status": "ok", "configured": setup_status.configured}

    router.include_router(build_assignment_router(context))
    router.include_router(build_auth_router(context))
    router.include_router(build_learner_router(context))
    router.include_router(build_curriculum_router(context))
    router.include_router(build_content_router(context))
    router.include_router(build_assessment_router(context))
    router.include_router(build_teacher_router(context))
    router.include_router(build_observability_router(context))
    router.include_router(build_setup_router(context))
    router.include_router(build_user_router(context))
    return router
