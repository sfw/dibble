from __future__ import annotations

from fastapi import APIRouter
from fastapi import status

from dibble.api.common import ApiContext, api_error
from dibble.models.admin_academics import AdminCourseSummary, AdminSectionSummary
from dibble.models.classroom import ClassroomUpsert
from dibble.models.admin import (
    SystemConfigResponse,
    SystemConfigUpdateRequest,
    SystemConfigUpdateResponse,
)
from dibble.models.course import CourseUpsert


def build_admin_router(context: ApiContext) -> APIRouter:
    router = APIRouter(
        prefix="/api/admin",
        dependencies=context.deps("admin"),
    )

    @router.get("/config", response_model=SystemConfigResponse)
    def get_system_config() -> SystemConfigResponse:
        return context.services.admin_config_service.get_config()

    @router.put("/config", response_model=SystemConfigUpdateResponse)
    def update_system_config(
        payload: SystemConfigUpdateRequest,
    ) -> SystemConfigUpdateResponse:
        return context.services.admin_config_service.update_config(payload)

    @router.get("/courses", response_model=list[AdminCourseSummary])
    def list_courses() -> list[AdminCourseSummary]:
        return context.services.admin_academic_catalog_service.list_courses()

    @router.put("/courses/{course_id}", response_model=AdminCourseSummary)
    def upsert_course(course_id: str, payload: CourseUpsert) -> AdminCourseSummary:
        if payload.course_id != course_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path course_id must match the course payload course_id.",
                code="course_id_mismatch",
            )
        context.services.admin_academic_catalog_service.upsert_course(payload)
        summary = context.services.admin_academic_catalog_service.get_course_summary(
            course_id
        )
        if summary is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found after write.",
                code="course_not_found",
            )
        return summary

    @router.get("/sections", response_model=list[AdminSectionSummary])
    def list_sections() -> list[AdminSectionSummary]:
        return context.services.admin_academic_catalog_service.list_sections()

    @router.put("/sections/{section_id}", response_model=AdminSectionSummary)
    def upsert_section(
        section_id: str, payload: ClassroomUpsert
    ) -> AdminSectionSummary:
        if payload.classroom_id != section_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path section_id must match the section payload classroom_id.",
                code="section_id_mismatch",
            )
        try:
            context.services.admin_academic_catalog_service.upsert_section(payload)
        except LookupError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Course {payload.course_id} does not exist.",
                code="section_course_not_found",
            ) from exc
        summary = context.services.admin_academic_catalog_service.get_section_summary(
            section_id
        )
        if summary is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found after write.",
                code="section_not_found",
            )
        return summary

    return router
