from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Query, Request, status

from dibble.api.common import ApiContext, api_error
from dibble.models.assignment import (
    Assignment,
    AssignmentCreate,
    AssignmentPage,
    AssignmentStatus,
    AssignmentUpdate,
)


def build_assignment_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.post(
        "/assignments",
        response_model=Assignment,
        status_code=status.HTTP_201_CREATED,
        dependencies=context.deps("teacher"),
    )
    def create_assignment(payload: AssignmentCreate, request: Request) -> Assignment:
        identity = getattr(request.state, "auth_identity", None)
        teacher_id = (
            identity.principal_id if identity and identity.principal_id else "unknown"
        )

        assignment = Assignment(
            assignment_id=str(uuid4()),
            student_id=payload.student_id,
            teacher_id=teacher_id,
            section_id=payload.section_id,
            title=payload.title,
            description=payload.description,
            target_resource_id=payload.target_resource_id,
            target_kc_ids=payload.target_kc_ids,
            target_lo_ids=payload.target_lo_ids,
            due_at=payload.due_at,
        )
        services.assignment_store.upsert(assignment)

        services.audit_store.append(
            event_type="assignment.created",
            status="created",
            student_id=payload.student_id,
            payload={
                "assignment_id": assignment.assignment_id,
                "teacher_id": teacher_id,
                "title": payload.title,
            },
        )
        return assignment

    @router.get(
        "/assignments/{assignment_id}",
        response_model=Assignment,
        dependencies=context.deps("viewer"),
    )
    def get_assignment(assignment_id: str) -> Assignment:
        assignment = services.assignment_store.get(assignment_id)
        if assignment is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found.",
                code="assignment_not_found",
            )
        return assignment

    @router.patch(
        "/assignments/{assignment_id}",
        response_model=Assignment,
        dependencies=context.deps("teacher"),
    )
    def update_assignment_status(
        assignment_id: str, payload: AssignmentUpdate
    ) -> Assignment:
        assignment = services.assignment_store.get(assignment_id)
        if assignment is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found.",
                code="assignment_not_found",
            )

        now = datetime.now(timezone.utc)
        assignment.status = payload.status
        assignment.updated_at = now

        if (
            payload.status == AssignmentStatus.in_progress
            and assignment.started_at is None
        ):
            assignment.started_at = now
        elif (
            payload.status == AssignmentStatus.completed
            and assignment.completed_at is None
        ):
            assignment.completed_at = now

        services.assignment_store.upsert(assignment)

        services.audit_store.append(
            event_type="assignment.updated",
            status=payload.status.value,
            student_id=assignment.student_id,
            payload={
                "assignment_id": assignment_id,
                "new_status": payload.status.value,
            },
        )
        return assignment

    @router.get(
        "/learners/{student_id}/assignments",
        response_model=AssignmentPage,
        dependencies=context.deps("viewer"),
    )
    def list_learner_assignments(
        student_id: str,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> AssignmentPage:
        items = services.assignment_store.list_for_student(
            student_id=student_id,
            limit=limit + 1,
            offset=offset,
        )
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]
        return AssignmentPage(
            items=items, offset=offset, limit=limit, has_more=has_more
        )

    @router.get(
        "/teachers/assignments",
        response_model=AssignmentPage,
        dependencies=context.deps("teacher"),
    )
    def list_teacher_assignments(
        request: Request,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> AssignmentPage:
        identity = getattr(request.state, "auth_identity", None)
        teacher_id = (
            identity.principal_id if identity and identity.principal_id else "unknown"
        )
        items = services.assignment_store.list_for_teacher(
            teacher_id=teacher_id,
            limit=limit + 1,
            offset=offset,
        )
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]
        return AssignmentPage(
            items=items, offset=offset, limit=limit, has_more=has_more
        )

    return router
