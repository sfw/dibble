from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from dibble.api.common import ApiContext
from dibble.models.assessment import (
    SocraticAssessmentRequest,
    SocraticAssessmentResponse,
    SocraticAssessmentSession,
)


def build_assessment_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.post(
        "/assessments/socratic",
        response_model=SocraticAssessmentResponse,
        dependencies=context.deps("editor"),
    )
    def assess_socratically(request: SocraticAssessmentRequest) -> SocraticAssessmentResponse:
        profile = services.profile_store.get(request.student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")

        result = services.socratic_assessment_service.assess(profile, request)
        session = services.socratic_session_store.get(result.session_id)
        profile_update = services.socratic_profile_updater.apply(profile, request, result, session)
        if profile_update.applied:
            services.profile_store.upsert(profile_update.profile)
        assessment_audit_event = services.audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=str(request.student_id),
            payload={
                "session_id": result.session_id,
                "learning_session_id": result.learning_session_id,
                "generation_id": result.generation_id,
                "target_kc_ids": request.target_kc_ids,
                "target_lo_ids": request.target_lo_ids,
                "evidence_strength": result.evaluation.evidence_strength.value,
                "evidence_score": result.evaluation.evidence_score,
                "inferred_mastery": result.evaluation.inferred_mastery,
                "next_action": result.evaluation.next_action.value,
                "matched_term_count": len(result.evaluation.matched_terms),
                "profile_update_applied": profile_update.applied,
                "updated_kc_mastery": profile_update.kc_mastery_updates,
                "updated_lo_mastery": profile_update.lo_mastery_updates,
                "propagated_kc_mastery": profile_update.propagated_kc_mastery_updates or {},
                "propagated_lo_mastery": profile_update.propagated_lo_mastery_updates or {},
                "updated_confidence_calibration": profile_update.confidence_calibration,
                "updated_self_monitoring": profile_update.self_monitoring,
                "updated_help_seeking": (
                    profile_update.help_seeking.value if profile_update.help_seeking is not None else None
                ),
                "prompt_style": result.prompt_style.value,
                "steering_action": result.steering_action.value,
                "prompt_template_name": (
                    result.generation_metadata.prompt_template_name
                    if result.generation_metadata is not None
                    else None
                ),
                "prompt_template_variant": (
                    result.generation_metadata.prompt_template_variant
                    if result.generation_metadata is not None
                    else None
                ),
            },
        )
        services.within_session_adaptation_service.record_assessment_event(
            student_id=request.student_id,
            event_payload=assessment_audit_event.payload,
        )
        services.predictive_content_invalidator.invalidate_from_trigger_event(assessment_audit_event)
        summary_events = services.learning_run_summary_recorder.record_from_trigger_event(
            trigger_event=assessment_audit_event
        )
        services.learning_calibration_profile_recorder.record_from_summary_events(summary_events=summary_events)
        services.learning_progress_profile_recorder.record_from_summary_events(summary_events=summary_events)
        services.learning_strategy_profile_recorder.record_from_summary_events(summary_events=summary_events)
        services.learning_state_profile_recorder.record_from_summary_events(summary_events=summary_events)
        return result

    @router.get(
        "/assessments/socratic/{session_id}",
        response_model=SocraticAssessmentSession,
        dependencies=context.deps("viewer"),
    )
    def get_socratic_assessment_session(session_id: str) -> SocraticAssessmentSession:
        session = services.socratic_session_store.get(session_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Socratic assessment session not found.")
        return session

    return router
