from __future__ import annotations

from fastapi import APIRouter, Request, status

from dibble.api.common import ApiContext, api_error
from dibble.models.auth import AuthIdentity
from dibble.models.classroom import Classroom, ClassroomUpsert
from dibble.models.classroom_membership import ClassroomMembershipRole
from dibble.models.mastery_history import SectionMasteryTrendsResponse
from dibble.models.section import Section, SectionUpsert
from dibble.models.teacher_classroom import (
    TeacherSectionOverview,
    TeacherSectionReadModel,
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
            services.classroom_membership_store.list_user_section_ids(
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
        return services.teacher_section_service.student_ids_for_section(classroom)

    @router.put(
        "/sections/{section_id}",
        response_model=Section,
        dependencies=context.deps("editor"),
    )
    def upsert_section(section_id: str, section: SectionUpsert) -> Section:
        if section_id != section.section_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path section_id must match the section payload section_id.",
                code="section_id_mismatch",
            )
        classroom = services.classroom_store.upsert(
            ClassroomUpsert(
                classroom_id=section.section_id,
                course_id=section.course_id,
                title=section.title,
                grade_level=section.grade_level,
                subject=section.subject,
                tags=section.tags,
            )
        )
        return Section(
            section_id=classroom.classroom_id,
            course_id=classroom.course_id,
            title=classroom.title,
            grade_level=classroom.grade_level,
            subject=classroom.subject,
            tags=classroom.tags,
            updated_at=classroom.updated_at,
        )

    @router.get(
        "/sections",
        response_model=list[TeacherSectionOverview],
        dependencies=context.deps("viewer"),
    )
    def list_sections(request: Request) -> list[TeacherSectionOverview]:
        return services.teacher_section_service.list_sections(
            _accessible_classrooms(request)
        )

    @router.get(
        "/sections/{section_id}",
        response_model=TeacherSectionReadModel,
        dependencies=context.deps("viewer"),
    )
    def get_section(section_id: str, request: Request) -> TeacherSectionReadModel:
        classroom = next(
            (
                candidate
                for candidate in _accessible_classrooms(request)
                if candidate.classroom_id == section_id
            ),
            None,
        )
        if classroom is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found.",
                code="section_not_found",
            )
        return services.teacher_section_service.build_section(classroom)

    @router.get(
        "/sections/{section_id}/mastery-trends",
        response_model=SectionMasteryTrendsResponse,
        dependencies=context.deps("viewer"),
    )
    def get_section_mastery_trends(
        section_id: str, request: Request, days: int = 30
    ) -> SectionMasteryTrendsResponse:
        classroom = next(
            (
                candidate
                for candidate in _accessible_classrooms(request)
                if candidate.classroom_id == section_id
            ),
            None,
        )
        if classroom is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found.",
                code="section_not_found",
            )
        return services.mastery_snapshot_service.get_section_trends(
            section_id=section_id,
            student_ids=_learner_ids(classroom),
            days=min(max(1, days), 365),
        )

    return router
