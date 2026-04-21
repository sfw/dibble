from __future__ import annotations

from fastapi import APIRouter
from fastapi import status

from dibble.api.common import ApiContext, api_error
from dibble.models.admin_academics import AdminCourseSummary, AdminSectionSummary
from dibble.models.admin_section_membership import (
    AdminSectionMembershipSummary,
    AdminSectionMembershipUpdateRequest,
)
from dibble.models.admin import (
    SystemConfigResponse,
    SystemConfigUpdateRequest,
    SystemConfigUpdateResponse,
)
from dibble.models.course import CourseUpsert
from dibble.models.curriculum_intake import (
    AlignmentEdge,
    AlignmentEdgeCreate,
    AlignmentReviewDecision,
    AlignmentReviewRequest,
    CurriculumFramework,
    CurriculumImportRequest,
    CurriculumPublishRequest,
    FrameworkImport,
    FrameworkImportArtifact,
    PublishedCurriculumSnapshot,
)
from dibble.models.section import SectionUpsert
from dibble.services.admin_section_membership_service import (
    SectionMembershipRoleMismatchError,
)


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

    @router.get("/curriculum/frameworks", response_model=list[CurriculumFramework])
    def list_curriculum_frameworks() -> list[CurriculumFramework]:
        return context.services.curriculum_intake_harness.list_frameworks()

    @router.get("/curriculum/imports", response_model=list[FrameworkImport])
    def list_curriculum_imports() -> list[FrameworkImport]:
        return context.services.curriculum_intake_harness.list_imports()

    @router.post("/curriculum/imports", response_model=FrameworkImport)
    def import_curriculum(payload: CurriculumImportRequest) -> FrameworkImport:
        try:
            return context.services.curriculum_intake_harness.import_framework(payload)
        except LookupError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown curriculum adapter {payload.adapter_key}.",
                code="curriculum_adapter_not_found",
            ) from exc

    @router.get("/curriculum/imports/{import_id}", response_model=FrameworkImport)
    def get_curriculum_import(import_id: str) -> FrameworkImport:
        framework_import = context.services.curriculum_intake_harness.get_import(
            import_id
        )
        if framework_import is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curriculum import not found.",
                code="curriculum_import_not_found",
            )
        return framework_import

    @router.get(
        "/curriculum/imports/{import_id}/artifacts",
        response_model=list[FrameworkImportArtifact],
    )
    def list_curriculum_import_artifacts(
        import_id: str,
    ) -> list[FrameworkImportArtifact]:
        return context.services.curriculum_intake_harness.list_import_artifacts(
            import_id
        )

    @router.post(
        "/curriculum/imports/{import_id}/publish",
        response_model=PublishedCurriculumSnapshot,
    )
    def publish_curriculum_import(
        import_id: str, payload: CurriculumPublishRequest
    ) -> PublishedCurriculumSnapshot:
        try:
            return context.services.curriculum_intake_harness.publish_import(
                import_id, force=payload.force
            )
        except LookupError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Curriculum import not found.",
                code="curriculum_import_not_found",
            ) from exc
        except ValueError as exc:
            code = str(exc)
            if code == "failed_import_requires_force":
                raise api_error(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed imports require force=true before publish.",
                    code="curriculum_import_publish_blocked",
                ) from exc
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Curriculum import could not be published.",
                code="curriculum_import_publish_failed",
            ) from exc

    @router.get(
        "/curriculum/snapshots",
        response_model=list[PublishedCurriculumSnapshot],
    )
    def list_curriculum_snapshots() -> list[PublishedCurriculumSnapshot]:
        return context.services.curriculum_intake_harness.list_snapshots()

    @router.get("/curriculum/alignments", response_model=list[AlignmentEdge])
    def list_curriculum_alignments() -> list[AlignmentEdge]:
        return context.services.curriculum_intake_harness.list_alignment_edges()

    @router.post("/curriculum/alignments", response_model=AlignmentEdge)
    def create_curriculum_alignment(payload: AlignmentEdgeCreate) -> AlignmentEdge:
        return context.services.curriculum_intake_harness.propose_alignment(payload)

    @router.post(
        "/curriculum/alignments/{edge_id}/review",
        response_model=AlignmentEdge,
    )
    def review_curriculum_alignment(
        edge_id: str, payload: AlignmentReviewRequest
    ) -> AlignmentEdge:
        try:
            return context.services.curriculum_intake_harness.review_alignment(
                edge_id, payload
            )
        except LookupError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alignment edge not found.",
                code="alignment_edge_not_found",
            ) from exc

    @router.get(
        "/curriculum/alignments/{edge_id}/reviews",
        response_model=list[AlignmentReviewDecision],
    )
    def list_curriculum_alignment_reviews(
        edge_id: str,
    ) -> list[AlignmentReviewDecision]:
        return context.services.curriculum_intake_harness.list_alignment_reviews(
            edge_id
        )

    @router.put("/sections/{section_id}", response_model=AdminSectionSummary)
    def upsert_section(section_id: str, payload: SectionUpsert) -> AdminSectionSummary:
        if payload.section_id != section_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path section_id must match the section payload section_id.",
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

    @router.get(
        "/sections/{section_id}/memberships",
        response_model=AdminSectionMembershipSummary,
    )
    def get_section_memberships(section_id: str) -> AdminSectionMembershipSummary:
        summary = (
            context.services.admin_section_membership_service.get_section_memberships(
                section_id
            )
        )
        if summary is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found.",
                code="section_not_found",
            )
        return summary

    @router.put(
        "/sections/{section_id}/memberships",
        response_model=AdminSectionMembershipSummary,
    )
    def update_section_memberships(
        section_id: str, payload: AdminSectionMembershipUpdateRequest
    ) -> AdminSectionMembershipSummary:
        try:
            return context.services.admin_section_membership_service.update_section_memberships(
                section_id,
                payload,
            )
        except LookupError as exc:
            user_id = getattr(exc, "user_id", None)
            if user_id is not None:
                raise api_error(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User {user_id} does not exist.",
                    code="section_membership_user_not_found",
                ) from exc
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found.",
                code="section_not_found",
            ) from exc
        except SectionMembershipRoleMismatchError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"User {exc.user_id} must have role "
                    f"{exc.expected_role}, found {exc.actual_role}."
                ),
                code="section_membership_role_mismatch",
            ) from exc

    return router
