from __future__ import annotations

from fastapi import APIRouter, Request, status

from dibble.api.common import ApiContext, api_error
from dibble.models.guardian import (
    FamilyLearnerCreateRequest,
    FamilyLearnerCreateResponse,
    FamilyLearnerSummary,
    GuardianInvite,
    GuardianInviteCreateRequest,
    GuardianRegisterRequest,
    GuardianRegisterResponse,
)
from dibble.services.guardian_onboarding import GuardianOnboardingError


def build_guardian_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.post(
        "/admin/guardian-invites",
        response_model=GuardianInvite,
        dependencies=context.deps("admin"),
    )
    def create_guardian_invite(
        payload: GuardianInviteCreateRequest, request: Request
    ) -> GuardianInvite:
        identity = getattr(request.state, "auth_identity", None)
        return services.guardian_onboarding_service.create_invite(
            created_by=identity.principal_id if identity is not None else None,
            family_name=payload.family_name,
        )

    @router.get(
        "/admin/guardian-invites",
        response_model=list[GuardianInvite],
        dependencies=context.deps("admin"),
    )
    def list_guardian_invites() -> list[GuardianInvite]:
        return services.guardian_onboarding_service.list_invites()

    # Open by design: the invite code is the authorization.
    @router.post("/auth/register-guardian", response_model=GuardianRegisterResponse)
    def register_guardian(
        payload: GuardianRegisterRequest,
    ) -> GuardianRegisterResponse:
        try:
            return services.guardian_onboarding_service.register_guardian(
                invite_code=payload.invite_code,
                display_name=payload.display_name,
                course_id=payload.course_id,
            )
        except GuardianOnboardingError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="guardian_invite_invalid",
                detail=str(exc),
            ) from exc

    @router.post(
        "/family/learners",
        response_model=FamilyLearnerCreateResponse,
        dependencies=context.deps("teacher", "parent"),
    )
    def create_family_learner(
        payload: FamilyLearnerCreateRequest, request: Request
    ) -> FamilyLearnerCreateResponse:
        identity = getattr(request.state, "auth_identity", None)
        try:
            return services.guardian_onboarding_service.create_family_learner(
                guardian_user_id=(
                    identity.principal_id if identity is not None else None
                ),
                display_name=payload.display_name,
                grade_level=payload.grade_level,
                section_id=payload.section_id,
            )
        except GuardianOnboardingError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="family_learner_invalid",
                detail=str(exc),
            ) from exc

    @router.get(
        "/family/learners",
        response_model=list[FamilyLearnerSummary],
        dependencies=context.deps("teacher", "parent"),
    )
    def list_family_learners(
        request: Request, section_id: str | None = None
    ) -> list[FamilyLearnerSummary]:
        identity = getattr(request.state, "auth_identity", None)
        try:
            return services.guardian_onboarding_service.list_family_learners(
                guardian_user_id=(
                    identity.principal_id if identity is not None else None
                ),
                section_id=section_id,
            )
        except GuardianOnboardingError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="family_section_unresolved",
                detail=str(exc),
            ) from exc

    return router
