from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from dibble.api.common import ApiContext, api_error
from dibble.models.placement import (
    PlacementReport,
    PlacementRespondRequest,
    PlacementStartRequest,
    PlacementStateResponse,
)
from dibble.services.placement import PlacementError


def build_placement_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.post(
        "/learners/{student_id}/placement",
        response_model=PlacementStateResponse,
        dependencies=context.deps("teacher", "parent"),
    )
    def start_placement(
        student_id: UUID, payload: PlacementStartRequest
    ) -> PlacementStateResponse:
        try:
            return services.placement_service.start(
                student_id=student_id,
                grade_band=payload.grade_band,
                question_budget=payload.question_budget,
            )
        except PlacementError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="placement_unavailable",
                detail=str(exc),
            ) from exc

    @router.post(
        "/learners/{student_id}/placement/{session_id}/respond",
        response_model=PlacementStateResponse,
        dependencies=context.deps("learner"),
    )
    def respond_placement(
        student_id: UUID, session_id: str, payload: PlacementRespondRequest
    ) -> PlacementStateResponse:
        try:
            return services.placement_service.respond(
                student_id=student_id,
                session_id=session_id,
                selected_option_id=payload.selected_option_id,
                correct=payload.correct,
            )
        except PlacementError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="placement_response_invalid",
                detail=str(exc),
            ) from exc

    @router.get(
        "/learners/{student_id}/placement/{session_id}",
        response_model=PlacementStateResponse,
        dependencies=context.deps("viewer"),
    )
    def get_placement(student_id: UUID, session_id: str) -> PlacementStateResponse:
        try:
            return services.placement_service.get_state(
                student_id=student_id, session_id=session_id
            )
        except PlacementError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="placement_not_found",
                detail=str(exc),
            ) from exc

    @router.get(
        "/learners/{student_id}/placement-report",
        response_model=PlacementReport | None,
        dependencies=context.deps("viewer"),
    )
    def get_placement_report(student_id: UUID) -> PlacementReport | None:
        return services.placement_service.latest_report(student_id=student_id)

    return router
