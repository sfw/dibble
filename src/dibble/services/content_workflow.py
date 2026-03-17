from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentWarmRequest,
    ContentWarmResult,
    GeneratedContent,
    GenerationRequest,
    PredictiveWarmProcessResult,
    RemedialTriggerRequest,
)
from dibble.models.profile import LearnerProfile
from dibble.models.remediation import (
    RemediationWorkflowAdvanceRequest,
    RemediationWorkflowAdvanceResponse,
    RemediationWorkflowSession,
    RemediationWorkflowStep,
)
from dibble.plugins.contracts import RouterPlugin
from dibble.services.content_warmer import ContentWarmer
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.generation_request_hydrator import hydrate_target_kc_hints
from dibble.services.generation_modes import build_generation_mode_plan
from dibble.services.learner_strategy_profiles import LearnerStrategySignalService
from dibble.services.misconception_profiles import LearningMisconceptionProfileRecorder
from dibble.services.observation_profile_update import ObservationProfileUpdater, RemediationProgressDecision
from dibble.services.predictive_content_warming import PredictiveContentWarmer
from dibble.services.predictive_warm_scheduler import PredictiveWarmScheduler
from dibble.services.progression_ownership import ProgressionOwnershipDecision, ProgressionOwnershipService
from dibble.services.protocols import AuditStore, KnowledgeComponentStore, ObservationStore, ProfileStore
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.remediation_workflows import (
    RemediationWorkflowCoordinator,
    RemediationWorkflowNotFoundError,
)
from dibble.services.within_session_adaptation import WithinSessionAdaptationService


class LearnerProfileNotFoundError(LookupError):
    def __init__(self, student_id: UUID) -> None:
        super().__init__(f"Learner profile not found for student_id {student_id}.")
        self.student_id = student_id


@dataclass(slots=True)
class ContentWorkflowService:
    profile_store: ProfileStore
    observation_store: ObservationStore
    knowledge_component_store: KnowledgeComponentStore
    router: RouterPlugin
    generation_engine: GenerationEngine
    content_warmer: ContentWarmer
    generation_mode_calibrator: GenerationModeCalibrator
    predictive_content_warmer: PredictiveContentWarmer
    predictive_warm_scheduler: PredictiveWarmScheduler
    remediation_planner: RemediationPlanner
    remediation_workflow_coordinator: RemediationWorkflowCoordinator
    strategy_signal_service: LearnerStrategySignalService
    misconception_profile_recorder: LearningMisconceptionProfileRecorder
    audit_store: AuditStore
    within_session_adaptation_service: WithinSessionAdaptationService
    observation_profile_updater: ObservationProfileUpdater | None = None
    progression_ownership_service: ProgressionOwnershipService | None = None

    def decide_route(self, request: GenerationRequest) -> AdaptiveRouteDecision:
        profile = self._load_profile(request.student_id)
        decision = self.router.route(profile, request)
        strategy = self.strategy_signal_service.strategy_for(student_id=request.student_id, request=request)
        self.audit_store.append(
            event_type="adaptive.decide",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "intervention_type": decision.intervention_type.value,
                "delivery_mode": decision.delivery_mode.value,
                "scaffolding_level": decision.scaffolding_level,
                "reason_count": len(decision.reasons),
                "calibration_signal": decision.calibration.signal if decision.calibration is not None else None,
                "calibration_source": decision.calibration.source if decision.calibration is not None else None,
                "calibration_confidence": decision.calibration.confidence if decision.calibration is not None else 0.0,
                "calibration_run_count": (
                    decision.calibration.matched_run_count if decision.calibration is not None else 0
                ),
                "calibration_outcome_score": (
                    decision.calibration.average_run_outcome_score if decision.calibration is not None else None
                ),
                "calibration_progress_signal": (
                    decision.calibration.progress_signal if decision.calibration is not None else None
                ),
                "calibration_progress_delta": (
                    decision.calibration.progress_delta if decision.calibration is not None else 0.0
                ),
                "strategy_signal": strategy.signal,
                "strategy_source": strategy.source,
                "strategy_support_bias": strategy.support_bias,
                "strategy_recovery_focus": strategy.recovery_focus,
            },
        )
        return decision

    def generate_content(self, request: GenerationRequest) -> GeneratedContent:
        profile = self._load_profile(request.student_id)
        progression_decision = self._progression_ownership_decision(request=request)
        resolved_request = progression_decision.request
        enriched_request = hydrate_target_kc_hints(
            request=resolved_request,
            knowledge_component_store=self.knowledge_component_store,
        )
        calibrated_request = self.generation_mode_calibrator.calibrate_request(request=enriched_request)
        response = self.generation_engine.generate(profile, calibrated_request)
        plan = build_generation_mode_plan(profile, calibrated_request, response.route)
        metadata = response.generation_metadata
        if metadata is None or response.generation_id is None:
            raise RuntimeError("Generated content metadata was not available.")

        generated_content = GeneratedContent(
            generation_id=response.generation_id,
            student_id=response.student_id,
            content_type=plan.content_type.value,
            request_context=plan.request_context,
            response=response,
            quality=metadata,
            created_at=response.generated_at,
        )
        self.audit_store.append(
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
                "moderation_status": metadata.moderation.status,
                "moderation_stage": metadata.moderation.stage,
                "moderation_categories": metadata.moderation.categories,
                "moderation_reasons": metadata.moderation.reasons,
                "moderation_matched_terms": metadata.moderation.matched_terms,
                "moderation_matches": [match.model_dump(mode="json") for match in metadata.moderation.matches],
                "moderation_severity": metadata.moderation.severity,
                "moderation_decision": metadata.moderation.decision,
                "moderation_blocked": metadata.moderation.blocked,
                "moderation_request_blocked": metadata.moderation.request_blocked,
                "moderation_response_rewritten": metadata.moderation.response_rewritten,
                "moderation_fallback_applied": metadata.moderation.fallback_applied,
                "moderation_fallback_kind": metadata.moderation.fallback_kind,
                "moderation_stream_action": metadata.moderation.stream_action,
                "moderation_provider_invoked": metadata.moderation.provider_invoked,
                "moderation_stream_buffered": metadata.moderation.stream_buffered,
                "moderation_original_block_count": metadata.moderation.original_block_count,
                "moderation_replacement_block_count": metadata.moderation.replacement_block_count,
                "moderation_audit_message": metadata.moderation.audit_message,
                "cache_hit": metadata.cache_hit,
                "quality_score": metadata.quality_score,
                "requested_target_kc_ids": progression_decision.requested_target_kc_ids,
                "applied_target_kc_ids": progression_decision.applied_target_kc_ids,
                "target_kc_ids": calibrated_request.target_kc_ids,
                "target_lo_ids": calibrated_request.target_lo_ids,
                "progression_action": progression_decision.action,
                "progression_source": progression_decision.source,
                "progression_bridge_kc_ids": progression_decision.bridge_kc_ids,
                "progression_deferred_target_kc_ids": progression_decision.deferred_target_kc_ids,
                "progression_rationale": progression_decision.rationale,
                "progression_evidence_observation_count": progression_decision.evidence_observation_count,
                "progression_evidence_assessment_count": progression_decision.evidence_assessment_count,
                "progression_evidence_confidence": progression_decision.evidence_confidence,
                "progression_average_observed_mastery": progression_decision.average_observed_mastery,
                "progression_average_assessment_mastery": progression_decision.average_assessment_mastery,
                "scaffolding_level": response.route.scaffolding_level,
                "mode_calibration_signal": (
                    calibrated_request.mode_calibration.signal if calibrated_request.mode_calibration is not None else None
                ),
                "mode_calibration_source": (
                    calibrated_request.mode_calibration.source if calibrated_request.mode_calibration is not None else None
                ),
                "mode_calibration_confidence": (
                    calibrated_request.mode_calibration.confidence
                    if calibrated_request.mode_calibration is not None
                    else 0.0
                ),
                "mode_calibration_run_count": (
                    calibrated_request.mode_calibration.matched_run_count
                    if calibrated_request.mode_calibration is not None
                    else 0
                ),
                "mode_support_bias": (
                    calibrated_request.mode_calibration.support_bias
                    if calibrated_request.mode_calibration is not None
                    else 0
                ),
                "mode_strategy_signal": (
                    calibrated_request.mode_calibration.strategy_signal
                    if calibrated_request.mode_calibration is not None
                    else None
                ),
                "mode_strategy_source": (
                    calibrated_request.mode_calibration.strategy_source
                    if calibrated_request.mode_calibration is not None
                    else None
                ),
                "mode_session_signal": (
                    calibrated_request.mode_calibration.session_signal
                    if calibrated_request.mode_calibration is not None
                    else None
                ),
                "mode_session_source": (
                    calibrated_request.mode_calibration.session_source
                    if calibrated_request.mode_calibration is not None
                    else None
                ),
                "mode_sequence_action": (
                    calibrated_request.mode_calibration.sequence_action
                    if calibrated_request.mode_calibration is not None
                    else None
                ),
                "mode_strategy_recovery_focus": (
                    calibrated_request.mode_calibration.strategy_recovery_focus
                    if calibrated_request.mode_calibration is not None
                    else None
                ),
                "mode_calibration_applied": bool(plan.request_context.get("mode_calibration_applied", False)),
                "route_calibration_signal": (
                    response.route.calibration.signal if response.route.calibration is not None else None
                ),
                "route_calibration_source": (
                    response.route.calibration.source if response.route.calibration is not None else None
                ),
                "route_calibration_confidence": (
                    response.route.calibration.confidence if response.route.calibration is not None else 0.0
                ),
                "route_calibration_progress_signal": (
                    response.route.calibration.progress_signal if response.route.calibration is not None else None
                ),
                "route_calibration_progress_delta": (
                    response.route.calibration.progress_delta if response.route.calibration is not None else 0.0
                ),
                "prompt_template_name": metadata.prompt_template_name,
                "prompt_template_version": metadata.prompt_template_version,
                "prompt_template_variant": metadata.prompt_template_variant,
            },
        )
        self._record_moderation_event(
            student_id=str(request.student_id),
            generation_id=generated_content.generation_id,
            learning_session_id=request.learning_session_id,
            moderation=metadata.moderation,
            delivery_mode=response.route.delivery_mode.value,
        )
        session_summary = self.within_session_adaptation_service.record_generation_step(
            request=calibrated_request,
            content_type=generated_content.content_type,
            generation_id=generated_content.generation_id,
        )
        self._apply_session_adaptation(
            generated_content=generated_content,
            session_summary=session_summary,
        )
        self._apply_progression_ownership(
            generated_content=generated_content,
            progression_decision=progression_decision,
        )
        predictive_plan = self.predictive_content_warmer.plan_follow_ups(generated_content)
        if predictive_plan.requests:
            enqueue_result = self.predictive_warm_scheduler.enqueue_plan(plan=predictive_plan)
            inline_process_result = self.predictive_warm_scheduler.process_inline(task_ids=enqueue_result.task_ids or [])
            self.audit_store.append(
                event_type="content.warm.predictive",
                status="success",
                student_id=str(request.student_id),
                payload={
                    "source_generation_id": generated_content.generation_id,
                    "learning_session_id": request.learning_session_id,
                    "target_kc_ids": request.target_kc_ids,
                    "target_lo_ids": request.target_lo_ids,
                    "predicted_request_count": len(predictive_plan.requests),
                    "predicted_content_types": predictive_plan.content_types,
                    "warm_reasons": predictive_plan.reasons,
                    "enqueued_tasks": enqueue_result.enqueued_count,
                    "duplicate_tasks": enqueue_result.duplicate_count,
                    "claimed_tasks": inline_process_result.claimed_tasks,
                    "supplemental_tasks": inline_process_result.supplemental_tasks,
                    "processed_tasks": inline_process_result.completed_tasks,
                    "failed_tasks": inline_process_result.failed_tasks,
                    "retried_tasks": inline_process_result.retried_tasks,
                    "requeued_tasks": inline_process_result.requeued_tasks,
                    "expired_tasks": inline_process_result.expired_tasks,
                    "deferred_tasks": inline_process_result.deferred_tasks,
                    "dropped_tasks": inline_process_result.dropped_tasks,
                    "pending_tasks": inline_process_result.pending_tasks,
                    "cache_hits": inline_process_result.cache_hits,
                    "cache_misses": inline_process_result.cache_misses,
                    "generation_ids": inline_process_result.generation_ids,
                },
            )
        return generated_content

    def _record_moderation_event(
        self,
        *,
        student_id: str,
        generation_id: str,
        learning_session_id: str | None,
        moderation,
        delivery_mode: str,
    ) -> None:
        if moderation.status != "flagged":
            return
        self.audit_store.append(
            event_type="content.moderation",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": generation_id,
                "learning_session_id": learning_session_id,
                "stage": moderation.stage,
                "severity": moderation.severity,
                "decision": moderation.decision,
                "blocked": moderation.blocked,
                "request_blocked": moderation.request_blocked,
                "response_rewritten": moderation.response_rewritten,
                "categories": moderation.categories,
                "matched_terms": moderation.matched_terms,
                "matches": [match.model_dump(mode="json") for match in moderation.matches],
                "fallback_applied": moderation.fallback_applied,
                "fallback_kind": moderation.fallback_kind,
                "stream_action": moderation.stream_action,
                "provider_invoked": moderation.provider_invoked,
                "stream_buffered": moderation.stream_buffered,
                "original_block_count": moderation.original_block_count,
                "replacement_block_count": moderation.replacement_block_count,
                "delivery_mode": delivery_mode,
                "stream_emitted": False,
                "audit_message": moderation.audit_message,
            },
        )

    def _apply_session_adaptation(
        self,
        *,
        generated_content: GeneratedContent,
        session_summary,
    ) -> None:
        if session_summary.signal == "insufficient":
            return
        request_context = generated_content.request_context
        request_context["session_adaptation"] = {
            "signal": session_summary.signal,
            "source": session_summary.source,
            "confidence": session_summary.confidence,
            "support_bias": session_summary.support_bias,
            "sequence_action": session_summary.sequence_action,
            "primary_kc_id": session_summary.primary_kc_id,
            "observation_count": session_summary.matched_observation_count,
            "assessment_count": session_summary.matched_assessment_count,
            "phase": session_summary.phase,
            "recovery_intent": session_summary.recovery_intent,
            "support_step_budget": session_summary.support_step_budget,
            "support_steps_remaining": session_summary.support_steps_remaining,
            "stuck_loop_risk": session_summary.stuck_loop_risk,
            "arc_action": session_summary.arc_action,
            "generated_step_count": session_summary.generated_step_count,
            "positive_streak": session_summary.positive_streak,
            "negative_streak": session_summary.negative_streak,
            "current_evidence_signal": session_summary.current_evidence_signal,
            "current_evidence_confidence": session_summary.current_evidence_confidence,
            "current_evidence_rationale": session_summary.current_evidence_rationale,
            "latest_prompt_style": session_summary.latest_assessment_prompt_style,
            "latest_next_action": session_summary.latest_assessment_next_action,
            "latest_evidence_strength": session_summary.latest_assessment_evidence_strength,
            "socratic_steering_action": session_summary.socratic_steering_action,
            "rationale": session_summary.rationale,
        }
        mode_calibration = request_context.get("mode_calibration")
        if isinstance(mode_calibration, dict):
            mode_calibration.update(
                {
                    "session_signal": session_summary.signal,
                    "session_source": session_summary.source,
                    "session_confidence": session_summary.confidence,
                    "session_support_bias": session_summary.support_bias,
                    "session_sequence_action": session_summary.sequence_action,
                    "session_primary_kc_id": session_summary.primary_kc_id,
                    "session_observation_count": session_summary.matched_observation_count,
                    "session_assessment_count": session_summary.matched_assessment_count,
                    "session_phase": session_summary.phase,
                    "session_recovery_intent": session_summary.recovery_intent,
                    "session_support_step_budget": session_summary.support_step_budget,
                    "session_support_steps_remaining": session_summary.support_steps_remaining,
                    "session_stuck_loop_risk": session_summary.stuck_loop_risk,
                    "session_arc_action": session_summary.arc_action,
                    "session_generated_step_count": session_summary.generated_step_count,
                    "session_positive_streak": session_summary.positive_streak,
                    "session_negative_streak": session_summary.negative_streak,
                    "current_evidence_signal": session_summary.current_evidence_signal,
                    "current_evidence_confidence": session_summary.current_evidence_confidence,
                    "current_evidence_rationale": session_summary.current_evidence_rationale,
                    "session_latest_prompt_style": session_summary.latest_assessment_prompt_style,
                    "session_latest_next_action": session_summary.latest_assessment_next_action,
                    "session_latest_evidence_strength": session_summary.latest_assessment_evidence_strength,
                    "socratic_steering_action": session_summary.socratic_steering_action,
                    "session_rationale": session_summary.rationale,
                    "sequence_source": session_summary.source
                    if session_summary.sequence_action != "monitor"
                    else mode_calibration.get("sequence_source", "insufficient"),
                }
            )

    def _apply_progression_ownership(
        self,
        *,
        generated_content: GeneratedContent,
        progression_decision: ProgressionOwnershipDecision,
    ) -> None:
        request_context = generated_content.request_context
        request_context["progression"] = {
            "action": progression_decision.action,
            "source": progression_decision.source,
            "requested_target_kc_ids": progression_decision.requested_target_kc_ids,
            "applied_target_kc_ids": progression_decision.applied_target_kc_ids,
            "deferred_target_kc_ids": progression_decision.deferred_target_kc_ids,
            "bridge_kc_ids": progression_decision.bridge_kc_ids,
            "rationale": progression_decision.rationale,
            "observation_count": progression_decision.evidence_observation_count,
            "assessment_count": progression_decision.evidence_assessment_count,
            "confidence": progression_decision.evidence_confidence,
            "average_observed_mastery": progression_decision.average_observed_mastery,
            "average_assessment_mastery": progression_decision.average_assessment_mastery,
        }

    def _progression_ownership_decision(self, *, request: GenerationRequest) -> ProgressionOwnershipDecision:
        if self.progression_ownership_service is None:
            return ProgressionOwnershipDecision(
                request=request,
                requested_target_kc_ids=list(request.target_kc_ids),
                applied_target_kc_ids=list(request.target_kc_ids),
            )
        return self.progression_ownership_service.resolve_request(
            student_id=request.student_id,
            request=request,
        )

    def warm_content(self, request: ContentWarmRequest) -> ContentWarmResult:
        warmed = self.content_warmer.warm(request.requests)
        self.audit_store.append(
            event_type="content.warm",
            status="success",
            payload={
                "total_requests": warmed.total_requests,
                "cache_hits": warmed.cache_hits,
                "cache_misses": warmed.cache_misses,
            },
        )
        return warmed

    def process_predictive_warm_queue(self, *, limit: int) -> PredictiveWarmProcessResult:
        result = self.predictive_warm_scheduler.process_pending(limit=limit)
        self.audit_store.append(
            event_type="content.warm.predictive.process",
            status="success",
            payload={
                "limit": limit,
                "attempted_tasks": result.attempted_tasks,
                "claimed_tasks": result.claimed_tasks,
                "supplemental_tasks": result.supplemental_tasks,
                "completed_tasks": result.completed_tasks,
                "failed_tasks": result.failed_tasks,
                "retried_tasks": result.retried_tasks,
                "requeued_tasks": result.requeued_tasks,
                "expired_tasks": result.expired_tasks,
                "deferred_tasks": result.deferred_tasks,
                "dropped_tasks": result.dropped_tasks,
                "skipped_tasks": result.skipped_tasks,
                "pending_tasks": result.pending_tasks,
                "cache_hits": result.cache_hits,
                "cache_misses": result.cache_misses,
                "generation_ids": result.generation_ids,
            },
        )
        return result

    def trigger_remedial_content(self, request: RemedialTriggerRequest) -> GeneratedContent:
        profile = self._load_profile(request.student_id)
        strategy_summary = self.strategy_signal_service.strategy_for(
            student_id=request.student_id,
            request=GenerationRequest(
                student_id=request.student_id,
                target_kc_ids=[request.target_kc_id],
                intent="remediation",
            ),
        )
        plan = self.remediation_planner.plan(
            profile,
            request.target_kc_id,
            misconception_description=request.misconception_description,
            curriculum_context=request.curriculum_context,
            strategy_summary=strategy_summary,
        )
        session = self.remediation_workflow_coordinator.start_session(
            student_id=request.student_id,
            target_kc_id=request.target_kc_id,
            misconception_description=request.misconception_description,
            curriculum_context=request.curriculum_context,
            plan=plan,
            strategy_summary=strategy_summary,
        )
        executed_step, updated_session, generated_content = self._execute_remediation_session_step(
            session_id=session.session_id,
            learner_prompt=request.learner_prompt,
            curriculum_context=[
                *[
                    signal.remediation_hint
                    for signal in plan.misconception_signals
                    if signal.remediation_hint is not None
                ],
                *request.curriculum_context,
            ],
        )
        enriched_content = self._enrich_remediation_content(
            generated_content=generated_content,
            session=updated_session,
            executed_step=executed_step,
            misconception_signals=[signal.model_dump(mode="json") for signal in plan.misconception_signals],
        )
        remediation_event = self.audit_store.append(
            event_type="remediation.trigger",
            status="success",
            student_id=str(request.student_id),
            payload={
                "remediation_session_id": updated_session.session_id,
                "target_kc_id": request.target_kc_id,
                "focus_kc_ids": plan.focus_kc_ids,
                "prerequisite_kc_ids": plan.prerequisite_kc_ids,
                "misconception_signal_count": len(plan.misconception_signals),
                "misconception_signals": [signal.model_dump(mode="json") for signal in plan.misconception_signals],
                "remediation_blueprint": plan.module_blueprint,
                "generation_id": enriched_content.generation_id,
                "rationale": plan.rationale,
                "executed_phase": executed_step.phase,
                "next_phase": self._next_remediation_phase(updated_session),
                "step_count": len(updated_session.steps),
                "strategy_signal": strategy_summary.signal,
                "strategy_support_bias": strategy_summary.support_bias,
                "strategy_recovery_focus": strategy_summary.recovery_focus,
                "sequence_action": plan.kc_sequence.action,
                "sequence_primary_kc_id": plan.kc_sequence.primary_kc_id,
                "sequence_ordered_kc_ids": plan.kc_sequence.ordered_kc_ids,
            },
        )
        self.misconception_profile_recorder.record_from_remediation_event(remediation_event=remediation_event)
        return enriched_content

    def get_remediation_session(self, session_id: str) -> RemediationWorkflowSession:
        session = self.remediation_workflow_coordinator.get(session_id)
        if session is None:
            raise RemediationWorkflowNotFoundError(session_id)
        return session

    def advance_remediation_session(
        self,
        *,
        session_id: str,
        request: RemediationWorkflowAdvanceRequest,
    ) -> RemediationWorkflowAdvanceResponse:
        session = self.get_remediation_session(session_id)
        progression_decision = self._remediation_progression_decision(session=session)
        if progression_decision.decision == "advance":
            executed_step, updated_session, generated_content = self._execute_remediation_session_step(
                session_id=session_id,
                learner_prompt=request.learner_prompt,
                curriculum_context=request.curriculum_context,
            )
        else:
            executed_step, updated_session, generated_content = self._execute_held_remediation_step(
                session=session,
                progression_decision=progression_decision,
                learner_prompt=request.learner_prompt,
                curriculum_context=request.curriculum_context,
            )
        enriched_content = self._enrich_remediation_content(
            generated_content=generated_content,
            session=updated_session,
            executed_step=executed_step,
        )
        self.audit_store.append(
            event_type="remediation.advance",
            status="success",
            student_id=str(session.student_id),
            payload={
                "remediation_session_id": updated_session.session_id,
                "target_kc_id": session.target_kc_id,
                "generation_id": enriched_content.generation_id,
                "executed_phase": executed_step.phase,
                "next_phase": self._next_remediation_phase(updated_session),
                "completed_step_count": len(updated_session.completed_generation_ids),
                "step_count": len(updated_session.steps),
                "progression_decision": updated_session.progression_decision,
                "progression_rationale": updated_session.progression_rationale,
                "progression_target_kc_ids": updated_session.progression_target_kc_ids,
            },
        )
        return RemediationWorkflowAdvanceResponse(
            session=updated_session,
            content=enriched_content,
            executed_phase=executed_step.phase,
        )

    def load_profile(self, student_id: UUID) -> LearnerProfile:
        return self._load_profile(student_id)

    def _load_profile(self, student_id: UUID) -> LearnerProfile:
        profile = self.profile_store.get(student_id)
        if profile is None:
            raise LearnerProfileNotFoundError(student_id)
        return profile

    def _execute_remediation_session_step(
        self,
        *,
        session_id: str,
        learner_prompt: str | None,
        curriculum_context: list[str],
    ) -> tuple[RemediationWorkflowStep, RemediationWorkflowSession, GeneratedContent]:
        _, current_step, generation_request = self.remediation_workflow_coordinator.generation_request_for_current_step(
            session_id=session_id,
            learner_prompt=learner_prompt,
            curriculum_context=curriculum_context,
        )
        generated_content = self.generate_content(generation_request)
        updated_session = self.remediation_workflow_coordinator.complete_current_step(
            session_id=session_id,
            generation_id=generated_content.generation_id,
        )
        return current_step, updated_session, generated_content

    def _execute_held_remediation_step(
        self,
        *,
        session: RemediationWorkflowSession,
        progression_decision: RemediationProgressDecision,
        learner_prompt: str | None,
        curriculum_context: list[str],
    ) -> tuple[RemediationWorkflowStep, RemediationWorkflowSession, GeneratedContent]:
        hold_step_index = progression_decision.hold_step_index
        if hold_step_index is None:
            raise RuntimeError("Remediation hold decision did not include a step index.")
        _, hold_step, generation_request = self.remediation_workflow_coordinator.generation_request_for_step(
            session_id=session.session_id,
            step_index=hold_step_index,
            learner_prompt=learner_prompt,
            curriculum_context=[
                *(curriculum_context or []),
                f"Progression decision: {progression_decision.decision}.",
                progression_decision.rationale or "Hold on the current repair target before advancing.",
            ],
        )
        generated_content = self.generate_content(generation_request)
        updated_session = self.remediation_workflow_coordinator.update_progression_decision(
            session_id=session.session_id,
            decision=progression_decision.decision,
            rationale=progression_decision.rationale,
            target_kc_ids=progression_decision.target_kc_ids or [],
        )
        return hold_step, updated_session, generated_content

    def _remediation_progression_decision(self, *, session: RemediationWorkflowSession) -> RemediationProgressDecision:
        if self.observation_profile_updater is None:
            return RemediationProgressDecision()
        observations = self.observation_store.list_recent(student_id=str(session.student_id))
        return self.observation_profile_updater.evaluate_remediation_progress(
            session=session,
            observations=observations,
        )

    def _enrich_remediation_content(
        self,
        *,
        generated_content: GeneratedContent,
        session: RemediationWorkflowSession,
        executed_step: RemediationWorkflowStep,
        misconception_signals: list[dict[str, object]] | None = None,
    ) -> GeneratedContent:
        next_step = self._current_remediation_step(session)
        enriched_request_context = {
            **generated_content.request_context,
            "target_kc_id": session.target_kc_id,
            "target_kc_ids": session.focus_kc_ids,
            "focus_kc_ids": session.focus_kc_ids,
            "prerequisite_kc_ids": session.prerequisite_kc_ids,
            "misconception_description": session.misconception_description,
            "remediation_rationale": session.rationale,
            "remediation_blueprint": session.blueprint,
            "remediation_session_id": session.session_id,
            "learner_strategy": session.strategy_summary.model_dump(mode="json"),
            "sequencing": session.kc_sequence.model_dump(mode="json"),
            "remediation_workflow": {
                "status": "complete" if session.current_step_index is None else "in_progress",
                "executed_phase": executed_step.phase,
                "executed_step_target_kc_ids": executed_step.target_kc_ids,
                "next_phase": next_step.phase if next_step is not None else None,
                "next_step_target_kc_ids": next_step.target_kc_ids if next_step is not None else [],
                "completed_step_count": len(session.completed_generation_ids),
                "step_count": len(session.steps),
                "progression_decision": session.progression_decision,
                "progression_rationale": session.progression_rationale,
                "progression_target_kc_ids": session.progression_target_kc_ids,
            },
        }
        if misconception_signals is not None:
            enriched_request_context["misconception_signals"] = misconception_signals
        return generated_content.model_copy(update={"request_context": enriched_request_context})

    def _current_remediation_step(self, session: RemediationWorkflowSession) -> RemediationWorkflowStep | None:
        current_index = session.current_step_index
        if current_index is None or current_index >= len(session.steps):
            return None
        return session.steps[current_index]

    def _next_remediation_phase(self, session: RemediationWorkflowSession) -> str | None:
        next_step = self._current_remediation_step(session)
        if next_step is None:
            return None
        return next_step.phase
