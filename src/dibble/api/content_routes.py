from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from dibble.api.common import ApiContext, api_error
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
from dibble.services.remediation_workflows import (
    RemediationWorkflowCompleteError,
    RemediationWorkflowNotFoundError,
)
from dibble.services.streaming import encode_sse_event


def build_content_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.post("/router/decide", response_model=AdaptiveRouteDecision, dependencies=context.deps("editor"))
    def decide_adaptive_route(request: GenerationRequest) -> AdaptiveRouteDecision:
        try:
            return services.content_workflow_service.decide_route(request)
        except LearnerProfileNotFoundError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                code="learner_profile_not_found",
            ) from exc

    @router.post("/content/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_content(request: GenerationRequest) -> GeneratedContent:
        try:
            return services.content_workflow_service.generate_content(request)
        except LearnerProfileNotFoundError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                code="learner_profile_not_found",
            ) from exc
        except RuntimeError as exc:
            raise api_error(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
                code="content_generation_failed",
            ) from exc

    @router.get("/content/{generation_id}", response_model=GeneratedContent, dependencies=context.deps("viewer"))
    def get_generated_content(generation_id: str) -> GeneratedContent:
        content = services.content_workflow_service.get_generated_content(generation_id)
        if content is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Generated content not found.",
                code="generated_content_not_found",
            )
        return content

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
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                code="learner_profile_not_found",
            ) from exc
        except RuntimeError as exc:
            raise api_error(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
                code="remediation_trigger_failed",
            ) from exc

    @router.get(
        "/remedial/sessions/{session_id}",
        response_model=RemediationWorkflowSession,
        dependencies=context.deps("viewer"),
    )
    def get_remediation_session(session_id: str) -> RemediationWorkflowSession:
        try:
            return services.content_workflow_service.get_remediation_session(session_id)
        except RemediationWorkflowNotFoundError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                code="remediation_session_not_found",
            ) from exc

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
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                code="learner_profile_not_found",
            ) from exc
        except RemediationWorkflowNotFoundError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                code="remediation_session_not_found",
            ) from exc
        except RemediationWorkflowCompleteError as exc:
            raise api_error(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
                code="remediation_session_complete",
            ) from exc
        except RuntimeError as exc:
            raise api_error(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
                code="remediation_advance_failed",
            ) from exc

    @router.post("/llm/stream", dependencies=context.deps("editor"))
    def stream_generated_content(request: GenerationRequest) -> StreamingResponse:
        try:
            prepared = services.content_workflow_service.prepare_generation_request(request)
        except LearnerProfileNotFoundError as exc:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                code="learner_profile_not_found",
            ) from exc

        def event_stream():
            try:
                complete_event: GenerationStreamEvent | None = None
                for event in services.generation_engine.stream_generate(prepared.profile, prepared.request):
                    if event.event == "moderation" and event.moderation is not None:
                        services.audit_store.append(
                            event_type="content.moderation",
                            status="success",
                            student_id=str(request.student_id),
                            payload={
                                "learning_session_id": prepared.request.learning_session_id,
                                "stage": event.moderation.stage,
                                "severity": event.moderation.severity,
                                "decision": event.moderation.decision,
                                "blocked": event.moderation.blocked,
                                "request_blocked": event.moderation.request_blocked,
                                "response_rewritten": event.moderation.response_rewritten,
                                "categories": event.moderation.categories,
                                "matched_terms": event.moderation.matched_terms,
                                "matches": [match.model_dump(mode="json") for match in event.moderation.matches],
                                "fallback_applied": event.moderation.fallback_applied,
                                "fallback_kind": event.moderation.fallback_kind,
                                "stream_action": event.moderation.stream_action,
                                "provider_invoked": event.moderation.provider_invoked,
                                "stream_buffered": event.moderation.stream_buffered,
                                "original_block_count": event.moderation.original_block_count,
                                "replacement_block_count": event.moderation.replacement_block_count,
                                "audit_message": event.moderation.audit_message,
                                "stream_emitted": True,
                            },
                        )
                    if event.event == "complete":
                        response = event.response
                        if response is not None:
                            generated_content = services.content_workflow_service.finalize_generated_content(
                                profile=prepared.profile,
                                request=prepared.request,
                                response=response,
                                progression_decision=prepared.progression_decision,
                                record_moderation_event=False,
                            )
                            event = event.model_copy(update={"workflow_summary": generated_content.workflow_summary})
                        complete_event = event
                        if response is not None:
                            services.audit_store.append(
                                event_type="content.generate.stream",
                                status="success",
                                student_id=str(request.student_id),
                                payload={
                                    "intent": prepared.request.intent.value,
                                    "content_type": generated_content.content_type,
                                    "intervention_type": response.route.intervention_type.value,
                                    "delivery_mode": response.route.delivery_mode.value,
                                    "grounding_count": len(response.grounding),
                                    "generated_block_count": len(response.blocks),
                                    "validation_issue_count": len(response.validation_issues),
                                    "generation_id": response.generation_id,
                                    "requested_target_kc_ids": prepared.progression_decision.requested_target_kc_ids,
                                    "applied_target_kc_ids": prepared.progression_decision.applied_target_kc_ids,
                                    "target_kc_ids": prepared.request.target_kc_ids,
                                    "target_lo_ids": prepared.request.target_lo_ids,
                                    "progression_action": prepared.progression_decision.action,
                                    "progression_source": prepared.progression_decision.source,
                                    "progression_target_stage": prepared.progression_decision.target_stage,
                                    "progression_target_redirect_applied": (
                                        prepared.progression_decision.target_redirect_applied
                                    ),
                                    "progression_bridge_kc_ids": prepared.progression_decision.bridge_kc_ids,
                                    "progression_transfer_target_kc_ids": (
                                        prepared.progression_decision.transfer_target_kc_ids
                                    ),
                                    "progression_deferred_target_kc_ids": (
                                        prepared.progression_decision.deferred_target_kc_ids
                                    ),
                                    "progression_rationale": prepared.progression_decision.rationale,
                                    "progression_requested_content_type": (
                                        prepared.progression_decision.requested_content_type
                                    ),
                                    "progression_applied_content_type": (
                                        prepared.progression_decision.applied_content_type
                                    ),
                                    "progression_mastery_gate_applied": (
                                        prepared.progression_decision.mastery_gate_applied
                                    ),
                                    "progression_mastery_gate_reason": (
                                        prepared.progression_decision.mastery_gate_reason
                                    ),
                                    "progression_evidence_observation_count": (
                                        prepared.progression_decision.evidence_observation_count
                                    ),
                                    "progression_evidence_assessment_count": (
                                        prepared.progression_decision.evidence_assessment_count
                                    ),
                                    "progression_evidence_confidence": (
                                        prepared.progression_decision.evidence_confidence
                                    ),
                                    "progression_average_observed_mastery": (
                                        prepared.progression_decision.average_observed_mastery
                                    ),
                                    "progression_average_assessment_mastery": (
                                        prepared.progression_decision.average_assessment_mastery
                                    ),
                                    "workflow_flow_type": (
                                        generated_content.workflow_summary.flow_type
                                        if generated_content.workflow_summary is not None
                                        else None
                                    ),
                                    "workflow_delivered_phase": (
                                        generated_content.workflow_summary.delivered_phase
                                        if generated_content.workflow_summary is not None
                                        else None
                                    ),
                                    "workflow_next_step_action": (
                                        generated_content.workflow_summary.next_step.action
                                        if generated_content.workflow_summary is not None
                                        else None
                                    ),
                                    "workflow_next_step_content_type": (
                                        generated_content.workflow_summary.next_step.content_type
                                        if generated_content.workflow_summary is not None
                                        else None
                                    ),
                                    "mode_calibration_signal": (
                                        prepared.request.mode_calibration.signal
                                        if prepared.request.mode_calibration is not None
                                        else None
                                    ),
                                    "mode_support_bias": (
                                        prepared.request.mode_calibration.support_bias
                                        if prepared.request.mode_calibration is not None
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
                                    "moderation_decision": (
                                        response.generation_metadata.moderation.decision
                                        if response.generation_metadata is not None
                                        else "allow"
                                    ),
                                    "moderation_blocked": bool(
                                        response.generation_metadata.moderation.blocked
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                    "moderation_request_blocked": bool(
                                        response.generation_metadata.moderation.request_blocked
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                    "moderation_response_rewritten": bool(
                                        response.generation_metadata.moderation.response_rewritten
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
                                    "moderation_provider_invoked": bool(
                                        response.generation_metadata.moderation.provider_invoked
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                    "moderation_stream_buffered": bool(
                                        response.generation_metadata.moderation.stream_buffered
                                        if response.generation_metadata is not None
                                        else False
                                    ),
                                    "moderation_original_block_count": (
                                        response.generation_metadata.moderation.original_block_count
                                        if response.generation_metadata is not None
                                        else 0
                                    ),
                                    "moderation_replacement_block_count": (
                                        response.generation_metadata.moderation.replacement_block_count
                                        if response.generation_metadata is not None
                                        else 0
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
                        payload={"intent": prepared.request.intent.value, "detail": "stream ended before completion"},
                    )
            except Exception as exc:
                services.audit_store.append(
                    event_type="content.generate.stream",
                    status="error",
                    student_id=str(request.student_id),
                    payload={"intent": prepared.request.intent.value, "detail": str(exc)},
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
