from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from dibble.api.common import ApiContext
from dibble.models.session_bookends import (
    DefectReportRequest,
    DefectReportResponse,
    SessionEndRequest,
    SessionRecap,
    SessionStartResponse,
)


def build_session_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.post(
        "/learners/{student_id}/session/start",
        response_model=SessionStartResponse,
        dependencies=context.deps("learner"),
    )
    def start_session(student_id: UUID) -> SessionStartResponse:
        return services.session_bookend_service.start_session(student_id=student_id)

    @router.post(
        "/learners/{student_id}/session/end",
        response_model=SessionRecap,
        dependencies=context.deps("learner"),
    )
    def end_session(student_id: UUID, payload: SessionEndRequest) -> SessionRecap:
        return services.session_bookend_service.end_session(
            student_id=student_id,
            learning_session_id=payload.learning_session_id,
        )

    @router.post(
        "/learners/{student_id}/defect-report",
        response_model=DefectReportResponse,
        dependencies=context.deps("learner"),
    )
    def report_defect(
        student_id: UUID, payload: DefectReportRequest, request: Request
    ) -> DefectReportResponse:
        identity = getattr(request.state, "auth_identity", None)
        return services.session_bookend_service.record_defect_report(
            student_id=student_id,
            generation_id=payload.generation_id,
            learning_session_id=payload.learning_session_id,
            note=payload.note,
            reported_role=identity.role if identity is not None else None,
        )

    return router
