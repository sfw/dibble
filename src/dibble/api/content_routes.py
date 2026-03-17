from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from dibble.api.common import ApiContext
from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentWarmRequest,
    ContentWarmResult,
    GeneratedContent,
    GenerationRequest,
    PredictiveWarmProcessRequest,
    PredictiveWarmProcessResult,
    GenerationStreamEvent,
    RemedialTriggerRequest,
)
from dibble.models.remediation import (
    RemediationWorkflowAdvanceRequest,
    RemediationWorkflowAdvanceResponse,
    RemediationWorkflowSession,
)
from dibble.services.content_workflow import LearnerProfileNotFoundError
from dibble.services.generation_request_hydrator import hydrate_target_kc_hints
from dibble.services.remediation_workflows import (
    RemediationWorkflowCompleteError,
    RemediationWorkflowNotFoundError,
)
from dibble.services.streaming import encode_sse_event


def build_content_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    def load_profile(student_id):
        try:
            return services.content_workflow_service.load_profile(student_id)
        except LearnerProfileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post("/router/decide", response_model=AdaptiveRouteDecision, dependencies=context.deps("editor"))
    def decide_adaptive_route(request: GenerationRequest) -> AdaptiveRouteDecision:
        try:
            return services.content_workflow_service.decide_route(request)
        except LearnerProfileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post("/content/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_content(request: GenerationRequest) -> GeneratedContent:
        try:
            return services.content_workflow_service.generate_content(request)
        except LearnerProfileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/content/warm", response_model=ContentWarmResult, dependencies=context.deps("editor"))
    def warm_content(request: ContentWarmRequest) -> ContentWarmResult:
        return services.content_workflow_service.warm_content(request)

    @router.post(
        "/content/warm/process",
        response_model=PredictiveWarmProcessResult,
        dependencies=context.deps("editor"),
    )
    def process_predictive_warm_queue(
        request: PredictiveWarmProcessRequest,
    ) -> PredictiveWarmProcessResult:
        return services.content_workflow_service.process_predictive_warm_queue(limit=request.limit)

    @router.post("/explanations/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_explanation(request: GenerationRequest) -> GeneratedContent:
        explanation_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "intent": "explanation",
                "requested_content_type": "micro_explanation",
            }
        )
        return generate_content(explanation_request)

    @router.post("/problems/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_problem(request: GenerationRequest) -> GeneratedContent:
        problem_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "intent": "practice",
                "requested_content_type": "practice_problem",
            }
        )
        return generate_content(problem_request)

    @router.post("/worked-examples/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_worked_example(request: GenerationRequest) -> GeneratedContent:
        worked_example_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "requested_content_type": "worked_example",
            }
        )
        return generate_content(worked_example_request)

    @router.post("/remedial/trigger", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def trigger_remedial_content(request: RemedialTriggerRequest) -> GeneratedContent:
        try:
            return services.content_workflow_service.trigger_remedial_content(request)
        except LearnerProfileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.get(
        "/remedial/sessions/{session_id}",
        response_model=RemediationWorkflowSession,
        dependencies=context.deps("viewer"),
    )
    def get_remediation_session(session_id: str) -> RemediationWorkflowSession:
        try:
            return services.content_workflow_service.get_remediation_session(session_id)
        except RemediationWorkflowNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @router.post(
        "/remedial/sessions/{session_id}/advance",
        response_model=RemediationWorkflowAdvanceResponse,
        dependencies=context.deps("editor"),
    )
    def advance_remediation_session(
        session_id: str,
        request: RemediationWorkflowAdvanceRequest,
    ) -> RemediationWorkflowAdvanceResponse:
        try:
            return services.content_workflow_service.advance_remediation_session(
                session_id=session_id,
                request=request,
            )
        except LearnerProfileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RemediationWorkflowNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RemediationWorkflowCompleteError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/llm/stream", dependencies=context.deps("editor"))
    def stream_generated_content(request: GenerationRequest) -> StreamingResponse:
        profile = load_profile(request.student_id)
        enriched_request = hydrate_target_kc_hints(
            request=request,
            knowledge_component_store=services.knowledge_component_store,
        )
        calibrated_request = services.generation_mode_calibrator.calibrate_request(request=enriched_request)

        def event_stream():
            try:
                complete_event: GenerationStreamEvent | None = None
                for event in services.generation_engine.stream_generate(profile, calibrated_request):
                    if event.event == "moderation" and event.moderation is not None:
                        services.audit_store.append(
                            event_type="content.moderation",
                            status="success",
                            student_id=str(request.student_id),
                            payload={
                                "learning_session_id": calibrated_request.learning_session_id,
                                "stage": event.moderation.stage,
                                "severity": event.moderation.severity,
                                "blocked": event.moderation.blocked,
                                "categories": event.moderation.categories,
                                "matched_terms": event.moderation.matched_terms,
                                "matches": [match.model_dump(mode="json") for match in event.moderation.matches],
                                "fallback_applied": event.moderation.fallback_applied,
                                "fallback_kind": event.moderation.fallback_kind,
                                "stream_action": event.moderation.stream_action,
                                "audit_message": event.moderation.audit_message,
                                "stream_emitted": True,
                            },
                        )
                    if event.event == "complete":
                        complete_event = event
                        response = event.response
                        if response is not None:
                            services.audit_store.append(
                                event_type="content.generate.stream",
                                status="success",
                                student_id=str(request.student_id),
                                payload={
                                    "intent": calibrated_request.intent.value,
                                    "intervention_type": response.route.intervention_type.value,
                                    "delivery_mode": response.route.delivery_mode.value,
                                    "grounding_count": len(response.grounding),
                                    "generated_block_count": len(response.blocks),
                                    "validation_issue_count": len(response.validation_issues),
                                    "generation_id": response.generation_id,
                                    "mode_calibration_signal": (
                                        calibrated_request.mode_calibration.signal
                                        if calibrated_request.mode_calibration is not None
                                        else None
                                    ),
                                    "mode_support_bias": (
                                        calibrated_request.mode_calibration.support_bias
                                        if calibrated_request.mode_calibration is not None
                                        else 0
                                    ),
                                    "cache_hit": bool(
                                        response.generation_metadata.cache_hit
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                    "moderation_status": (
                                        response.generation_metadata.moderation.status
                                        if response.generation_metadata is not None
                                        else "clear"
                                    ),
                                    "moderation_stage": (
                                        response.generation_metadata.moderation.stage
                                        if response.generation_metadata is not None
                                        else "none"
                                    ),
                                    "moderation_categories": (
                                        response.generation_metadata.moderation.categories
                                        if response.generation_metadata is not None
                                        else []
                                    ),
                                    "moderation_reasons": (
                                        response.generation_metadata.moderation.reasons
                                        if response.generation_metadata is not None
                                        else []
                                    ),
                                    "moderation_matches": (
                                        [
                                            match.model_dump(mode="json")
                                            for match in response.generation_metadata.moderation.matches
                                        ]
                                        if response.generation_metadata is not None
                                        else []
                                    ),
                                    "moderation_severity": (
                                        response.generation_metadata.moderation.severity
                                        if response.generation_metadata is not None
                                        else "none"
                                    ),
                                    "moderation_blocked": bool(
                                        response.generation_metadata.moderation.blocked
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                    "moderation_matched_terms": (
                                        response.generation_metadata.moderation.matched_terms
                                        if response.generation_metadata is not None
                                        else []
                                    ),
                                    "moderation_fallback_applied": bool(
                                        response.generation_metadata.moderation.fallback_applied
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                    "moderation_fallback_kind": (
                                        response.generation_metadata.moderation.fallback_kind
                                        if response.generation_metadata is not None
                                        else None
                                    ),
                                    "moderation_stream_action": (
                                        response.generation_metadata.moderation.stream_action
                                        if response.generation_metadata is not None
                                        else "none"
                                    ),
                                    "moderation_audit_message": (
                                        response.generation_metadata.moderation.audit_message
                                        if response.generation_metadata is not None
                                        else None
                                    ),
                                    "prompt_template_name": (
                                        response.generation_metadata.prompt_template_name
                                        if response.generation_metadata is not None
                                        else None
                                    ),
                                    "prompt_template_version": (
                                        response.generation_metadata.prompt_template_version
                                        if response.generation_metadata is not None
                                        else None
                                    ),
                                    "prompt_template_variant": (
                                        response.generation_metadata.prompt_template_variant
                                        if response.generation_metadata is not None
                                        else None
                                    ),
                                },
                            )
                    yield encode_sse_event(event)

                if complete_event is None:
                    services.audit_store.append(
                        event_type="content.generate.stream",
                        status="error",
                        student_id=str(request.student_id),
                        payload={"intent": calibrated_request.intent.value, "detail": "stream ended before completion"},
                    )
            except Exception as exc:
                services.audit_store.append(
                    event_type="content.generate.stream",
                    status="error",
                    student_id=str(request.student_id),
                    payload={"intent": calibrated_request.intent.value, "detail": str(exc)},
                )
                yield encode_sse_event(
                    GenerationStreamEvent(
                        event="error",
                        student_id=request.student_id,
                        validation_issues=[str(exc)],
                    )
                )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return router
