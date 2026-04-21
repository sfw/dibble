from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import (
    AdaptiveRouteDecision,
    GenerationModeCalibration,
    GenerationRequest,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.services.harness.authoring_rules import (
    _append_socratic_guidance,
    _micro_explanation_guidance,
    _worked_example_guidance,
    _worked_steps_visible,
    plan_practice_progression,
    plan_worked_example_progression,
    select_content_type,
)

_PROVIDER_SAFE_CONSTRAINT_KEYS = {
    "difficulty_band",
    "fading_strategy",
    "mode_calibration_applied",
    "practice_answer_check_focus",
    "practice_distractor_blueprint",
    "practice_distractor_family",
    "practice_distractor_focus",
    "practice_distractor_misconception_ids",
    "practice_distractor_remediation_hint",
    "practice_distractor_slots",
    "practice_distractor_style",
    "practice_distractor_support_intensity",
    "worked_example_fade_focus",
    "worked_example_hidden_step_role",
    "worked_example_learner_release",
    "worked_example_learner_release_intensity",
    "worked_example_progression_action",
    "worked_example_release_stage",
    "worked_example_release_transition",
    "worked_example_step_outline",
    "worked_example_transfer_move",
    "worked_example_transfer_plan",
    "worked_example_visible_step_roles",
    "worked_steps_visible",
}


@dataclass(frozen=True, slots=True)
class HarnessAuthoringPolicy:
    content_type: RequestedContentType
    prompt_guidance: str
    request_context: dict[str, object]
    generation_constraints: dict[str, object]


class HarnessAuthoringPolicyBuilder:
    """Builds authoring policy at the learner-private harness boundary.

    This keeps trajectory/support shaping in the harness while giving downstream
    provider-facing code a curriculum-safe policy artifact to consume.
    """

    def build(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
    ) -> HarnessAuthoringPolicy:
        mode_calibration = request.mode_calibration
        content_type, selection_mode, selection_rationale = select_content_type(
            profile,
            request,
            route,
            mode_calibration=mode_calibration,
        )
        request_context: dict[str, object] = {
            "learning_session_id": request.learning_session_id,
            "intent": request.intent.value,
            "target_kc_ids": request.target_kc_ids,
            "target_lo_ids": request.target_lo_ids,
            "curriculum_context": request.curriculum_context,
            "requested_content_type": request.requested_content_type.value
            if request.requested_content_type
            else None,
            "selected_content_type": content_type.value,
            "selection_mode": selection_mode,
        }
        if selection_rationale is not None:
            request_context["selection_rationale"] = selection_rationale
        if mode_calibration is not None:
            request_context["mode_calibration"] = mode_calibration.model_dump(
                mode="json"
            )
            if mode_calibration.sequence_action != "monitor":
                request_context["sequencing"] = {
                    "action": mode_calibration.sequence_action,
                    "primary_kc_id": mode_calibration.sequence_primary_kc_id,
                    "ordered_kc_ids": mode_calibration.sequence_kc_ids,
                    "deferred_kc_ids": mode_calibration.sequence_deferred_kc_ids,
                    "source": mode_calibration.sequence_source,
                    "rationale": mode_calibration.sequence_rationale,
                }
            if mode_calibration.session_signal != "insufficient":
                request_context["session_adaptation"] = {
                    "signal": mode_calibration.session_signal,
                    "source": mode_calibration.session_source,
                    "confidence": mode_calibration.session_confidence,
                    "support_bias": mode_calibration.session_support_bias,
                    "sequence_action": mode_calibration.session_sequence_action,
                    "primary_kc_id": mode_calibration.session_primary_kc_id,
                    "observation_count": mode_calibration.session_observation_count,
                    "assessment_count": mode_calibration.session_assessment_count,
                    "phase": mode_calibration.session_phase,
                    "recovery_intent": mode_calibration.session_recovery_intent,
                    "support_step_budget": mode_calibration.session_support_step_budget,
                    "support_steps_remaining": (
                        mode_calibration.session_support_steps_remaining
                    ),
                    "stuck_loop_risk": mode_calibration.session_stuck_loop_risk,
                    "arc_action": mode_calibration.session_arc_action,
                    "generated_step_count": (
                        mode_calibration.session_generated_step_count
                    ),
                    "positive_streak": mode_calibration.session_positive_streak,
                    "negative_streak": mode_calibration.session_negative_streak,
                    "current_evidence_signal": (
                        mode_calibration.current_evidence_signal
                    ),
                    "current_evidence_confidence": (
                        mode_calibration.current_evidence_confidence
                    ),
                    "current_evidence_rationale": (
                        mode_calibration.current_evidence_rationale
                    ),
                    "latest_prompt_style": (
                        mode_calibration.session_latest_prompt_style
                    ),
                    "latest_next_action": mode_calibration.session_latest_next_action,
                    "latest_evidence_strength": (
                        mode_calibration.session_latest_evidence_strength
                    ),
                    "socratic_steering_action": (
                        mode_calibration.socratic_steering_action
                    ),
                    "rationale": mode_calibration.session_rationale,
                }
            if mode_calibration.session_assessment_count > 0:
                request_context["socratic_follow_up"] = {
                    "action": mode_calibration.socratic_steering_action,
                    "arc_action": mode_calibration.session_arc_action,
                    "stuck_loop_risk": mode_calibration.session_stuck_loop_risk,
                    "latest_prompt_style": mode_calibration.session_latest_prompt_style,
                    "latest_next_action": mode_calibration.session_latest_next_action,
                    "latest_evidence_strength": (
                        mode_calibration.session_latest_evidence_strength
                    ),
                }
        if request.predictive_warm:
            request_context["is_predictive_warm"] = True
            if request.warm_reason is not None:
                request_context["warm_reason"] = request.warm_reason
            if request.source_generation_id is not None:
                request_context["source_generation_id"] = request.source_generation_id

        if content_type == RequestedContentType.practice_problem:
            prompt_guidance = self._practice_policy(
                profile=profile,
                request=request,
                mode_calibration=mode_calibration,
                request_context=request_context,
            )
        elif content_type == RequestedContentType.worked_example:
            prompt_guidance = self._worked_example_policy(
                profile=profile,
                request=request,
                mode_calibration=mode_calibration,
                request_context=request_context,
            )
        elif content_type == RequestedContentType.assessment_probe:
            prompt_guidance = (
                "Generate a short diagnostic probe that reveals learner understanding "
                "without giving away the full answer."
            )
        elif content_type == RequestedContentType.remedial_micro_module:
            prompt_guidance = (
                "Step back to prerequisite understanding, simplify language, and "
                "reconnect the learner to the target concept."
            )
        else:
            prompt_guidance = _append_socratic_guidance(
                _micro_explanation_guidance(request),
                mode_calibration=mode_calibration,
            )

        return HarnessAuthoringPolicy(
            content_type=content_type,
            prompt_guidance=prompt_guidance,
            request_context=request_context,
            generation_constraints={
                key: value
                for key, value in request_context.items()
                if key in _PROVIDER_SAFE_CONSTRAINT_KEYS
            },
        )

    def _practice_policy(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        mode_calibration: GenerationModeCalibration | None,
        request_context: dict[str, object],
    ) -> str:
        progression = plan_practice_progression(
            profile=profile,
            request=request,
            mode_calibration=mode_calibration,
        )
        request_context["difficulty_band"] = progression.difficulty_band.value
        request_context["difficulty_progression_action"] = progression.progression_action
        request_context["practice_distractor_style"] = progression.distractor_style
        request_context["practice_distractor_family"] = progression.distractor_family
        request_context["practice_distractor_support_intensity"] = (
            progression.distractor_support_intensity
        )
        request_context["practice_distractor_focus"] = progression.distractor_focus
        request_context["practice_distractor_blueprint"] = (
            progression.distractor_blueprint
        )
        request_context["practice_distractor_slots"] = progression.distractor_slots
        request_context["practice_answer_check_focus"] = (
            progression.answer_check_focus
        )
        request_context["practice_distractor_misconception_ids"] = (
            progression.target_misconception_ids
        )
        request_context["practice_distractor_remediation_hint"] = (
            progression.remediation_anchor
        )
        request_context["practice_distractor_rationale"] = (
            progression.distractor_rationale
        )
        request_context["mode_calibration_applied"] = progression.calibration_applied
        distractor_slots = "; ".join(progression.distractor_slots)
        blueprint_slots = "; ".join(
            f"{entry['slot']} ({entry['surface_shift']})"
            for entry in progression.distractor_blueprint
        )
        prompt_guidance = (
            "Create one practice problem with a clear success target, one concise worked cue, "
            f"and a brief answer-check instruction. Tune the problem to {progression.difficulty_band.value} difficulty. "
            f"Use the {progression.distractor_family.replace('_', ' ')} distractor family at {progression.distractor_support_intensity} support intensity "
            f"and structure it for {progression.progression_action.replace('_', ' ')}. "
            f"Distractor focus: {progression.distractor_focus}. "
            f"Distractor blueprint: {blueprint_slots}. "
            f"Distractor slots: {distractor_slots}. "
            f"Answer-check focus: {progression.answer_check_focus}."
        )
        if progression.remediation_anchor is not None:
            prompt_guidance = (
                f"{prompt_guidance} If you include a hint, anchor it in this corrective move: "
                f"{progression.remediation_anchor}."
            )
        return _append_socratic_guidance(
            prompt_guidance, mode_calibration=mode_calibration
        )

    def _worked_example_policy(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        mode_calibration: GenerationModeCalibration | None,
        request_context: dict[str, object],
    ) -> str:
        progression = plan_worked_example_progression(
            profile=profile,
            request=request,
            mode_calibration=mode_calibration,
        )
        request_context["fading_strategy"] = progression.fading.value
        request_context["worked_steps_visible"] = _worked_steps_visible(
            progression.fading
        )
        request_context["worked_example_progression_action"] = (
            progression.progression_action
        )
        request_context["worked_example_fade_focus"] = progression.fade_focus
        request_context["worked_example_release_stage"] = progression.release_stage
        request_context["worked_example_learner_release_intensity"] = (
            progression.learner_release_intensity
        )
        request_context["worked_example_release_transition"] = (
            progression.release_transition
        )
        request_context["worked_example_visible_step_roles"] = (
            progression.visible_step_roles
        )
        request_context["worked_example_hidden_step_role"] = (
            progression.hidden_step_role
        )
        request_context["worked_example_transfer_move"] = progression.transfer_move
        request_context["worked_example_transfer_plan"] = progression.transfer_plan
        request_context["worked_example_step_outline"] = progression.step_outline
        request_context["worked_example_learner_release"] = (
            progression.learner_release
        )
        request_context["worked_example_release_rationale"] = (
            progression.release_rationale
        )
        request_context["mode_calibration_applied"] = progression.calibration_applied
        return _append_socratic_guidance(
            _worked_example_guidance(
                progression.fading,
                progression.fade_focus,
                release_stage=progression.release_stage,
                learner_release_intensity=progression.learner_release_intensity,
                release_transition=progression.release_transition,
                visible_step_roles=progression.visible_step_roles,
                hidden_step_role=progression.hidden_step_role,
                transfer_move=progression.transfer_move,
                transfer_plan=progression.transfer_plan,
                step_outline=progression.step_outline,
                learner_release=progression.learner_release,
            ),
            mode_calibration=mode_calibration,
        )
