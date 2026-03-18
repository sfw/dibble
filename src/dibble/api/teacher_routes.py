from __future__ import annotations

from fastapi import APIRouter, status

from dibble.api.common import ApiContext, api_error
from dibble.models.classroom import Classroom, ClassroomUpsert
from dibble.models.mastery_history import ClassroomMasteryTrendsResponse
from dibble.models.teacher_classroom import (
    TeacherClassroomOverview,
    TeacherClassroomReadModel,
)


def build_teacher_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api/teachers")
    services = context.services

    @router.put(
        "/classrooms/{classroom_id}",
        response_model=Classroom,
        dependencies=context.deps("editor"),
    )
    def upsert_classroom(classroom_id: str, classroom: ClassroomUpsert) -> Classroom:
        if classroom_id != classroom.classroom_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path classroom_id must match the classroom payload classroom_id.",
                code="classroom_id_mismatch",
            )
        return services.classroom_store.upsert(classroom)

    @router.get(
        "/classrooms",
        response_model=list[TeacherClassroomOverview],
        dependencies=context.deps("viewer"),
    )
    def list_classrooms() -> list[TeacherClassroomOverview]:
        return services.teacher_classroom_service.list_classrooms(
            services.classroom_store.list()
        )

    @router.get(
        "/classrooms/{classroom_id}",
        response_model=TeacherClassroomReadModel,
        dependencies=context.deps("viewer"),
    )
    def get_classroom(classroom_id: str) -> TeacherClassroomReadModel:
        classroom = services.classroom_store.get(classroom_id)
        if classroom is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Classroom not found.",
                code="classroom_not_found",
            )
        return services.teacher_classroom_service.build_classroom(classroom)

    @router.get(
        "/classrooms/{classroom_id}/mastery-trends",
        response_model=ClassroomMasteryTrendsResponse,
        dependencies=context.deps("viewer"),
    )
    def get_classroom_mastery_trends(
        classroom_id: str, days: int = 30
    ) -> ClassroomMasteryTrendsResponse:
        classroom = services.classroom_store.get(classroom_id)
        if classroom is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Classroom not found.",
                code="classroom_not_found",
            )
        return services.mastery_snapshot_service.get_classroom_trends(
            classroom_id=classroom_id,
            student_ids=classroom.student_ids,
            days=min(max(1, days), 365),
        )

    return router
