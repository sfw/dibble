from __future__ import annotations

from fastapi import APIRouter, Request, status

from dibble.api.common import ApiContext, api_error
from dibble.models.auth import AuthIdentity
from dibble.models.classroom import Classroom, ClassroomUpsert
from dibble.models.classroom_membership import ClassroomMembershipRole
from dibble.models.mastery_history import ClassroomMasteryTrendsResponse
from dibble.models.teacher_classroom import (
    TeacherClassroomOverview,
    TeacherClassroomReadModel,
)


def build_teacher_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api/teachers")
    services = context.services

    def _accessible_classrooms(request: Request) -> list[Classroom]:
        classrooms = services.classroom_store.list()
        identity = getattr(request.state, "auth_identity", None)
        if not isinstance(identity, AuthIdentity):
            return classrooms
        if identity.role != "teacher":
            return classrooms

        allowed_ids = set(
            services.classroom_membership_store.list_user_classroom_ids(
                identity.principal_id,
                role=ClassroomMembershipRole.teacher,
            )
        )
        return [
            classroom
            for classroom in classrooms
            if classroom.classroom_id in allowed_ids
        ]

    def _learner_ids(classroom: Classroom) -> list[str]:
        return services.teacher_classroom_service.student_ids_for_classroom(classroom)

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
    def list_classrooms(request: Request) -> list[TeacherClassroomOverview]:
        return services.teacher_classroom_service.list_classrooms(
            _accessible_classrooms(request)
        )

    @router.get(
        "/classrooms/{classroom_id}",
        response_model=TeacherClassroomReadModel,
        dependencies=context.deps("viewer"),
    )
    def get_classroom(classroom_id: str, request: Request) -> TeacherClassroomReadModel:
        classroom = next(
            (
                candidate
                for candidate in _accessible_classrooms(request)
                if candidate.classroom_id == classroom_id
            ),
            None,
        )
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
        classroom_id: str, request: Request, days: int = 30
    ) -> ClassroomMasteryTrendsResponse:
        classroom = next(
            (
                candidate
                for candidate in _accessible_classrooms(request)
                if candidate.classroom_id == classroom_id
            ),
            None,
        )
        if classroom is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Classroom not found.",
                code="classroom_not_found",
            )
        return services.mastery_snapshot_service.get_classroom_trends(
            classroom_id=classroom_id,
            student_ids=_learner_ids(classroom),
            days=min(max(1, days), 365),
        )

    return router
