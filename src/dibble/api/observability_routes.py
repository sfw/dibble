from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from dibble.api.common import ApiContext, api_error
from dibble.models.generation import (
    CurriculumContentKey,
    CurriculumLibraryPrivacyAudit,
    CurriculumLibraryPrivacyAuditEntry,
    CurriculumLibrarySelectionTrace,
    GenerationRequest,
    ModalityRoutingInspection,
)
from dibble.models.household import LearnerRelationshipState
from dibble.models.observability import (
    AutonomousTeacherExplanationBundle,
    HarnessBoundary,
    MasteryProgressionMeasurementSummary,
    ModalityDecisionExplanationBundle,
    OperationalTrace,
    ReleaseReadinessSnapshot,
)
from dibble.models.planning import ActivePlanningState
from dibble.models.retention import RetentionReviewCandidate
from dibble.models.telemetry import AuditEvent, TelemetrySnapshot


_CURRICULUM_LIBRARY_STUDENT_ID = UUID("00000000-0000-0000-0000-000000000000")
_FORBIDDEN_LIBRARY_FIELDS = {
    "learner_id",
    "household_id",
    "parent_user_id",
    "session_id",
    "learning_session_id",
    "learner_profile",
    "observation_history",
    "relationship_state",
    "parent_preferences",
    "response_text",
    "profile",
}


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
    def inspect_modality_routing(
        payload: GenerationRequest,
    ) -> ModalityRoutingInspection:
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
        "/observability/adaptation/modality-routing/explain",
        response_model=ModalityDecisionExplanationBundle,
        dependencies=context.deps("admin"),
    )
    def explain_modality_routing(
        payload: GenerationRequest,
    ) -> ModalityDecisionExplanationBundle:
        profile = services.profile_store.get(payload.student_id)
        if profile is None:
            raise api_error(
                status_code=404,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.modality_routing_harness.explain(
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
        "/observability/adaptation/library/privacy-audit",
        response_model=CurriculumLibraryPrivacyAudit,
        dependencies=context.deps("admin"),
    )
    def audit_library_privacy() -> CurriculumLibraryPrivacyAudit:
        entries = services.curriculum_content_library_store.list_entries(
            include_expired=True
        )
        audit_entries: list[CurriculumLibraryPrivacyAuditEntry] = []
        all_hits: list[str] = []
        for entry in entries:
            hits = _library_forbidden_field_hits(entry.model_dump(mode="json"))
            all_hits.extend(
                f"{entry.cache_key or '<missing-cache-key>'}:{hit}" for hit in hits
            )
            audit_entries.append(
                CurriculumLibraryPrivacyAuditEntry(
                    cache_key=entry.cache_key or entry.content_key.cache_key(),
                    storage_scope=entry.storage_scope,
                    source_generation_id=entry.source_generation_id,
                    content_student_id=entry.content.student_id,
                    response_student_id=entry.content.response.student_id,
                    request_context_keys=sorted(entry.content.request_context.keys()),
                    curriculum_key_fields=sorted(
                        entry.content_key.request.model_dump(mode="json").keys()
                    ),
                    provenance_status=(
                        entry.provenance.publish_status
                        if entry.provenance is not None
                        else None
                    ),
                    forbidden_field_hits=hits,
                )
            )
        return CurriculumLibraryPrivacyAudit(
            entry_count=len(audit_entries),
            forbidden_field_hits=all_hits,
            entries=audit_entries,
        )

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
        "/observability/adaptation/retention/{student_id}/due",
        response_model=list[RetentionReviewCandidate],
        dependencies=context.deps("admin"),
    )
    def get_due_retention_reviews(
        student_id: UUID,
        limit: int = 20,
    ) -> list[RetentionReviewCandidate]:
        return services.retention_scheduler_service.due_reviews_for_student(
            learner_id=student_id,
            limit=max(1, min(limit, 100)),
        )

    @router.get(
        "/observability/adaptation/retention/{student_id}/scheduled",
        response_model=list[RetentionReviewCandidate],
        dependencies=context.deps("admin"),
    )
    def get_scheduled_retention_reviews(
        student_id: UUID,
        limit: int = 20,
    ) -> list[RetentionReviewCandidate]:
        return services.retention_scheduler_service.scheduled_reviews_for_student(
            learner_id=student_id,
            limit=max(1, min(limit, 100)),
        )

    @router.get(
        "/observability/adaptation/mastery-progression/metrics",
        response_model=MasteryProgressionMeasurementSummary,
        dependencies=context.deps("admin"),
    )
    def get_mastery_progression_metrics(
        student_id: UUID | None = None,
        limit: int = 500,
        lookback_days: int | None = 90,
    ) -> MasteryProgressionMeasurementSummary:
        return services.mastery_progression_measurement_service.summarize(
            learner_id=student_id,
            limit=max(1, min(limit, 2000)),
            lookback_days=lookback_days,
        )

    @router.get(
        "/observability/adaptation/autonomous-teacher/{household_id}/{learner_id}",
        response_model=LearnerRelationshipState,
        dependencies=context.deps("admin"),
    )
    def get_autonomous_teacher_adaptation(
        household_id: str,
        learner_id: str,
    ) -> LearnerRelationshipState:
        state = (
            services.autonomous_teacher_harness.learner_relationship_state_store.get(
                household_id=household_id,
                learner_id=learner_id,
            )
        )
        if state is None:
            raise api_error(
                status_code=404,
                detail="Learner relationship state not found.",
                code="learner_relationship_state_not_found",
            )
        return state

    @router.get(
        "/observability/adaptation/autonomous-teacher/{household_id}/{learner_id}/explain",
        response_model=AutonomousTeacherExplanationBundle,
        dependencies=context.deps("admin"),
    )
    def explain_autonomous_teacher_adaptation(
        household_id: str,
        learner_id: str,
    ) -> AutonomousTeacherExplanationBundle:
        try:
            return services.household_service.explain_autonomous_teacher_decision(
                household_id=household_id,
                learner_id=learner_id,
            )
        except RuntimeError as exc:
            raise api_error(
                status_code=404,
                detail=str(exc),
                code="learner_relationship_state_not_found",
            ) from exc

    return router


def _library_forbidden_field_hits(value: Any, *, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if _is_forbidden_library_field(key=key, value=child):
                hits.append(child_path)
            hits.extend(_library_forbidden_field_hits(child, path=child_path))
        return hits
    if isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_library_forbidden_field_hits(child, path=f"{path}[{index}]"))
    return hits


def _is_forbidden_library_field(*, key: str, value: Any) -> bool:
    if key == "student_id":
        return str(value) != str(_CURRICULUM_LIBRARY_STUDENT_ID)
    return key in _FORBIDDEN_LIBRARY_FIELDS
