from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from dibble.models.auth import AuthIdentity, AuthRefreshRequest, AuthRevokeRequest, AuthToken
from dibble.models.curriculum import (
    CurriculumResource,
    CurriculumResourceUpsert,
    KnowledgeComponent,
    KnowledgeComponentUpsert,
)
from dibble.models.generation import (
    AdaptiveRouteDecision,
    GeneratedContent,
    GenerationRequest,
    GenerationStreamEvent,
    RemedialTriggerRequest,
)
from dibble.models.observations import InferredLearnerState, LearnerObservationCreate
from dibble.models.profile import LearnerProfile, LearnerProfileV2, ProfileSummary
from dibble.models.telemetry import AuditEvent, TelemetrySnapshot
from dibble.plugins.contracts import RouterPlugin
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import (
    AuthService,
    AuthenticationError,
    AuthorizationError,
    TokenConfigurationError,
)
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.services.streaming import encode_sse_event
from dibble.services.telemetry import TelemetryService


def build_router(
    profile_store: SQLiteProfileStore,
    curriculum_store: SQLiteCurriculumStore,
    knowledge_component_store: SQLiteKnowledgeComponentStore,
    audit_store: SQLiteAuditStore,
    observation_store: SQLiteObservationStore,
    auth_service: AuthService,
    telemetry_service: TelemetryService,
    router_service: RouterPlugin,
    generation_engine: GenerationEngine,
    remediation_planner: RemediationPlanner,
    state_inference_service: LearnerStateInferenceService,
) -> APIRouter:
    router = APIRouter()
    api_router = APIRouter(prefix="/api")

    def require_access(*allowed_roles: str):
        async def dependency(
            request: Request,
            api_key: str | None = Header(default=None, alias=auth_service.header_name),
            authorization: str | None = Header(default=None, alias="Authorization"),
        ) -> AuthIdentity:
            bearer_token = None
            if authorization and authorization.lower().startswith("bearer "):
                bearer_token = authorization[7:].strip()
            try:
                session = auth_service.authorize(
                    provided_key=api_key,
                    bearer_token=bearer_token,
                    allowed_roles=tuple(allowed_roles) or ("viewer",),
                )
                identity = session.identity
                request.state.auth_identity = identity
                return identity
            except AuthenticationError as exc:
                audit_store.append(
                    event_type="auth.request",
                    status="denied",
                    payload={
                        "path": request.url.path,
                        "method": request.method,
                        "header_name": auth_service.header_name,
                        "required_roles": list(allowed_roles or ("viewer",)),
                    },
                )
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
            except AuthorizationError as exc:
                identity = auth_service.authenticate(api_key)
                audit_store.append(
                    event_type="auth.request",
                    status="forbidden",
                    payload={
                        "path": request.url.path,
                        "method": request.method,
                        "header_name": auth_service.header_name,
                        "principal_id": identity.principal_id,
                        "role": identity.role,
                        "required_roles": list(allowed_roles or ("viewer",)),
                    },
                )
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

        return dependency

    @router.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    def deps(*roles: str):
        if not auth_service.enabled:
            return []
        return [Depends(require_access(*roles))]

    @api_router.get("/auth/me", response_model=AuthIdentity, dependencies=deps("viewer"))
    def get_current_identity(request: Request) -> AuthIdentity:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            return auth_service.authenticate(None)
        return identity

    @api_router.post("/auth/token", response_model=AuthToken, dependencies=deps("viewer"))
    def issue_access_token(request: Request) -> AuthToken:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            return auth_service.issue_token(auth_service.authenticate(None))
        try:
            token = auth_service.issue_token(identity)
        except TokenConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        audit_store.append(
            event_type="auth.token",
            status="issued",
            payload={"principal_id": identity.principal_id, "role": identity.role},
        )
        return token

    @api_router.post("/auth/token/refresh", response_model=AuthToken)
    def refresh_access_token(payload: AuthRefreshRequest) -> AuthToken:
        try:
            token = auth_service.refresh_session(payload.refresh_token)
        except (AuthenticationError, TokenConfigurationError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        audit_store.append(
            event_type="auth.token",
            status="refreshed",
            payload={
                "principal_id": token.identity.principal_id,
                "role": token.identity.role,
            },
        )
        return token

    @api_router.post("/auth/token/revoke")
    def revoke_access_token(
        payload: AuthRevokeRequest | None = None,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, str]:
        bearer_token = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer_token = authorization[7:].strip()

        try:
            auth_service.revoke_session(
                refresh_token=payload.refresh_token if payload is not None else None,
                bearer_token=bearer_token,
            )
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        audit_store.append(
            event_type="auth.token",
            status="revoked",
            payload={"mode": "refresh" if payload and payload.refresh_token else "bearer"},
        )
        return {"status": "revoked"}

    @api_router.put("/learners/{student_id}/profile", response_model=LearnerProfile, dependencies=deps("editor"))
    def upsert_profile(student_id: UUID, profile: LearnerProfile) -> LearnerProfile:
        if student_id != profile.student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path student_id must match the profile payload student_id.",
            )
        return profile_store.upsert(profile)

    @api_router.get("/learners/{student_id}/profile", response_model=LearnerProfileV2, dependencies=deps("viewer"))
    def get_profile(student_id: UUID) -> LearnerProfileV2:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return LearnerProfileV2.from_profile(profile)

    @api_router.get("/learners", response_model=list[str], dependencies=deps("viewer"))
    def list_profiles() -> list[str]:
        return profile_store.list_ids()

    @api_router.post(
        "/learners/{student_id}/observations",
        response_model=InferredLearnerState,
        dependencies=deps("editor"),
    )
    def observe_learner_state(student_id: UUID, observation: LearnerObservationCreate) -> InferredLearnerState:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")

        observation_store.append(student_id=str(student_id), observation=observation)
        recent_observations = observation_store.list_recent(student_id=str(student_id))
        inferred_state = state_inference_service.infer(student_id=student_id, observations=recent_observations)
        updated_profile = profile.model_copy(
            update={
                "affective_state": inferred_state.affective_state,
                "cognitive_load": inferred_state.cognitive_load,
                "updated_at": inferred_state.last_observation_at or profile.updated_at,
            }
        )
        profile_store.upsert(updated_profile)
        audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=str(student_id),
            payload={
                "observation_count": inferred_state.observation_count,
                "response_time_ms": observation.response_time_ms,
                "hints_used": observation.hints_used,
                "error_count": observation.error_count,
                "engagement": inferred_state.affective_state.engagement.value,
                "frustration": inferred_state.affective_state.frustration.value,
                "total_load": inferred_state.cognitive_load.total_load,
            },
        )
        return inferred_state

    @api_router.get(
        "/learners/{student_id}/state",
        response_model=InferredLearnerState,
        dependencies=deps("viewer"),
    )
    def get_inferred_learner_state(student_id: UUID) -> InferredLearnerState:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        observations = observation_store.list_recent(student_id=str(student_id))
        if observations:
            return state_inference_service.infer(student_id=student_id, observations=observations)
        return InferredLearnerState(
            student_id=student_id,
            affective_state=profile.affective_state,
            cognitive_load=profile.cognitive_load,
            observation_count=0,
            last_observation_at=None,
        )

    @api_router.get(
        "/learners/{student_id}/summary",
        response_model=ProfileSummary,
        dependencies=deps("viewer"),
    )
    def get_profile_summary(student_id: UUID) -> ProfileSummary:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return ProfileSummary.from_profile(profile)

    @api_router.put(
        "/curriculum/resources/{resource_id}",
        response_model=CurriculumResource,
        dependencies=deps("editor"),
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

    @api_router.get(
        "/curriculum/resources",
        response_model=list[CurriculumResource],
        dependencies=deps("viewer"),
    )
    def list_curriculum_resources() -> list[CurriculumResource]:
        return curriculum_store.list()

    @api_router.put(
        "/knowledge-components/{kc_id}",
        response_model=KnowledgeComponent,
        dependencies=deps("editor"),
    )
    def upsert_knowledge_component(
        kc_id: str,
        component: KnowledgeComponentUpsert,
    ) -> KnowledgeComponent:
        if kc_id != component.kc_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path kc_id must match the knowledge component payload kc_id.",
            )
        return knowledge_component_store.upsert(component)

    @api_router.get(
        "/knowledge-components",
        response_model=list[KnowledgeComponent],
        dependencies=deps("viewer"),
    )
    def list_knowledge_components() -> list[KnowledgeComponent]:
        return knowledge_component_store.list()

    @api_router.get(
        "/knowledge-components/{kc_id}/prerequisites",
        response_model=list[KnowledgeComponent],
        dependencies=deps("viewer"),
    )
    def list_knowledge_component_prerequisites(kc_id: str) -> list[KnowledgeComponent]:
        component = knowledge_component_store.get(kc_id)
        if component is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge component not found.")
        return knowledge_component_store.list_prerequisites(kc_id)

    @api_router.post(
        "/router/decide",
        response_model=AdaptiveRouteDecision,
        dependencies=deps("editor"),
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

    @api_router.post(
        "/content/generate",
        response_model=GeneratedContent,
        dependencies=deps("editor"),
    )
    def generate_content(request: GenerationRequest) -> GeneratedContent:
        profile = profile_store.get(request.student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")

        response = generation_engine.generate(profile, request)
        metadata = response.generation_metadata
        if metadata is None or response.generation_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Generated content metadata was not available.",
            )

        generated_content = GeneratedContent(
            generation_id=response.generation_id,
            student_id=response.student_id,
            content_type=_content_type_label(request),
            request_context={
                "intent": request.intent.value,
                "target_kc_ids": request.target_kc_ids,
                "target_lo_ids": request.target_lo_ids,
                "curriculum_context": request.curriculum_context,
            },
            response=response,
            quality=metadata,
            created_at=response.generated_at,
        )

        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "content_type": generated_content.content_type,
                "generation_id": generated_content.generation_id,
                "intervention_type": response.route.intervention_type.value,
                "delivery_mode": response.route.delivery_mode.value,
                "grounding_count": len(response.grounding),
                "generated_block_count": len(response.blocks),
                "validation_issue_count": len(response.validation_issues),
                "validation_passed": metadata.validation_passed,
                "cache_hit": metadata.cache_hit,
                "quality_score": metadata.quality_score,
            },
        )
        return generated_content

    @api_router.post(
        "/explanations/generate",
        response_model=GeneratedContent,
        dependencies=deps("editor"),
    )
    def generate_explanation(request: GenerationRequest) -> GeneratedContent:
        explanation_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "intent": "explanation",
            }
        )
        return generate_content(explanation_request)

    @api_router.post(
        "/problems/generate",
        response_model=GeneratedContent,
        dependencies=deps("editor"),
    )
    def generate_problem(request: GenerationRequest) -> GeneratedContent:
        problem_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "intent": "practice",
            }
        )
        return generate_content(problem_request)

    @api_router.post(
        "/remedial/trigger",
        response_model=GeneratedContent,
        dependencies=deps("editor"),
    )
    def trigger_remedial_content(request: RemedialTriggerRequest) -> GeneratedContent:
        profile = profile_store.get(request.student_id) or _missing_profile(request.student_id)
        plan = remediation_planner.plan(
            profile,
            request.target_kc_id,
            misconception_description=request.misconception_description,
            curriculum_context=request.curriculum_context,
        )
        generation_request = GenerationRequest(
            student_id=request.student_id,
            target_kc_ids=plan.focus_kc_ids,
            intent="remediation",
            learner_prompt=(
                f"{request.learner_prompt} Step back through prerequisite components before returning to the target."
                if request.learner_prompt
                else "Step back through prerequisite components before returning to the target."
            ),
            curriculum_context=[request.misconception_description, *request.curriculum_context],
        )
        generated_content = generate_content(generation_request)
        enriched_request_context = {
            **generated_content.request_context,
            "target_kc_id": request.target_kc_id,
            "focus_kc_ids": plan.focus_kc_ids,
            "prerequisite_kc_ids": plan.prerequisite_kc_ids,
            "misconception_description": request.misconception_description,
            "misconception_signals": [signal.model_dump(mode="json") for signal in plan.misconception_signals],
            "remediation_rationale": plan.rationale,
        }
        enriched_content = generated_content.model_copy(update={"request_context": enriched_request_context})
        audit_store.append(
            event_type="remediation.trigger",
            status="success",
            student_id=str(request.student_id),
            payload={
                "target_kc_id": request.target_kc_id,
                "focus_kc_ids": plan.focus_kc_ids,
                "prerequisite_kc_ids": plan.prerequisite_kc_ids,
                "misconception_signal_count": len(plan.misconception_signals),
                "misconception_signals": [signal.model_dump(mode="json") for signal in plan.misconception_signals],
                "generation_id": enriched_content.generation_id,
                "rationale": plan.rationale,
            },
        )
        return enriched_content

    @api_router.post("/llm/stream", dependencies=deps("editor"))
    def stream_generated_content(request: GenerationRequest) -> StreamingResponse:
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
                                event_type="content.generate.stream",
                                status="success",
                                student_id=str(request.student_id),
                                payload={
                                    "intent": request.intent.value,
                                    "intervention_type": response.route.intervention_type.value,
                                    "delivery_mode": response.route.delivery_mode.value,
                                    "grounding_count": len(response.grounding),
                                    "generated_block_count": len(response.blocks),
                                    "validation_issue_count": len(response.validation_issues),
                                    "generation_id": response.generation_id,
                                    "cache_hit": bool(
                                        response.generation_metadata.cache_hit
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                },
                            )
                    yield encode_sse_event(event)

                if complete_event is None:
                    audit_store.append(
                        event_type="content.generate.stream",
                        status="error",
                        student_id=str(request.student_id),
                        payload={"intent": request.intent.value, "detail": "stream ended before completion"},
                    )
            except Exception as exc:
                audit_store.append(
                    event_type="content.generate.stream",
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

    @api_router.get("/audit/events", response_model=list[AuditEvent], dependencies=deps("admin"))
    def list_audit_events(limit: int = 50) -> list[AuditEvent]:
        safe_limit = max(1, min(limit, 200))
        return audit_store.list(limit=safe_limit)

    @api_router.get(
        "/observability/metrics",
        response_model=TelemetrySnapshot,
        dependencies=deps("admin"),
    )
    def get_observability_metrics() -> TelemetrySnapshot:
        return telemetry_service.snapshot()

    router.include_router(api_router)
    return router


def _content_type_label(request: GenerationRequest) -> str:
    if request.intent.value == "remediation":
        return "remedial_micro_module"
    if request.intent.value == "practice":
        return "practice_problem"
    if request.intent.value == "assessment":
        return "assessment_probe"
    return "micro_explanation"


def _missing_profile(student_id: UUID) -> LearnerProfile:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Learner profile not found for student_id {student_id}.",
    )
