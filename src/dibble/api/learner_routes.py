from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from dibble.api.common import ApiContext, api_error
from dibble.models.history import (
    LearnerGenerationHistoryPage,
    LearnerRemediationSessionHistoryPage,
    LearnerSocraticSessionHistoryPage,
)
from dibble.models.observations import InferredLearnerState, LearnerObservationCreate
from dibble.models.mastery_history import MasteryHistoryResponse
from dibble.models.profile import (
    LearnerCurriculumProgressionSummary,
    LearnerFlowSummary,
    LearnerProfile,
    LearnerProfileV2,
    ProfileSummary,
)
from dibble.models.teacher_actions import (
    TeacherInterventionActionContract,
    TeacherInterventionDecisionRequest,
)
from dibble.models.workspace import LearnerWorkspace
from dibble.services.teacher_intervention_actions import (
    TeacherInterventionActionUnavailableError,
    TeacherInterventionOptionNotFoundError,
)


def build_learner_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.put(
        "/learners/{student_id}/profile",
        response_model=LearnerProfile,
        dependencies=context.deps("editor"),
    )
    def upsert_profile(student_id: UUID, profile: LearnerProfile) -> LearnerProfile:
        if student_id != profile.student_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path student_id must match the profile payload student_id.",
                code="learner_profile_id_mismatch",
            )
        return services.profile_store.upsert(profile)

    @router.get(
        "/learners/{student_id}/profile",
        response_model=LearnerProfileV2,
        dependencies=context.deps("viewer"),
    )
    def get_profile(student_id: UUID) -> LearnerProfileV2:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return LearnerProfileV2.from_profile(profile)

    @router.get(
        "/learners", response_model=list[str], dependencies=context.deps("viewer")
    )
    def list_profiles() -> list[str]:
        return services.profile_store.list_ids()

    @router.post(
        "/learners/{student_id}/observations",
        response_model=InferredLearnerState,
        dependencies=context.deps("editor"),
    )
    def observe_learner_state(
        student_id: UUID, observation: LearnerObservationCreate
    ) -> InferredLearnerState:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )

        persisted_observation = services.observation_store.append(
            student_id=str(student_id), observation=observation
        )
        recent_observations = services.observation_store.list_recent(
            student_id=str(student_id)
        )
        inferred_state = services.state_inference_service.infer(
            student_id=student_id, observations=recent_observations
        )
        calibration = services.learner_state_calibrator.calibrate(
            student_id=student_id,
            observation=observation,
            inferred_state=inferred_state,
        )
        inferred_state = calibration.state
        inferred_cognitive_traits = services.cognitive_trait_inference_service.infer(
            student_id=student_id,
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
        observation_profile_update = services.observation_profile_updater.apply(
            updated_profile,
            persisted_observation,
            recent_observations=recent_observations,
        )
        updated_profile = observation_profile_update.profile
        services.profile_store.upsert(updated_profile)
        services.mastery_snapshot_service.record_from_profile(updated_profile)
        progression_outcomes = (
            services.progression_outcome_tracker.evaluate_recent_decisions(
                student_id=str(student_id),
                current_kc_mastery=updated_profile.knowledge_state.kc_mastery,
            )
        )
        if progression_outcomes:
            services.progression_outcome_tracker.record_outcomes(progression_outcomes)
        remediation_outcomes = (
            services.misconception_remediation_outcome_tracker.evaluate_recent_sessions(
                student_id=str(student_id),
                current_kc_mastery=updated_profile.knowledge_state.kc_mastery,
            )
        )
        if remediation_outcomes:
            services.misconception_remediation_outcome_tracker.record_outcomes(
                remediation_outcomes
            )
        observation_audit_event = services.audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=str(student_id),
            payload={
                "observation_count": inferred_state.observation_count,
                "response_time_ms": observation.response_time_ms,
                "hints_used": observation.hints_used,
                "error_count": observation.error_count,
                "pause_count": observation.pause_count,
                "modality_switches": observation.modality_switches,
                "completed": observation.completed,
                "expected_duration_ms": observation.expected_duration_ms,
                "task_type": observation.task_type.value,
                "support_level": observation.support_level.value,
                "learning_session_id": observation.learning_session_id,
                "generation_id": observation.generation_id,
                "observed_content_type": observation.observed_content_type,
                "target_kc_ids": observation.target_kc_ids,
                "target_lo_ids": observation.target_lo_ids,
                "observation_mastery_applied": observation_profile_update.applied,
                "observation_inferred_mastery": observation_profile_update.inferred_mastery,
                "observation_evidence_strength": (
                    observation_profile_update.evidence_strength.value
                    if observation_profile_update.evidence_strength is not None
                    else None
                ),
                "observation_mastery_linkage_source": observation_profile_update.linkage_source,
                "observation_matched_observation_count": observation_profile_update.matched_observation_count,
                "observation_average_recent_mastery": observation_profile_update.average_recent_observed_mastery,
                "observation_evidence_confidence": observation_profile_update.evidence_confidence,
                "durable_mastery_signal": observation_profile_update.durable_mastery_signal,
                "durable_mastery_source": observation_profile_update.durable_mastery_source,
                "durable_mastery_confidence": observation_profile_update.durable_mastery_confidence,
                "durable_mastery_matched_observation_count": observation_profile_update.durable_mastery_matched_observation_count,
                "durable_mastery_average_observed_mastery": observation_profile_update.durable_mastery_average_observed_mastery,
                "durable_mastery_low_support_success_rate": observation_profile_update.durable_mastery_low_support_success_rate,
                "durable_mastery_high_support_dependency_rate": observation_profile_update.durable_mastery_high_support_dependency_rate,
                "durable_mastery_rationale": observation_profile_update.durable_mastery_rationale,
                "updated_kc_mastery": observation_profile_update.kc_mastery_updates
                or {},
                "updated_lo_mastery": observation_profile_update.lo_mastery_updates
                or {},
                "propagated_kc_mastery": observation_profile_update.propagated_kc_mastery_updates
                or {},
                "propagated_lo_mastery": observation_profile_update.propagated_lo_mastery_updates
                or {},
                "observation_mastery_rationale": observation_profile_update.rationale,
                "engagement": inferred_state.affective_state.engagement.value,
                "frustration": inferred_state.affective_state.frustration.value,
                "total_load": inferred_state.cognitive_load.total_load,
                "confidence_calibration": inferred_state.metacognitive_state.confidence_calibration,
                "help_seeking": inferred_state.metacognitive_state.help_seeking.value,
                "current_evidence_signal": (
                    inferred_state.current_evidence.signal
                    if inferred_state.current_evidence is not None
                    else "steady"
                ),
                "current_evidence_confidence": (
                    inferred_state.current_evidence.confidence
                    if inferred_state.current_evidence is not None
                    else 0.0
                ),
                "current_evidence_rationale": (
                    inferred_state.current_evidence.rationale
                    if inferred_state.current_evidence is not None
                    else None
                ),
                "updated_cognitive_traits": sorted(inferred_cognitive_traits.keys()),
                "state_calibration_signal": calibration.signal,
                "state_calibration_source": calibration.source,
                "state_calibration_confidence": calibration.confidence,
                "state_calibration_run_count": calibration.matched_run_count,
                "state_calibration_session_count": calibration.matched_session_count,
                "state_calibration_outcome_score": calibration.average_run_outcome_score,
                "state_calibration_progress_signal": calibration.progress_signal,
                "state_calibration_strategy_signal": calibration.strategy_signal,
                "state_calibration_recovery_stability": calibration.recovery_stability,
                "state_calibration_overload_risk": calibration.overload_risk,
                "state_calibration_metacognitive_reliability": calibration.metacognitive_reliability,
                "state_calibration_current_evidence_signal": calibration.current_evidence_signal,
                "state_calibration_current_evidence_confidence": calibration.current_evidence_confidence,
                "state_calibration_current_evidence_rationale": calibration.current_evidence_rationale,
                "state_calibration_rationale": calibration.rationale,
                "state_calibration_applied": calibration.applied,
            },
        )
        services.within_session_adaptation_service.record_observation_event(
            student_id=student_id,
            event_payload=observation_audit_event.payload,
        )
        services.predictive_content_invalidator.invalidate_from_trigger_event(
            observation_audit_event
        )
        summary_events = (
            services.learning_run_summary_recorder.record_from_trigger_event(
                trigger_event=observation_audit_event
            )
        )
        services.learning_calibration_profile_recorder.record_from_summary_events(
            summary_events=summary_events
        )
        services.learning_progress_profile_recorder.record_from_summary_events(
            summary_events=summary_events
        )
        services.learning_strategy_profile_recorder.record_from_summary_events(
            summary_events=summary_events
        )
        services.learning_state_profile_recorder.record_from_summary_events(
            summary_events=summary_events
        )
        services.learning_trait_profile_recorder.record_from_observation_events(
            observation_events=[observation_audit_event]
        )
        services.ordinary_mastery_profile_recorder.record_from_observation_events(
            observation_events=[observation_audit_event]
        )
        return inferred_state

    @router.get(
        "/learners/{student_id}/state",
        response_model=InferredLearnerState,
        dependencies=context.deps("viewer"),
    )
    def get_inferred_learner_state(student_id: UUID) -> InferredLearnerState:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        observations = services.observation_store.list_recent(
            student_id=str(student_id)
        )
        if observations:
            inferred_state = services.state_inference_service.infer(
                student_id=student_id, observations=observations
            )
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

    @router.get(
        "/learners/{student_id}/summary",
        response_model=ProfileSummary,
        dependencies=context.deps("viewer"),
    )
    def get_profile_summary(student_id: UUID) -> ProfileSummary:
        summary = services.learner_summary_service.build_for_student(
            student_id=student_id
        )
        if summary is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return summary

    @router.get(
        "/learners/{student_id}/flow",
        response_model=LearnerFlowSummary,
        dependencies=context.deps("viewer"),
    )
    def get_learner_flow(student_id: UUID) -> LearnerFlowSummary:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.learner_flow_service.build_for_student(student_id=student_id)

    @router.get(
        "/learners/{student_id}/progression",
        response_model=LearnerCurriculumProgressionSummary,
        dependencies=context.deps("viewer"),
    )
    def get_learner_progression(
        student_id: UUID,
    ) -> LearnerCurriculumProgressionSummary:
        progression = services.learner_progression_service.build_for_student(
            student_id=student_id
        )
        if progression is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return progression

    @router.get(
        "/learners/{student_id}/workspace",
        response_model=LearnerWorkspace,
        dependencies=context.deps("viewer"),
    )
    def get_learner_workspace(student_id: UUID) -> LearnerWorkspace:
        workspace = services.learner_workspace_service.build_for_student(
            student_id=student_id
        )
        if workspace is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return workspace

    @router.get(
        "/learners/{student_id}/history/generations",
        response_model=LearnerGenerationHistoryPage,
        dependencies=context.deps("viewer"),
    )
    def list_generation_history(
        student_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> LearnerGenerationHistoryPage:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.learner_history_service.list_generation_history(
            student_id=student_id,
            limit=limit,
            offset=offset,
        )

    @router.get(
        "/learners/{student_id}/history/socratic-sessions",
        response_model=LearnerSocraticSessionHistoryPage,
        dependencies=context.deps("viewer"),
    )
    def list_socratic_session_history(
        student_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> LearnerSocraticSessionHistoryPage:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.learner_history_service.list_socratic_session_history(
            student_id=student_id,
            limit=limit,
            offset=offset,
        )

    @router.get(
        "/learners/{student_id}/history/remediation-sessions",
        response_model=LearnerRemediationSessionHistoryPage,
        dependencies=context.deps("viewer"),
    )
    def list_remediation_session_history(
        student_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> LearnerRemediationSessionHistoryPage:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.learner_history_service.list_remediation_session_history(
            student_id=student_id,
            limit=limit,
            offset=offset,
        )

    @router.get(
        "/learners/{student_id}/mastery-history",
        response_model=MasteryHistoryResponse,
        dependencies=context.deps("viewer"),
    )
    def get_mastery_history(student_id: UUID, days: int = 30) -> MasteryHistoryResponse:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.mastery_snapshot_service.get_learner_history(
            student_id=student_id,
            days=min(max(1, days), 365),
        )

    @router.get(
        "/learners/{student_id}/intervention-action",
        response_model=TeacherInterventionActionContract,
        dependencies=context.deps("viewer"),
    )
    def get_teacher_intervention_action(
        student_id: UUID,
    ) -> TeacherInterventionActionContract:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        return services.teacher_intervention_action_service.build_for_student(
            student_id=student_id
        )

    @router.post(
        "/learners/{student_id}/intervention-action",
        response_model=TeacherInterventionActionContract,
        dependencies=context.deps("editor"),
    )
    def record_teacher_intervention_action(
        student_id: UUID,
        decision: TeacherInterventionDecisionRequest,
        request: Request,
    ) -> TeacherInterventionActionContract:
        profile = services.profile_store.get(student_id)
        if profile is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner profile not found.",
                code="learner_profile_not_found",
            )
        try:
            return services.teacher_intervention_action_service.record_decision(
                student_id=student_id,
                decision=decision,
                identity=getattr(request.state, "auth_identity", None),
            )
        except TeacherInterventionActionUnavailableError as exc:
            raise api_error(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
                code="teacher_intervention_unavailable",
            ) from exc
        except TeacherInterventionOptionNotFoundError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                code="teacher_intervention_option_not_found",
            ) from exc
        except ValueError as exc:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                code="teacher_intervention_invalid_decision",
            ) from exc

    return router
