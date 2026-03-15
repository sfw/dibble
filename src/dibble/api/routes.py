from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from dibble.models.curriculum import CurriculumResource, CurriculumResourceUpsert
from dibble.models.generation import AdaptiveRouteDecision, GenerationRequest, GenerationResponse, GenerationStreamEvent
from dibble.models.profile import LearnerProfile, ProfileSummary
from dibble.models.telemetry import AuditEvent, TelemetrySnapshot
from dibble.plugins.contracts import RouterPlugin
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import AuthService, AuthenticationError
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.streaming import encode_sse_event
from dibble.services.telemetry import TelemetryService


def build_router(
    profile_store: SQLiteProfileStore,
    curriculum_store: SQLiteCurriculumStore,
    audit_store: SQLiteAuditStore,
    auth_service: AuthService,
    telemetry_service: TelemetryService,
    router_service: RouterPlugin,
    generation_engine: GenerationEngine,
) -> APIRouter:
    router = APIRouter()
    protected_router = APIRouter()

    async def require_auth(
        request: Request,
        api_key: str | None = Header(default=None, alias=auth_service.header_name),
    ) -> None:
        try:
            auth_service.authorize(api_key)
        except AuthenticationError as exc:
            audit_store.append(
                event_type="auth.request",
                status="denied",
                payload={
                    "path": request.url.path,
                    "method": request.method,
                    "header_name": auth_service.header_name,
                },
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    @router.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    protected_dependencies = [Depends(require_auth)] if auth_service.enabled else []

    @protected_router.put("/api/v1/profiles/{student_id}", response_model=LearnerProfile, dependencies=protected_dependencies)
    def upsert_profile(student_id: UUID, profile: LearnerProfile) -> LearnerProfile:
        if student_id != profile.student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path student_id must match the profile payload student_id.",
            )
        return profile_store.upsert(profile)

    @protected_router.get("/api/v1/profiles/{student_id}", response_model=LearnerProfile, dependencies=protected_dependencies)
    def get_profile(student_id: UUID) -> LearnerProfile:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return profile

    @protected_router.get("/api/v1/profiles", response_model=list[str], dependencies=protected_dependencies)
    def list_profiles() -> list[str]:
        return profile_store.list_ids()

    @protected_router.get(
        "/api/v1/profiles/{student_id}/summary",
        response_model=ProfileSummary,
        dependencies=protected_dependencies,
    )
    def get_profile_summary(student_id: UUID) -> ProfileSummary:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return ProfileSummary.from_profile(profile)

    @protected_router.put(
        "/api/v1/curriculum/resources/{resource_id}",
        response_model=CurriculumResource,
        dependencies=protected_dependencies,
    )
    def upsert_curriculum_resource(
        resource_id: str,
        resource: CurriculumResourceUpsert,
    ) -> CurriculumResource:
        if resource_id != resource.resource_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path resource_id must match the resource payload resource_id.",
            )
        return curriculum_store.upsert(resource)

    @protected_router.get(
        "/api/v1/curriculum/resources",
        response_model=list[CurriculumResource],
        dependencies=protected_dependencies,
    )
    def list_curriculum_resources() -> list[CurriculumResource]:
        return curriculum_store.list()

    @protected_router.post(
        "/api/v1/adaptive/decide",
        response_model=AdaptiveRouteDecision,
        dependencies=protected_dependencies,
    )
    def decide_adaptive_route(request: GenerationRequest) -> AdaptiveRouteDecision:
        profile = profile_store.get(request.student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        decision = router_service.route(profile, request)
        audit_store.append(
            event_type="adaptive.decide",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "intervention_type": decision.intervention_type.value,
                "delivery_mode": decision.delivery_mode.value,
                "scaffolding_level": decision.scaffolding_level,
                "reason_count": len(decision.reasons),
            },
        )
        return decision

    @protected_router.post(
        "/api/v1/adaptive/generate",
        response_model=GenerationResponse,
        dependencies=protected_dependencies,
    )
    def generate_adaptive_content(request: GenerationRequest) -> GenerationResponse:
        profile = profile_store.get(request.student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")

        response = generation_engine.generate(profile, request)
        audit_store.append(
            event_type="adaptive.generate",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "intervention_type": response.route.intervention_type.value,
                "delivery_mode": response.route.delivery_mode.value,
                "grounding_count": len(response.grounding),
                "generated_block_count": len(response.blocks),
                "validation_issue_count": len(response.validation_issues),
            },
        )
        return response

    @protected_router.post("/api/v1/adaptive/generate/stream", dependencies=protected_dependencies)
    def stream_adaptive_content(request: GenerationRequest) -> StreamingResponse:
        profile = profile_store.get(request.student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")

        def event_stream():
            try:
                complete_event: GenerationStreamEvent | None = None
                for event in generation_engine.stream_generate(profile, request):
                    if event.event == "complete":
                        complete_event = event
                        response = event.response
                        if response is not None:
                            audit_store.append(
                                event_type="adaptive.generate.stream",
                                status="success",
                                student_id=str(request.student_id),
                                payload={
                                    "intent": request.intent.value,
                                    "intervention_type": response.route.intervention_type.value,
                                    "delivery_mode": response.route.delivery_mode.value,
                                    "grounding_count": len(response.grounding),
                                    "generated_block_count": len(response.blocks),
                                    "validation_issue_count": len(response.validation_issues),
                                },
                            )
                    yield encode_sse_event(event)

                if complete_event is None:
                    audit_store.append(
                        event_type="adaptive.generate.stream",
                        status="error",
                        student_id=str(request.student_id),
                        payload={"intent": request.intent.value, "detail": "stream ended before completion"},
                    )
            except Exception as exc:
                audit_store.append(
                    event_type="adaptive.generate.stream",
                    status="error",
                    student_id=str(request.student_id),
                    payload={"intent": request.intent.value, "detail": str(exc)},
                )
                yield encode_sse_event(
                    GenerationStreamEvent(
                        event="error",
                        student_id=request.student_id,
                        validation_issues=[str(exc)],
                    )
                )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @protected_router.get("/api/v1/audit/events", response_model=list[AuditEvent], dependencies=protected_dependencies)
    def list_audit_events(limit: int = 50) -> list[AuditEvent]:
        safe_limit = max(1, min(limit, 200))
        return audit_store.list(limit=safe_limit)

    @protected_router.get(
        "/api/v1/observability/metrics",
        response_model=TelemetrySnapshot,
        dependencies=protected_dependencies,
    )
    def get_observability_metrics() -> TelemetrySnapshot:
        return telemetry_service.snapshot()

    router.include_router(protected_router)
    return router
