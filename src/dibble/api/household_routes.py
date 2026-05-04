from __future__ import annotations

from fastapi import APIRouter, Request

from dibble.api.common import ApiContext, api_error
from dibble.models.household import (
    HouseholdNotificationSnoozeRequest,
    HouseholdOverview,
    ParentApprovalPreview,
    HouseholdPreferenceUpdateRequest,
    HouseholdSessionSuggestionSnoozeRequest,
    HouseholdSetupRequest,
    HouseholdSetupResponse,
)


def build_household_router(context: ApiContext) -> APIRouter:
    router = APIRouter(
        prefix="/api/households",
        dependencies=context.deps("parent", "household_admin", "admin"),
    )

    @router.get("/me/overview", response_model=HouseholdOverview)
    def get_household_overview(request: Request) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        try:
            return context.services.household_service.get_household_overview(
                parent_user_id=identity.principal_id
            )
        except RuntimeError as exc:
            raise api_error(
                status_code=404,
                detail=str(exc),
                code="household_parent_not_found",
            ) from exc

    @router.put("/me/setup", response_model=HouseholdSetupResponse)
    def setup_household(
        payload: HouseholdSetupRequest, request: Request
    ) -> HouseholdSetupResponse:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        try:
            return context.services.household_service.setup_household(
                parent_user_id=identity.principal_id,
                request=payload,
            )
        except RuntimeError as exc:
            raise api_error(
                status_code=404,
                detail=str(exc),
                code="household_parent_not_found",
            ) from exc

    @router.post("/me/notifications/{notification_id}/read", response_model=HouseholdOverview)
    def mark_household_notification_read(
        notification_id: str, request: Request
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.mark_notification_read(
            parent_user_id=identity.principal_id,
            notification_id=notification_id,
        )

    @router.post(
        "/me/notifications/{notification_id}/dismiss",
        response_model=HouseholdOverview,
    )
    def dismiss_household_notification(
        notification_id: str, request: Request
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.dismiss_notification(
            parent_user_id=identity.principal_id,
            notification_id=notification_id,
        )

    @router.post(
        "/me/notifications/{notification_id}/snooze",
        response_model=HouseholdOverview,
    )
    def snooze_household_notification(
        notification_id: str,
        payload: HouseholdNotificationSnoozeRequest,
        request: Request,
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.snooze_notification(
            parent_user_id=identity.principal_id,
            notification_id=notification_id,
            request=payload,
        )

    @router.patch("/me/preferences", response_model=HouseholdOverview)
    def update_household_preferences(
        payload: HouseholdPreferenceUpdateRequest, request: Request
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        try:
            return context.services.household_service.update_parent_preferences(
                parent_user_id=identity.principal_id,
                request=payload,
            )
        except RuntimeError as exc:
            raise api_error(
                status_code=404,
                detail=str(exc),
                code="household_parent_not_found",
            ) from exc

    @router.post(
        "/me/session-suggestions/{learner_id}/accept",
        response_model=HouseholdOverview,
    )
    def accept_household_session_suggestion(
        learner_id: str, request: Request
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.accept_session_suggestion(
            parent_user_id=identity.principal_id,
            learner_id=learner_id,
        )

    @router.post(
        "/me/session-suggestions/{learner_id}/defer",
        response_model=HouseholdOverview,
    )
    def defer_household_session_suggestion(
        learner_id: str, request: Request
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.defer_session_suggestion(
            parent_user_id=identity.principal_id,
            learner_id=learner_id,
        )

    @router.post(
        "/me/session-suggestions/{learner_id}/snooze",
        response_model=HouseholdOverview,
    )
    def snooze_household_session_suggestion(
        learner_id: str,
        payload: HouseholdSessionSuggestionSnoozeRequest,
        request: Request,
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.snooze_session_suggestion(
            parent_user_id=identity.principal_id,
            learner_id=learner_id,
            request=payload,
        )

    @router.post(
        "/me/approvals/{learner_id}/{approval_id}/approve",
        response_model=HouseholdOverview,
    )
    def approve_household_parent_approval(
        learner_id: str,
        approval_id: str,
        request: Request,
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.approve_parent_approval(
            parent_user_id=identity.principal_id,
            learner_id=learner_id,
            approval_id=approval_id,
        )

    @router.get(
        "/me/approvals/{learner_id}/{approval_id}/preview",
        response_model=ParentApprovalPreview,
    )
    def preview_household_parent_approval(
        learner_id: str,
        approval_id: str,
        request: Request,
    ) -> ParentApprovalPreview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        try:
            return context.services.household_service.preview_parent_approval(
                parent_user_id=identity.principal_id,
                learner_id=learner_id,
                approval_id=approval_id,
            )
        except RuntimeError as exc:
            raise api_error(
                status_code=404,
                detail=str(exc),
                code="household_parent_approval_not_found",
            ) from exc

    @router.post(
        "/me/approvals/{learner_id}/{approval_id}/reject",
        response_model=HouseholdOverview,
    )
    def reject_household_parent_approval(
        learner_id: str,
        approval_id: str,
        request: Request,
    ) -> HouseholdOverview:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            raise api_error(
                status_code=401,
                detail="Authentication is required.",
                code="auth_invalid_credentials",
            )
        return context.services.household_service.reject_parent_approval(
            parent_user_id=identity.principal_id,
            learner_id=learner_id,
            approval_id=approval_id,
        )

    return router
