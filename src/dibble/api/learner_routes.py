from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from dibble.api.common import ApiContext
from dibble.models.observations import InferredLearnerState, LearnerObservationCreate
from dibble.models.profile import LearnerProfile, LearnerProfileV2, ProfileSummary


def build_learner_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.put("/learners/{student_id}/profile", response_model=LearnerProfile, dependencies=context.deps("editor"))
    def upsert_profile(student_id: UUID, profile: LearnerProfile) -> LearnerProfile:
        if student_id != profile.student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path student_id must match the profile payload student_id.",
            )
        return services.profile_store.upsert(profile)

    @router.get("/learners/{student_id}/profile", response_model=LearnerProfileV2, dependencies=context.deps("viewer"))
    def get_profile(student_id: UUID) -> LearnerProfileV2:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return LearnerProfileV2.from_profile(profile)

    @router.get("/learners", response_model=list[str], dependencies=context.deps("viewer"))
    def list_profiles() -> list[str]:
        return services.profile_store.list_ids()

    @router.post(
        "/learners/{student_id}/observations",
        response_model=InferredLearnerState,
        dependencies=context.deps("editor"),
    )
    def observe_learner_state(student_id: UUID, observation: LearnerObservationCreate) -> InferredLearnerState:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")

        services.observation_store.append(student_id=str(student_id), observation=observation)
        recent_observations = services.observation_store.list_recent(student_id=str(student_id))
        inferred_state = services.state_inference_service.infer(student_id=student_id, observations=recent_observations)
        calibration = services.learner_state_calibrator.calibrate(
            student_id=student_id,
            observation=observation,
            inferred_state=inferred_state,
        )
        inferred_state = calibration.state
        inferred_cognitive_traits = services.cognitive_trait_inference_service.infer(
            observations=recent_observations,
            existing_traits=profile.cognitive_traits,
        )
        updated_profile = profile.model_copy(
            update={
                "cognitive_traits": inferred_cognitive_traits,
                "affective_state": inferred_state.affective_state,
                "cognitive_load": inferred_state.cognitive_load,
                "metacognitive_state": inferred_state.metacognitive_state,
                "updated_at": inferred_state.last_observation_at or profile.updated_at,
            }
        )
        services.profile_store.upsert(updated_profile)
        observation_audit_event = services.audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=str(student_id),
            payload={
                "observation_count": inferred_state.observation_count,
                "response_time_ms": observation.response_time_ms,
                "hints_used": observation.hints_used,
                "error_count": observation.error_count,
                "task_type": observation.task_type.value,
                "support_level": observation.support_level.value,
                "learning_session_id": observation.learning_session_id,
                "generation_id": observation.generation_id,
                "observed_content_type": observation.observed_content_type,
                "target_kc_ids": observation.target_kc_ids,
                "target_lo_ids": observation.target_lo_ids,
                "engagement": inferred_state.affective_state.engagement.value,
                "frustration": inferred_state.affective_state.frustration.value,
                "total_load": inferred_state.cognitive_load.total_load,
                "confidence_calibration": inferred_state.metacognitive_state.confidence_calibration,
                "help_seeking": inferred_state.metacognitive_state.help_seeking.value,
                "updated_cognitive_traits": sorted(inferred_cognitive_traits.keys()),
                "state_calibration_signal": calibration.signal,
                "state_calibration_confidence": calibration.confidence,
                "state_calibration_run_count": calibration.matched_run_count,
                "state_calibration_outcome_score": calibration.average_run_outcome_score,
                "state_calibration_applied": calibration.applied,
            },
        )
        services.predictive_content_invalidator.invalidate_from_trigger_event(observation_audit_event)
        summary_events = services.learning_run_summary_recorder.record_from_trigger_event(
            trigger_event=observation_audit_event
        )
        services.learning_calibration_profile_recorder.record_from_summary_events(summary_events=summary_events)
        return inferred_state

    @router.get("/learners/{student_id}/state", response_model=InferredLearnerState, dependencies=context.deps("viewer"))
    def get_inferred_learner_state(student_id: UUID) -> InferredLearnerState:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        observations = services.observation_store.list_recent(student_id=str(student_id))
        if observations:
            inferred_state = services.state_inference_service.infer(student_id=student_id, observations=observations)
            latest_observation = observations[0]
            return services.learner_state_calibrator.calibrate(
                student_id=student_id,
                observation=latest_observation,
                inferred_state=inferred_state,
            ).state
        return InferredLearnerState(
            student_id=student_id,
            affective_state=profile.affective_state,
            cognitive_load=profile.cognitive_load,
            metacognitive_state=profile.metacognitive_state,
            observation_count=0,
            last_observation_at=None,
        )

    @router.get("/learners/{student_id}/summary", response_model=ProfileSummary, dependencies=context.deps("viewer"))
    def get_profile_summary(student_id: UUID) -> ProfileSummary:
        summary = services.learner_summary_service.build_for_student(student_id=student_id)
        if summary is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return summary

    return router
