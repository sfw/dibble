from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from dibble.api.common import ApiContext, missing_profile
from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentWarmRequest,
    ContentWarmResult,
    GeneratedContent,
    GenerationRequest,
    GenerationStreamEvent,
    RemedialTriggerRequest,
)
from dibble.services.generation_modes import build_generation_mode_plan
from dibble.services.streaming import encode_sse_event


def build_content_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    def load_profile(student_id: UUID):
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return profile

    def generate_content_response(request: GenerationRequest) -> GeneratedContent:
        profile = load_profile(request.student_id)
        response = services.generation_engine.generate(profile, request)
        plan = build_generation_mode_plan(profile, request, response.route)
        metadata = response.generation_metadata
        if metadata is None or response.generation_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Generated content metadata was not available.",
            )

        generated_content = GeneratedContent(
            generation_id=response.generation_id,
            student_id=response.student_id,
            content_type=plan.content_type.value,
            request_context=plan.request_context,
            response=response,
            quality=metadata,
            created_at=response.generated_at,
        )
        services.audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "learning_session_id": request.learning_session_id,
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
                "target_kc_ids": request.target_kc_ids,
                "target_lo_ids": request.target_lo_ids,
                "scaffolding_level": response.route.scaffolding_level,
                "prompt_template_name": metadata.prompt_template_name,
                "prompt_template_version": metadata.prompt_template_version,
                "prompt_template_variant": metadata.prompt_template_variant,
            },
        )
        return generated_content

    @router.post("/router/decide", response_model=AdaptiveRouteDecision, dependencies=context.deps("editor"))
    def decide_adaptive_route(request: GenerationRequest) -> AdaptiveRouteDecision:
        profile = load_profile(request.student_id)
        decision = services.router_plugin.route(profile, request)
        services.audit_store.append(
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

    @router.post("/content/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_content(request: GenerationRequest) -> GeneratedContent:
        return generate_content_response(request)

    @router.post("/content/warm", response_model=ContentWarmResult, dependencies=context.deps("editor"))
    def warm_content(request: ContentWarmRequest) -> ContentWarmResult:
        warmed = services.content_warmer.warm(request.requests)
        services.audit_store.append(
            event_type="content.warm",
            status="success",
            payload={
                "total_requests": warmed.total_requests,
                "cache_hits": warmed.cache_hits,
                "cache_misses": warmed.cache_misses,
            },
        )
        return warmed

    @router.post("/explanations/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_explanation(request: GenerationRequest) -> GeneratedContent:
        explanation_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "intent": "explanation",
                "requested_content_type": "micro_explanation",
            }
        )
        return generate_content_response(explanation_request)

    @router.post("/problems/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_problem(request: GenerationRequest) -> GeneratedContent:
        problem_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "intent": "practice",
                "requested_content_type": "practice_problem",
            }
        )
        return generate_content_response(problem_request)

    @router.post("/worked-examples/generate", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def generate_worked_example(request: GenerationRequest) -> GeneratedContent:
        worked_example_request = GenerationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "requested_content_type": "worked_example",
            }
        )
        return generate_content_response(worked_example_request)

    @router.post("/remedial/trigger", response_model=GeneratedContent, dependencies=context.deps("editor"))
    def trigger_remedial_content(request: RemedialTriggerRequest) -> GeneratedContent:
        profile = services.profile_store.get(request.student_id) or missing_profile(request.student_id)
        plan = services.remediation_planner.plan(
            profile,
            request.target_kc_id,
            misconception_description=request.misconception_description,
            curriculum_context=request.curriculum_context,
        )
        generation_request = GenerationRequest(
            student_id=request.student_id,
            target_kc_ids=plan.focus_kc_ids,
            intent="remediation",
            requested_content_type="remedial_micro_module",
            learner_prompt=(
                f"{request.learner_prompt} Step back through prerequisite components before returning to the target."
                if request.learner_prompt
                else "Step back through prerequisite components before returning to the target."
            ),
            curriculum_context=[request.misconception_description, *request.curriculum_context],
        )
        generated_content = generate_content_response(generation_request)
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
        services.audit_store.append(
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

    @router.post("/llm/stream", dependencies=context.deps("editor"))
    def stream_generated_content(request: GenerationRequest) -> StreamingResponse:
        profile = load_profile(request.student_id)

        def event_stream():
            try:
                complete_event: GenerationStreamEvent | None = None
                for event in services.generation_engine.stream_generate(profile, request):
                    if event.event == "complete":
                        complete_event = event
                        response = event.response
                        if response is not None:
                            services.audit_store.append(
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
                        payload={"intent": request.intent.value, "detail": "stream ended before completion"},
                    )
            except Exception as exc:
                services.audit_store.append(
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

    return router
