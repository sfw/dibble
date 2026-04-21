from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from dibble.api.common import ApiContext, api_error
from dibble.models.generation import (
    CurriculumContentKey,
    CurriculumLibrarySelectionTrace,
    GenerationRequest,
    ModalityRoutingInspection,
)
from dibble.models.household import LearnerRelationshipState
from dibble.models.observability import (
    HarnessBoundary,
    OperationalTrace,
    ReleaseReadinessSnapshot,
)
from dibble.models.planning import ActivePlanningState
from dibble.models.telemetry import AuditEvent, TelemetrySnapshot


def build_observability_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.get(
        "/audit/events",
        response_model=list[AuditEvent],
        dependencies=context.deps("admin"),
    )
    def list_audit_events(limit: int = 50) -> list[AuditEvent]:
        safe_limit = max(1, min(limit, 200))
        return services.audit_store.list(limit=safe_limit)

    @router.get(
        "/observability/traces",
        response_model=list[OperationalTrace],
        dependencies=context.deps("admin"),
    )
    def list_operational_traces(
        limit: int = 100,
        harness: HarnessBoundary | None = None,
        degraded_only: bool = False,
        request_id: str | None = None,
        session_id: str | None = None,
    ) -> list[OperationalTrace]:
        safe_limit = max(1, min(limit, 200))
        return services.operational_observability_service.list_traces(
            limit=safe_limit,
            harness=harness,
            degraded_only=degraded_only,
            request_id=request_id,
            session_id=session_id,
        )

    @router.get(
        "/observability/metrics",
        response_model=TelemetrySnapshot,
        dependencies=context.deps("admin"),
    )
    def get_observability_metrics() -> TelemetrySnapshot:
        return services.telemetry_service.snapshot()

    @router.get(
        "/observability/readiness",
        response_model=ReleaseReadinessSnapshot,
        dependencies=context.deps("admin"),
    )
    def get_release_readiness() -> ReleaseReadinessSnapshot:
        return services.operational_observability_service.release_readiness_snapshot()

    @router.post(
        "/observability/adaptation/modality-routing/inspect",
        response_model=ModalityRoutingInspection,
        dependencies=context.deps("admin"),
    )
    def inspect_modality_routing(payload: GenerationRequest) -> ModalityRoutingInspection:
        profile = services.profile_store.get(payload.student_id)
        if profile is None:
            raise api_error(
                status_code=404,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.modality_routing_harness.inspect(
            profile=profile,
            request=payload,
        )

    @router.post(
        "/observability/adaptation/library/inspect",
        response_model=CurriculumLibrarySelectionTrace,
        dependencies=context.deps("admin"),
    )
    def inspect_library_ranking(
        payload: CurriculumContentKey,
    ) -> CurriculumLibrarySelectionTrace:
        library = services.generation_engine.harness.content_library.library
        if library is None or not hasattr(library, "inspect_selection"):
            raise api_error(
                status_code=404,
                detail="Curriculum content library observability is not available.",
                code="curriculum_library_unavailable",
            )
        return library.inspect_selection(key=payload)

    @router.get(
        "/observability/adaptation/planning/{student_id}",
        response_model=ActivePlanningState,
        dependencies=context.deps("admin"),
    )
    def get_planning_adaptation(student_id: str) -> ActivePlanningState:
        planning = services.curriculum_planning_harness.get_active_state(
            student_id=UUID(student_id)
        )
        if planning.goal is None and planning.trajectory is None:
            raise api_error(
                status_code=404,
                detail="Active planning state not found.",
                code="planning_state_not_found",
            )
        return ActivePlanningState(goal=planning.goal, trajectory=planning.trajectory)

    @router.get(
        "/observability/adaptation/autonomous-teacher/{household_id}/{learner_id}",
        response_model=LearnerRelationshipState,
        dependencies=context.deps("admin"),
    )
    def get_autonomous_teacher_adaptation(
        household_id: str,
        learner_id: str,
    ) -> LearnerRelationshipState:
        state = services.autonomous_teacher_harness.learner_relationship_state_store.get(
            household_id=household_id,
            learner_id=learner_id,
        )
        if state is None:
            raise api_error(
                status_code=404,
                detail="Learner relationship state not found.",
                code="learner_relationship_state_not_found",
            )
        return state

    return router
