from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentWarmRequest,
    ContentWarmResult,
    GeneratedContent,
    GenerationResponse,
    GenerationWorkflowSummary,
    GenerationRequest,
    PredictiveWarmProcessResult,
    RemedialTriggerRequest,
    RequestedContentType,
)
from dibble.models.profile import (
    LearnerContinueAction,
    LearnerFlowNextStep,
    LearnerProfile,
)
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
from dibble.services.learner_strategy_signal import LearnerStrategySignalService
from dibble.services.misconception_profiles import LearningMisconceptionProfileRecorder
from dibble.services.observation_profile_update import (
    ObservationProfileUpdater,
    RemediationProgressDecision,
)
from dibble.services.predictive_content_warming import (
    PredictiveContentWarmer,
    PredictiveWarmPlan,
)
from dibble.services.predictive_warm_scheduler import PredictiveWarmScheduler
from dibble.services.progression_ownership import (
    ProgressionOwnershipDecision,
    ProgressionOwnershipService,
)
from dibble.services.protocols import (
    AuditStore,
    GeneratedContentStore,
    KnowledgeComponentStore,
    ObservationStore,
    ProfileStore,
)
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.remediation_workflows import (
    RemediationWorkflowCoordinator,
    RemediationWorkflowNotFoundError,
)
from dibble.services.within_session_adaptation import WithinSessionAdaptationService
from dibble.services.workflow_rationale import decision_grade_rationale


class LearnerProfileNotFoundError(LookupError):
    def __init__(self, student_id: UUID) -> None:
        super().__init__(f"Learner profile not found for student_id {student_id}.")
        self.student_id = student_id


@dataclass(frozen=True, slots=True)
class PreparedGenerationRequest:
    profile: LearnerProfile
    request: GenerationRequest
    progression_decision: ProgressionOwnershipDecision


@dataclass(slots=True)
class ContentWorkflowService:
    profile_store: ProfileStore
    observation_store: ObservationStore
    knowledge_component_store: KnowledgeComponentStore
    generated_content_store: GeneratedContentStore
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
        strategy = self.strategy_signal_service.strategy_for(
            student_id=request.student_id, request=request
        )
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
                "calibration_signal": decision.calibration.signal
                if decision.calibration is not None
                else None,
                "calibration_source": decision.calibration.source
                if decision.calibration is not None
                else None,
                "calibration_confidence": decision.calibration.confidence
                if decision.calibration is not None
                else 0.0,
                "calibration_run_count": (
                    decision.calibration.matched_run_count
                    if decision.calibration is not None
                    else 0
                ),
                "calibration_outcome_score": (
                    decision.calibration.average_run_outcome_score
                    if decision.calibration is not None
                    else None
                ),
                "calibration_progress_signal": (
                    decision.calibration.progress_signal
                    if decision.calibration is not None
                    else None
                ),
                "calibration_progress_delta": (
                    decision.calibration.progress_delta
                    if decision.calibration is not None
                    else 0.0
                ),
                "strategy_signal": strategy.signal,
                "strategy_source": strategy.source,
                "strategy_support_bias": strategy.support_bias,
                "strategy_recovery_focus": strategy.recovery_focus,
            },
        )
        return decision

    def generate_content(self, request: GenerationRequest) -> GeneratedContent:
        prepared = self.prepare_generation_request(request)
        response = self.generation_engine.generate(prepared.profile, prepared.request)
        plan = build_generation_mode_plan(
            prepared.profile, prepared.request, response.route
        )
        metadata = response.generation_metadata
        if metadata is None or response.generation_id is None:
            raise RuntimeError("Generated content metadata was not available.")
        self.audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=str(request.student_id),
            payload={
                "intent": request.intent.value,
                "learning_session_id": request.learning_session_id,
                "content_type": plan.content_type.value,
                "generation_id": response.generation_id,
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
                "moderation_matches": [
                    match.model_dump(mode="json")
                    for match in metadata.moderation.matches
                ],
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
                "requested_target_kc_ids": prepared.progression_decision.requested_target_kc_ids,
                "applied_target_kc_ids": prepared.progression_decision.applied_target_kc_ids,
                "target_kc_ids": prepared.request.target_kc_ids,
                "target_lo_ids": prepared.request.target_lo_ids,
                "progression_action": prepared.progression_decision.action,
                "progression_source": prepared.progression_decision.source,
                "progression_target_stage": prepared.progression_decision.target_stage,
                "progression_target_redirect_applied": prepared.progression_decision.target_redirect_applied,
                "progression_bridge_kc_ids": prepared.progression_decision.bridge_kc_ids,
                "progression_transfer_target_kc_ids": prepared.progression_decision.transfer_target_kc_ids,
                "progression_deferred_target_kc_ids": prepared.progression_decision.deferred_target_kc_ids,
                "progression_rationale": prepared.progression_decision.rationale,
                "progression_requested_content_type": prepared.progression_decision.requested_content_type,
                "progression_applied_content_type": prepared.progression_decision.applied_content_type,
                "progression_mastery_gate_applied": prepared.progression_decision.mastery_gate_applied,
                "progression_mastery_gate_reason": prepared.progression_decision.mastery_gate_reason,
                "progression_evidence_observation_count": prepared.progression_decision.evidence_observation_count,
                "progression_evidence_assessment_count": prepared.progression_decision.evidence_assessment_count,
                "progression_evidence_confidence": prepared.progression_decision.evidence_confidence,
                "progression_average_observed_mastery": prepared.progression_decision.average_observed_mastery,
                "progression_average_assessment_mastery": prepared.progression_decision.average_assessment_mastery,
                "progression_ordinary_mastery_signal": prepared.progression_decision.ordinary_mastery_signal,
                "progression_ordinary_mastery_source": prepared.progression_decision.ordinary_mastery_source,
                "progression_ordinary_mastery_confidence": prepared.progression_decision.ordinary_mastery_confidence,
                "progression_ordinary_mastery_average_observed_mastery": (
                    prepared.progression_decision.ordinary_mastery_average_observed_mastery
                ),
                "progression_ordinary_mastery_rationale": prepared.progression_decision.ordinary_mastery_rationale,
                "scaffolding_level": response.route.scaffolding_level,
                "mode_calibration_signal": (
                    prepared.request.mode_calibration.signal
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_calibration_source": (
                    prepared.request.mode_calibration.source
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_calibration_confidence": (
                    prepared.request.mode_calibration.confidence
                    if prepared.request.mode_calibration is not None
                    else 0.0
                ),
                "mode_calibration_run_count": (
                    prepared.request.mode_calibration.matched_run_count
                    if prepared.request.mode_calibration is not None
                    else 0
                ),
                "mode_support_bias": (
                    prepared.request.mode_calibration.support_bias
                    if prepared.request.mode_calibration is not None
                    else 0
                ),
                "mode_strategy_signal": (
                    prepared.request.mode_calibration.strategy_signal
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_strategy_source": (
                    prepared.request.mode_calibration.strategy_source
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_session_signal": (
                    prepared.request.mode_calibration.session_signal
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_session_source": (
                    prepared.request.mode_calibration.session_source
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_sequence_action": (
                    prepared.request.mode_calibration.sequence_action
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_strategy_recovery_focus": (
                    prepared.request.mode_calibration.strategy_recovery_focus
                    if prepared.request.mode_calibration is not None
                    else None
                ),
                "mode_calibration_applied": bool(
                    plan.request_context.get("mode_calibration_applied", False)
                ),
                "route_calibration_signal": (
                    response.route.calibration.signal
                    if response.route.calibration is not None
                    else None
                ),
                "route_calibration_source": (
                    response.route.calibration.source
                    if response.route.calibration is not None
                    else None
                ),
                "route_calibration_confidence": (
                    response.route.calibration.confidence
                    if response.route.calibration is not None
                    else 0.0
                ),
                "route_calibration_progress_signal": (
                    response.route.calibration.progress_signal
                    if response.route.calibration is not None
                    else None
                ),
                "route_calibration_progress_delta": (
                    response.route.calibration.progress_delta
                    if response.route.calibration is not None
                    else 0.0
                ),
                "prompt_template_name": metadata.prompt_template_name,
                "prompt_template_version": metadata.prompt_template_version,
                "prompt_template_variant": metadata.prompt_template_variant,
            },
        )
        return self.finalize_generated_content(
            profile=prepared.profile,
            request=prepared.request,
            response=response,
            progression_decision=prepared.progression_decision,
        )

    def prepare_generation_request(
        self, request: GenerationRequest
    ) -> PreparedGenerationRequest:
        profile = self._load_profile(request.student_id)
        progression_decision = self._progression_ownership_decision(request=request)
        enriched_request = hydrate_target_kc_hints(
            request=progression_decision.request,
            knowledge_component_store=self.knowledge_component_store,
        )
        calibrated_request = self.generation_mode_calibrator.calibrate_request(
            request=enriched_request
        )
        return PreparedGenerationRequest(
            profile=profile,
            request=calibrated_request,
            progression_decision=progression_decision,
        )

    def finalize_generated_content(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        response: GenerationResponse,
        progression_decision: ProgressionOwnershipDecision,
        record_moderation_event: bool = True,
    ) -> GeneratedContent:
        plan = build_generation_mode_plan(profile, request, response.route)
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
        if record_moderation_event:
            self._record_moderation_event(
                student_id=str(request.student_id),
                generation_id=generated_content.generation_id,
                learning_session_id=request.learning_session_id,
                moderation=metadata.moderation,
                delivery_mode=response.route.delivery_mode.value,
            )
        session_summary = self.within_session_adaptation_service.record_generation_step(
            request=request,
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
        predictive_plan = self.predictive_content_warmer.plan_follow_ups(
            generated_content
        )
        if predictive_plan.requests:
            enqueue_result = self.predictive_warm_scheduler.enqueue_plan(
                plan=predictive_plan
            )
            inline_process_result = self.predictive_warm_scheduler.process_inline(
                task_ids=enqueue_result.task_ids or []
            )
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
                    "worker_id": inline_process_result.worker_id,
                    "execution_mode": inline_process_result.execution_mode,
                    "claimed_tasks": inline_process_result.claimed_tasks,
                    "targeted_tasks": inline_process_result.targeted_tasks,
                    "autonomous_tasks": inline_process_result.autonomous_tasks,
                    "supplemental_tasks": inline_process_result.supplemental_tasks,
                    "stale_recovered_tasks": inline_process_result.stale_recovered_tasks,
                    "processed_tasks": inline_process_result.completed_tasks,
                    "failed_tasks": inline_process_result.failed_tasks,
                    "retried_tasks": inline_process_result.retried_tasks,
                    "requeued_tasks": inline_process_result.requeued_tasks,
                    "expired_tasks": inline_process_result.expired_tasks,
                    "deferred_tasks": inline_process_result.deferred_tasks,
                    "dropped_tasks": inline_process_result.dropped_tasks,
                    "pending_tasks": inline_process_result.pending_tasks,
                    "eligible_tasks": inline_process_result.eligible_tasks,
                    "blocked_tasks": inline_process_result.blocked_tasks,
                    "cache_hits": inline_process_result.cache_hits,
                    "cache_misses": inline_process_result.cache_misses,
                    "generation_ids": inline_process_result.generation_ids,
                    "claim_details": [
                        detail.model_dump(mode="json")
                        for detail in inline_process_result.claim_details
                    ],
                },
            )
        finalized_content = self._apply_generation_workflow_summary(
            generated_content=generated_content,
            predictive_plan=predictive_plan,
        )
        self._refresh_generated_content(finalized_content)
        return finalized_content

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
                "matches": [
                    match.model_dump(mode="json") for match in moderation.matches
                ],
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
            "target_stage": progression_decision.target_stage,
            "target_redirect_applied": progression_decision.target_redirect_applied,
            "requested_target_kc_ids": progression_decision.requested_target_kc_ids,
            "applied_target_kc_ids": progression_decision.applied_target_kc_ids,
            "transfer_target_kc_ids": progression_decision.transfer_target_kc_ids,
            "deferred_target_kc_ids": progression_decision.deferred_target_kc_ids,
            "bridge_kc_ids": progression_decision.bridge_kc_ids,
            "rationale": progression_decision.rationale,
            "requested_content_type": progression_decision.requested_content_type,
            "applied_content_type": progression_decision.applied_content_type,
            "mastery_gate_applied": progression_decision.mastery_gate_applied,
            "mastery_gate_reason": progression_decision.mastery_gate_reason,
            "observation_count": progression_decision.evidence_observation_count,
            "assessment_count": progression_decision.evidence_assessment_count,
            "confidence": progression_decision.evidence_confidence,
            "average_observed_mastery": progression_decision.average_observed_mastery,
            "average_assessment_mastery": progression_decision.average_assessment_mastery,
            "ordinary_mastery_signal": progression_decision.ordinary_mastery_signal,
            "ordinary_mastery_source": progression_decision.ordinary_mastery_source,
            "ordinary_mastery_confidence": progression_decision.ordinary_mastery_confidence,
            "ordinary_mastery_average_observed_mastery": progression_decision.ordinary_mastery_average_observed_mastery,
            "ordinary_mastery_rationale": progression_decision.ordinary_mastery_rationale,
        }

    def _apply_generation_workflow_summary(
        self,
        *,
        generated_content: GeneratedContent,
        predictive_plan: PredictiveWarmPlan | None = None,
    ) -> GeneratedContent:
        request_context = generated_content.request_context
        progression = request_context.get("progression")
        progression_data = progression if isinstance(progression, dict) else {}
        remediation_workflow = request_context.get("remediation_workflow")
        remediation_data = (
            remediation_workflow if isinstance(remediation_workflow, dict) else {}
        )

        if remediation_data:
            executed_phase = str(remediation_data.get("executed_phase", "repair"))
            next_phase = remediation_data.get("next_phase")
            progression_decision = str(
                remediation_data.get("progression_decision", "advance")
            )
            next_target_kc_ids = self._remediation_next_step_target_kc_ids(
                remediation_data=remediation_data
            )
            explicit_next_step_rationale = self._maybe_str(
                remediation_data.get("next_step_rationale")
            )
            next_step = LearnerFlowNextStep(
                action=(
                    str(remediation_data.get("progression_decision"))
                    if progression_decision.startswith("hold_")
                    else str(next_phase or "complete")
                ),
                content_type=self._content_type_for_remediation_phase(
                    phase=next_phase,
                    progression_decision=progression_decision,
                ),
                target_stage=self._target_stage_for_remediation_next_step(
                    phase=next_phase or executed_phase,
                    progression_decision=progression_decision,
                ),
                target_kc_ids=next_target_kc_ids,
                rationale=self._workflow_step_rationale(
                    primary=explicit_next_step_rationale
                    or self._maybe_str(remediation_data.get("progression_rationale")),
                    action=(
                        progression_decision
                        if progression_decision.startswith("hold_")
                        else str(next_phase or "complete")
                    ),
                    target_stage=self._target_stage_for_remediation_next_step(
                        phase=next_phase or executed_phase,
                        progression_decision=progression_decision,
                    ),
                    fallback=(
                        None
                        if explicit_next_step_rationale is not None
                        else self._first_text(
                            progression_data.get("mastery_gate_reason"),
                            progression_data.get("rationale"),
                            request_context.get("remediation_rationale"),
                        )
                    ),
                ),
            )
            return generated_content.model_copy(
                update={
                    "workflow_summary": GenerationWorkflowSummary(
                        status="delivered",
                        flow_type="remediation",
                        learning_session_id=self._maybe_str(
                            request_context.get("learning_session_id")
                        ),
                        delivered_phase=executed_phase,
                        delivered_content_type=generated_content.content_type,
                        progression_action=progression_decision,
                        target_stage=self._target_stage_for_phase(executed_phase),
                        active_target_kc_ids=self._string_list(
                            progression_data.get("applied_target_kc_ids")
                            or request_context.get("target_kc_ids")
                        ),
                        rationale=next_step.rationale,
                        next_step=next_step,
                        continue_action=self._continue_action_for_remediation_content(
                            generated_content=generated_content,
                            request_context=request_context,
                            remediation_data=remediation_data,
                            next_step=next_step,
                        ),
                    )
                }
            )

        next_step = self._predictive_next_step(
            generated_content=generated_content,
            predictive_plan=predictive_plan,
        )
        return generated_content.model_copy(
            update={
                "workflow_summary": GenerationWorkflowSummary(
                    status="delivered",
                    flow_type="lesson",
                    learning_session_id=self._maybe_str(
                        request_context.get("learning_session_id")
                    ),
                    delivered_phase=str(
                        progression_data.get("target_stage")
                        or self._dict_value(
                            request_context.get("session_adaptation")
                        ).get("phase")
                        or "target"
                    ),
                    delivered_content_type=generated_content.content_type,
                    progression_action=str(
                        progression_data.get("action", "stay_on_requested_target")
                    ),
                    target_stage=str(progression_data.get("target_stage", "target")),
                    active_target_kc_ids=self._string_list(
                        progression_data.get("applied_target_kc_ids")
                        or request_context.get("target_kc_ids")
                    ),
                    rationale=next_step.rationale,
                    next_step=next_step,
                    continue_action=self._continue_action_for_lesson_content(
                        generated_content=generated_content,
                        next_step=next_step,
                    ),
                )
            }
        )

    def _predictive_next_step(
        self,
        *,
        generated_content: GeneratedContent,
        predictive_plan: PredictiveWarmPlan | None,
    ) -> LearnerFlowNextStep:
        request_context = generated_content.request_context
        progression = self._dict_value(request_context.get("progression"))
        forced_content_type = self._forced_next_step_content_type(progression)
        if forced_content_type is not None:
            return LearnerFlowNextStep(
                action=str(progression.get("action", "stay_on_requested_target")),
                content_type=forced_content_type,
                target_stage=str(progression.get("target_stage", "target")),
                target_kc_ids=self._string_list(
                    progression.get("applied_target_kc_ids")
                    or request_context.get("target_kc_ids")
                ),
                rationale=self._workflow_step_rationale(
                    primary=self._maybe_str(progression.get("mastery_gate_reason")),
                    action=str(progression.get("action", "stay_on_requested_target")),
                    target_stage=str(progression.get("target_stage", "target")),
                    fallback=self._maybe_str(progression.get("rationale")),
                ),
            )
        if predictive_plan is None or not predictive_plan.content_types:
            return LearnerFlowNextStep(
                action=str(progression.get("action", "stay_on_requested_target")),
                content_type=None,
                target_stage=str(progression.get("target_stage", "target")),
                target_kc_ids=self._string_list(
                    progression.get("applied_target_kc_ids")
                    or request_context.get("target_kc_ids")
                ),
                rationale=self._workflow_step_rationale(
                    primary=self._maybe_str(progression.get("mastery_gate_reason")),
                    action=str(progression.get("action", "stay_on_requested_target")),
                    target_stage=str(progression.get("target_stage", "target")),
                    fallback=self._maybe_str(progression.get("rationale")),
                ),
            )
        next_content_type = predictive_plan.content_types[0]
        next_reason = predictive_plan.reasons[0] if predictive_plan.reasons else None
        target_kc_ids = self._string_list(progression.get("applied_target_kc_ids"))
        if next_content_type == RequestedContentType.assessment_probe.value:
            target_kc_ids = (
                self._string_list(progression.get("transfer_target_kc_ids"))
                or target_kc_ids
            )
        return LearnerFlowNextStep(
            action=str(progression.get("action", "stay_on_requested_target")),
            content_type=next_content_type,
            target_stage=str(progression.get("target_stage", "target")),
            target_kc_ids=target_kc_ids
            or self._string_list(request_context.get("target_kc_ids")),
            rationale=self._workflow_step_rationale(
                primary=self._maybe_str(progression.get("mastery_gate_reason")),
                action=str(progression.get("action", "stay_on_requested_target")),
                target_stage=str(progression.get("target_stage", "target")),
                fallback=self._first_text(
                    progression.get("rationale"),
                    next_reason,
                ),
            ),
        )

    def _content_type_for_remediation_phase(
        self,
        *,
        phase: object,
        progression_decision: str,
    ) -> str | None:
        if progression_decision == "hold_bridge_target":
            return RequestedContentType.practice_problem.value
        if progression_decision.startswith("hold_"):
            return RequestedContentType.remedial_micro_module.value
        if phase is None:
            return None
        if str(phase) == "return":
            return RequestedContentType.practice_problem.value
        return RequestedContentType.remedial_micro_module.value

    def _remediation_next_step_target_kc_ids(
        self,
        *,
        remediation_data: dict[str, object],
    ) -> list[str]:
        progression_decision = str(
            remediation_data.get("progression_decision", "advance")
        )
        if progression_decision.startswith("hold_"):
            return self._string_list(remediation_data.get("progression_target_kc_ids"))
        return self._string_list(remediation_data.get("next_step_target_kc_ids"))

    def _target_stage_for_remediation_next_step(
        self,
        *,
        phase: str,
        progression_decision: str,
    ) -> str:
        if progression_decision == "hold_bridge_target":
            return "bridge"
        if progression_decision.startswith("hold_"):
            return "repair"
        return self._target_stage_for_phase(phase)

    def _forced_next_step_content_type(
        self, progression: dict[str, object]
    ) -> str | None:
        action = str(progression.get("action", ""))
        if action in {"hold_target", "hold_target_before_assessment"}:
            return RequestedContentType.practice_problem.value
        if action == "hold_bridge_target":
            return RequestedContentType.practice_problem.value
        if action in {
            "rebuild_prerequisite_first",
            "rebuild_prerequisite_before_assessment",
            "hold_repair_target",
            "hold_repair_target_before_assessment",
        }:
            return RequestedContentType.remedial_micro_module.value
        if action == "bridge_before_assessment":
            return RequestedContentType.practice_problem.value
        return None

    def _workflow_step_rationale(
        self,
        *,
        primary: str | None,
        action: str | None = None,
        target_stage: str | None = None,
        fallback: str | None,
    ) -> str | None:
        return decision_grade_rationale(
            primary,
            action=action,
            target_stage=target_stage,
            fallback=fallback,
        )

    def _continue_action_for_lesson_content(
        self,
        *,
        generated_content: GeneratedContent,
        next_step: LearnerFlowNextStep,
    ) -> LearnerContinueAction:
        if next_step.content_type is None:
            return LearnerContinueAction.idle(rationale=next_step.rationale)
        request_context = generated_content.request_context
        return LearnerContinueAction.generate_follow_up(
            resource_id=generated_content.generation_id,
            generation_id=generated_content.generation_id,
            learning_session_id=self._maybe_str(
                request_context.get("learning_session_id")
            ),
            content_type=next_step.content_type,
            target_stage=next_step.target_stage,
            target_kc_ids=list(next_step.target_kc_ids),
            request_payload=self._generation_request_payload(
                generated_content=generated_content,
                next_step=next_step,
            ),
            rationale=next_step.rationale,
        )

    def _continue_action_for_remediation_content(
        self,
        *,
        generated_content: GeneratedContent,
        request_context: dict[str, object],
        remediation_data: dict[str, object],
        next_step: LearnerFlowNextStep,
    ) -> LearnerContinueAction:
        session_id = self._maybe_str(request_context.get("remediation_session_id"))
        if session_id is None:
            return LearnerContinueAction.idle(rationale=next_step.rationale)
        if str(remediation_data.get("status", "in_progress")) == "complete":
            summary_continue_action = self._dict_value(
                remediation_data.get("summary_continue_action")
            )
            if summary_continue_action:
                return LearnerContinueAction.model_validate(summary_continue_action)

            target_kc_ids = list(next_step.target_kc_ids) or self._string_list(
                request_context.get("focus_kc_ids")
                or request_context.get("target_kc_ids")
            )
            follow_up_step = next_step.model_copy(
                update={
                    "content_type": RequestedContentType.practice_problem.value,
                    "target_stage": "transfer",
                    "target_kc_ids": target_kc_ids,
                    "rationale": decision_grade_rationale(
                        next_step.rationale,
                        action="attempt_transfer",
                        target_stage="transfer",
                        fallback="Return to the target skill after remediation.",
                    ),
                }
            )
            return LearnerContinueAction.generate_follow_up(
                resource_id=session_id,
                generation_id=generated_content.generation_id,
                learning_session_id=self._maybe_str(
                    request_context.get("learning_session_id")
                ),
                content_type=follow_up_step.content_type,
                target_stage=follow_up_step.target_stage,
                target_kc_ids=list(follow_up_step.target_kc_ids),
                request_payload=self._generation_request_payload(
                    generated_content=generated_content,
                    next_step=follow_up_step,
                ),
                rationale=follow_up_step.rationale,
            )
        return LearnerContinueAction.advance_remediation(
            endpoint=f"/api/remedial/sessions/{session_id}/advance",
            resource_id=session_id,
            generation_id=generated_content.generation_id,
            learning_session_id=self._maybe_str(
                request_context.get("learning_session_id")
            ),
            content_type=next_step.content_type,
            target_stage=next_step.target_stage,
            target_kc_ids=list(next_step.target_kc_ids),
            request_payload={
                "curriculum_context": list(
                    generated_content.response.curriculum_context
                ),
            },
            rationale=next_step.rationale,
        )

    def _generation_request_payload(
        self,
        *,
        generated_content: GeneratedContent,
        next_step: LearnerFlowNextStep,
    ) -> dict[str, object]:
        request_context = generated_content.request_context
        return {
            "student_id": str(generated_content.student_id),
            "learning_session_id": self._maybe_str(
                request_context.get("learning_session_id")
            ),
            "target_kc_ids": list(next_step.target_kc_ids),
            "target_lo_ids": self._string_list(request_context.get("target_lo_ids")),
            "requested_content_type": next_step.content_type,
            "curriculum_context": list(generated_content.response.curriculum_context),
            "source_generation_id": generated_content.generation_id,
        }

    def _target_stage_for_phase(self, phase: str) -> str:
        if phase == "bridge":
            return "bridge"
        if phase == "return":
            return "transfer"
        return "repair"

    def _dict_value(self, value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None]

    def _maybe_str(self, value: object) -> str | None:
        return str(value) if value is not None else None

    def _first_text(self, *values: object) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _progression_ownership_decision(
        self, *, request: GenerationRequest
    ) -> ProgressionOwnershipDecision:
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

    def process_predictive_warm_queue(
        self, *, limit: int
    ) -> PredictiveWarmProcessResult:
        result = self.predictive_warm_scheduler.process_pending(limit=limit)
        self.audit_store.append(
            event_type="content.warm.predictive.process",
            status="success",
            payload={
                "limit": limit,
                "attempted_tasks": result.attempted_tasks,
                "worker_id": result.worker_id,
                "execution_mode": result.execution_mode,
                "claimed_tasks": result.claimed_tasks,
                "targeted_tasks": result.targeted_tasks,
                "autonomous_tasks": result.autonomous_tasks,
                "supplemental_tasks": result.supplemental_tasks,
                "stale_recovered_tasks": result.stale_recovered_tasks,
                "completed_tasks": result.completed_tasks,
                "failed_tasks": result.failed_tasks,
                "retried_tasks": result.retried_tasks,
                "requeued_tasks": result.requeued_tasks,
                "expired_tasks": result.expired_tasks,
                "deferred_tasks": result.deferred_tasks,
                "dropped_tasks": result.dropped_tasks,
                "skipped_tasks": result.skipped_tasks,
                "pending_tasks": result.pending_tasks,
                "eligible_tasks": result.eligible_tasks,
                "blocked_tasks": result.blocked_tasks,
                "cache_hits": result.cache_hits,
                "cache_misses": result.cache_misses,
                "generation_ids": result.generation_ids,
                "claim_details": [
                    detail.model_dump(mode="json") for detail in result.claim_details
                ],
            },
        )
        return result

    def trigger_remedial_content(
        self, request: RemedialTriggerRequest
    ) -> GeneratedContent:
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
        executed_step, updated_session, generated_content = (
            self._execute_remediation_session_step(
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
        )
        enriched_content = self._enrich_remediation_content(
            generated_content=generated_content,
            session=updated_session,
            executed_step=executed_step,
            misconception_signals=[
                signal.model_dump(mode="json") for signal in plan.misconception_signals
            ],
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
                "misconception_signals": [
                    signal.model_dump(mode="json")
                    for signal in plan.misconception_signals
                ],
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
        self.misconception_profile_recorder.record_from_remediation_event(
            remediation_event=remediation_event
        )
        return enriched_content

    def get_remediation_session(self, session_id: str) -> RemediationWorkflowSession:
        session = self.remediation_workflow_coordinator.get(session_id)
        if session is None:
            raise RemediationWorkflowNotFoundError(session_id)
        return session

    def get_generated_content(self, generation_id: str) -> GeneratedContent | None:
        generated_content = self.generated_content_store.get(
            generation_id=generation_id
        )
        if generated_content is None:
            return None
        if generated_content.workflow_summary is not None:
            return generated_content
        return self._apply_generation_workflow_summary(
            generated_content=generated_content
        )

    def advance_remediation_session(
        self,
        *,
        session_id: str,
        request: RemediationWorkflowAdvanceRequest,
    ) -> RemediationWorkflowAdvanceResponse:
        session = self.get_remediation_session(session_id)
        progression_decision = self._remediation_progression_decision(session=session)
        if progression_decision.decision == "advance":
            executed_step, updated_session, generated_content = (
                self._execute_remediation_session_step(
                    session_id=session_id,
                    learner_prompt=request.learner_prompt,
                    curriculum_context=request.curriculum_context,
                )
            )
        else:
            executed_step, updated_session, generated_content = (
                self._execute_held_remediation_step(
                    session=session,
                    progression_decision=progression_decision,
                    learner_prompt=request.learner_prompt,
                    curriculum_context=request.curriculum_context,
                )
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
                "progression_evidence_observation_count": updated_session.progression_evidence_observation_count,
                "progression_evidence_confidence": updated_session.progression_evidence_confidence,
                "progression_average_observed_mastery": updated_session.progression_average_observed_mastery,
                "progression_low_support_success_count": updated_session.progression_low_support_success_count,
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
        _, current_step, generation_request = (
            self.remediation_workflow_coordinator.generation_request_for_current_step(
                session_id=session_id,
                learner_prompt=learner_prompt,
                curriculum_context=curriculum_context,
            )
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
            raise RuntimeError(
                "Remediation hold decision did not include a step index."
            )
        _, hold_step, generation_request = (
            self.remediation_workflow_coordinator.generation_request_for_step(
                session_id=session.session_id,
                step_index=hold_step_index,
                learner_prompt=learner_prompt,
                curriculum_context=[
                    *(curriculum_context or []),
                    f"Progression decision: {progression_decision.decision}.",
                    progression_decision.rationale
                    or "Hold on the current repair target before advancing.",
                ],
            )
        )
        generated_content = self.generate_content(generation_request)
        updated_session = self.remediation_workflow_coordinator.update_progression_decision(
            session_id=session.session_id,
            decision=progression_decision.decision,
            rationale=progression_decision.rationale,
            target_kc_ids=progression_decision.target_kc_ids or [],
            generation_id=generated_content.generation_id,
            step_index=hold_step_index,
            evidence_observation_count=progression_decision.matched_observation_count,
            evidence_confidence=progression_decision.evidence_confidence,
            average_observed_mastery=progression_decision.average_observed_mastery,
            low_support_success_count=progression_decision.low_support_success_count,
        )
        return hold_step, updated_session, generated_content

    def _remediation_progression_decision(
        self, *, session: RemediationWorkflowSession
    ) -> RemediationProgressDecision:
        if self.observation_profile_updater is None:
            return RemediationProgressDecision()
        observations = self.observation_store.list_recent(
            student_id=str(session.student_id)
        )
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
                "status": "complete"
                if session.current_step_index is None
                else "in_progress",
                "executed_phase": executed_step.phase,
                "executed_step_target_kc_ids": executed_step.target_kc_ids,
                "next_phase": next_step.phase if next_step is not None else None,
                "next_step_target_kc_ids": list(
                    session.summary.next_step.target_kc_ids
                ),
                "completed_step_count": len(session.completed_generation_ids),
                "step_count": len(session.steps),
                "progression_decision": session.progression_decision,
                "progression_rationale": session.progression_rationale,
                "progression_target_kc_ids": session.progression_target_kc_ids,
                "progression_evidence_observation_count": session.progression_evidence_observation_count,
                "progression_evidence_confidence": session.progression_evidence_confidence,
                "progression_average_observed_mastery": session.progression_average_observed_mastery,
                "progression_low_support_success_count": session.progression_low_support_success_count,
                "next_step_rationale": session.summary.next_step.rationale,
                "summary_continue_action": session.summary.continue_action.model_dump(
                    mode="json"
                ),
            },
        }
        if misconception_signals is not None:
            enriched_request_context["misconception_signals"] = misconception_signals
        enriched_content = generated_content.model_copy(
            update={"request_context": enriched_request_context}
        )
        finalized_content = self._apply_generation_workflow_summary(
            generated_content=enriched_content
        )
        self._refresh_generated_content(finalized_content)
        return finalized_content

    def _current_remediation_step(
        self, session: RemediationWorkflowSession
    ) -> RemediationWorkflowStep | None:
        current_index = session.current_step_index
        if current_index is None or current_index >= len(session.steps):
            return None
        return session.steps[current_index]

    def _refresh_generated_content(self, generated_content: GeneratedContent) -> None:
        self.generated_content_store.refresh(content=generated_content)

    def _next_remediation_phase(
        self, session: RemediationWorkflowSession
    ) -> str | None:
        next_step = self._current_remediation_step(session)
        if next_step is None:
            return None
        return next_step.phase
