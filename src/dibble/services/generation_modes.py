from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    GenerationModeCalibration,
    GenerationRequest,
    PracticeDifficultyBand,
    RequestedContentType,
    TargetKcGenerationHint,
    WorkedExampleFading,
)
from dibble.models.profile import LearnerProfile, SignalLevel


@dataclass(frozen=True, slots=True)
class GenerationModePlan:
    content_type: RequestedContentType
    prompt_guidance: str
    request_context: dict[str, object]


@dataclass(frozen=True, slots=True)
class PracticeProgressionPlan:
    difficulty_band: PracticeDifficultyBand
    progression_action: str
    distractor_style: str
    distractor_family: str
    distractor_support_intensity: str
    distractor_focus: str
    distractor_blueprint: list[dict[str, str]]
    distractor_slots: list[str]
    answer_check_focus: str
    target_misconception_ids: list[str]
    remediation_anchor: str | None
    distractor_rationale: str
    calibration_applied: bool


@dataclass(frozen=True, slots=True)
class WorkedExampleProgressionPlan:
    fading: WorkedExampleFading
    progression_action: str
    fade_focus: str
    release_stage: str
    learner_release_intensity: str
    release_transition: str
    visible_step_roles: list[str]
    hidden_step_role: str
    transfer_move: str
    transfer_plan: dict[str, str]
    step_outline: list[str]
    learner_release: str
    release_rationale: str
    calibration_applied: bool


def build_generation_mode_plan(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
) -> GenerationModePlan:
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
        "requested_content_type": request.requested_content_type.value if request.requested_content_type else None,
        "selected_content_type": content_type.value,
        "selection_mode": selection_mode,
    }
    if selection_rationale is not None:
        request_context["selection_rationale"] = selection_rationale
    if mode_calibration is not None:
        request_context["mode_calibration"] = mode_calibration.model_dump(mode="json")
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
                "support_steps_remaining": mode_calibration.session_support_steps_remaining,
                "stuck_loop_risk": mode_calibration.session_stuck_loop_risk,
                "arc_action": mode_calibration.session_arc_action,
                "generated_step_count": mode_calibration.session_generated_step_count,
                "positive_streak": mode_calibration.session_positive_streak,
                "negative_streak": mode_calibration.session_negative_streak,
                "current_evidence_signal": mode_calibration.current_evidence_signal,
                "current_evidence_confidence": mode_calibration.current_evidence_confidence,
                "current_evidence_rationale": mode_calibration.current_evidence_rationale,
                "latest_prompt_style": mode_calibration.session_latest_prompt_style,
                "latest_next_action": mode_calibration.session_latest_next_action,
                "latest_evidence_strength": mode_calibration.session_latest_evidence_strength,
                "socratic_steering_action": mode_calibration.socratic_steering_action,
                "rationale": mode_calibration.session_rationale,
            }
        if mode_calibration.session_assessment_count > 0:
            request_context["socratic_follow_up"] = {
                "action": mode_calibration.socratic_steering_action,
                "arc_action": mode_calibration.session_arc_action,
                "stuck_loop_risk": mode_calibration.session_stuck_loop_risk,
                "latest_prompt_style": mode_calibration.session_latest_prompt_style,
                "latest_next_action": mode_calibration.session_latest_next_action,
                "latest_evidence_strength": mode_calibration.session_latest_evidence_strength,
            }
    if request.predictive_warm:
        request_context["is_predictive_warm"] = True
        if request.warm_reason is not None:
            request_context["warm_reason"] = request.warm_reason
        if request.source_generation_id is not None:
            request_context["source_generation_id"] = request.source_generation_id

    if content_type == RequestedContentType.practice_problem:
        progression = plan_practice_progression(profile=profile, request=request, mode_calibration=mode_calibration)
        request_context["difficulty_band"] = progression.difficulty_band.value
        request_context["difficulty_progression_action"] = progression.progression_action
        request_context["practice_distractor_style"] = progression.distractor_style
        request_context["practice_distractor_family"] = progression.distractor_family
        request_context["practice_distractor_support_intensity"] = progression.distractor_support_intensity
        request_context["practice_distractor_focus"] = progression.distractor_focus
        request_context["practice_distractor_blueprint"] = progression.distractor_blueprint
        request_context["practice_distractor_slots"] = progression.distractor_slots
        request_context["practice_answer_check_focus"] = progression.answer_check_focus
        request_context["practice_distractor_misconception_ids"] = progression.target_misconception_ids
        request_context["practice_distractor_remediation_hint"] = progression.remediation_anchor
        request_context["practice_distractor_rationale"] = progression.distractor_rationale
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
            f"Answer-check focus: {progression.answer_check_focus}. "
            f"Distractor rationale: {progression.distractor_rationale}."
        )
        if progression.remediation_anchor is not None:
            prompt_guidance = (
                f"{prompt_guidance} If you include a hint, anchor it in this corrective move: {progression.remediation_anchor}."
            )
        prompt_guidance = _append_socratic_guidance(prompt_guidance, mode_calibration=mode_calibration)
    elif content_type == RequestedContentType.worked_example:
        progression = plan_worked_example_progression(profile=profile, request=request, mode_calibration=mode_calibration)
        request_context["fading_strategy"] = progression.fading.value
        request_context["worked_steps_visible"] = _worked_steps_visible(progression.fading)
        request_context["worked_example_progression_action"] = progression.progression_action
        request_context["worked_example_fade_focus"] = progression.fade_focus
        request_context["worked_example_release_stage"] = progression.release_stage
        request_context["worked_example_learner_release_intensity"] = progression.learner_release_intensity
        request_context["worked_example_release_transition"] = progression.release_transition
        request_context["worked_example_visible_step_roles"] = progression.visible_step_roles
        request_context["worked_example_hidden_step_role"] = progression.hidden_step_role
        request_context["worked_example_transfer_move"] = progression.transfer_move
        request_context["worked_example_transfer_plan"] = progression.transfer_plan
        request_context["worked_example_step_outline"] = progression.step_outline
        request_context["worked_example_learner_release"] = progression.learner_release
        request_context["worked_example_release_rationale"] = progression.release_rationale
        request_context["mode_calibration_applied"] = progression.calibration_applied
        prompt_guidance = _append_socratic_guidance(
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
                release_rationale=progression.release_rationale,
            ),
            mode_calibration=mode_calibration,
        )
    elif content_type == RequestedContentType.assessment_probe:
        prompt_guidance = (
            "Generate a short diagnostic probe that reveals learner understanding without giving away the full answer."
        )
    elif content_type == RequestedContentType.remedial_micro_module:
        prompt_guidance = (
            "Step back to prerequisite understanding, simplify language, and reconnect the learner to the target concept."
        )
    else:
        prompt_guidance = (
            "Focus on clear explanation, one grounded example, and a concise check-for-understanding next step."
        )
        prompt_guidance = _append_socratic_guidance(prompt_guidance, mode_calibration=mode_calibration)

    return GenerationModePlan(
        content_type=content_type,
        prompt_guidance=prompt_guidance,
        request_context=request_context,
    )


def resolve_content_type(request: GenerationRequest) -> RequestedContentType:
    if request.requested_content_type is not None:
        return request.requested_content_type
    if request.intent == ContentIntent.remediation:
        return RequestedContentType.remedial_micro_module
    if request.intent == ContentIntent.practice:
        return RequestedContentType.practice_problem
    if request.intent == ContentIntent.assessment:
        return RequestedContentType.assessment_probe
    return RequestedContentType.micro_explanation


def select_content_type(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
    *,
    mode_calibration: GenerationModeCalibration | None = None,
) -> tuple[RequestedContentType, str, str | None]:
    if request.requested_content_type is not None:
        return request.requested_content_type, "explicit", None

    default_type = resolve_content_type(request)
    if (
        default_type == RequestedContentType.micro_explanation
        and mode_calibration is not None
        and mode_calibration.session_assessment_count > 0
    ):
        if mode_calibration.session_arc_action == "bridge_with_target" and mode_calibration.session_phase == "bridge":
            return (
                RequestedContentType.practice_problem,
                "session_arc",
                "Within-session recovery is in a bridge phase, so the next generated step should use one guided target problem before a freer transfer check.",
            )
        if mode_calibration.socratic_steering_action == "repair_then_model":
            return (
                RequestedContentType.worked_example,
                "socratic_follow_up",
                "Recent Socratic turns still point to prerequisite repair, so the next generated step should model the correction before freer explanation.",
            )
        if (
            mode_calibration.socratic_steering_action == "verify_transfer"
            and mode_calibration.session_support_bias > 0
            and mode_calibration.session_phase == "transfer_check"
        ):
            return (
                RequestedContentType.practice_problem,
                "socratic_follow_up",
                "Recent Socratic turns demonstrated understanding, so the next generated step should test independent application instead of re-explaining.",
            )
    if (
        default_type == RequestedContentType.micro_explanation
        and route.delivery_mode.value != "blended"
        and (
            profile.metacognitive_state.help_seeking in {SignalLevel.medium, SignalLevel.high}
            or profile.cognitive_load.total_load >= 0.7
            or profile.metacognitive_state.confidence_calibration < 0.45
        )
    ):
        return (
            RequestedContentType.worked_example,
            "adaptive",
            "The unified generation path shifted to a worked example because learner-state signals favored modeled support before freer explanation.",
        )

    return default_type, "intent_default", None


def select_practice_difficulty_band(
    profile: LearnerProfile,
    request: GenerationRequest,
) -> PracticeDifficultyBand:
    mastery = _average_target_mastery(profile, request)
    if profile.cognitive_load.total_load >= 0.75 or mastery < 0.4:
        return PracticeDifficultyBand.support
    if mastery >= 0.8 and profile.affective_state.engagement == SignalLevel.high:
        return PracticeDifficultyBand.stretch
    return PracticeDifficultyBand.on_grade


def select_worked_example_fading(
    profile: LearnerProfile,
    request: GenerationRequest,
) -> WorkedExampleFading:
    mastery = _average_target_mastery(profile, request)
    if (
        profile.cognitive_load.total_load >= 0.75
        or profile.affective_state.frustration in {SignalLevel.medium, SignalLevel.high}
    ):
        return WorkedExampleFading.full
    if (
        mastery < 0.75
        or profile.metacognitive_state.help_seeking in {SignalLevel.medium, SignalLevel.high}
        or profile.metacognitive_state.confidence_calibration < 0.6
        or profile.metacognitive_state.self_monitoring < 0.6
    ):
        return WorkedExampleFading.completion
    return WorkedExampleFading.independent


def apply_support_bias_to_difficulty_band(
    difficulty_band: PracticeDifficultyBand,
    mode_calibration: GenerationModeCalibration | None,
) -> PracticeDifficultyBand:
    if mode_calibration is None or mode_calibration.support_bias == 0:
        return difficulty_band
    bands = [
        PracticeDifficultyBand.support,
        PracticeDifficultyBand.on_grade,
        PracticeDifficultyBand.stretch,
    ]
    current_index = bands.index(difficulty_band)
    adjusted_index = max(0, min(len(bands) - 1, current_index + mode_calibration.support_bias))
    return bands[adjusted_index]


def apply_support_bias_to_fading(
    fading: WorkedExampleFading,
    mode_calibration: GenerationModeCalibration | None,
) -> WorkedExampleFading:
    if mode_calibration is None or mode_calibration.support_bias == 0:
        return fading
    strategies = [
        WorkedExampleFading.full,
        WorkedExampleFading.completion,
        WorkedExampleFading.independent,
    ]
    current_index = strategies.index(fading)
    adjusted_index = max(0, min(len(strategies) - 1, current_index + mode_calibration.support_bias))
    return strategies[adjusted_index]


def plan_practice_progression(
    *,
    profile: LearnerProfile,
    request: GenerationRequest,
    mode_calibration: GenerationModeCalibration | None,
) -> PracticeProgressionPlan:
    baseline_band = select_practice_difficulty_band(profile, request)
    difficulty_band = apply_support_bias_to_difficulty_band(baseline_band, mode_calibration)
    progression_action = "steady_practice"
    distractor_style = "single_contrast"

    if mode_calibration is not None:
        if mode_calibration.session_phase in {"stabilize", "repair"}:
            difficulty_band = PracticeDifficultyBand.support
            progression_action = "repair_rebuild"
            distractor_style = "misconception_contrast"
        elif mode_calibration.session_phase == "consolidate":
            difficulty_band = _cap_practice_band(difficulty_band, PracticeDifficultyBand.on_grade)
            progression_action = "guided_consolidation"
            distractor_style = "scaffolded_near_miss"
        elif mode_calibration.session_phase == "bridge":
            difficulty_band = _cap_practice_band(difficulty_band, PracticeDifficultyBand.on_grade)
            progression_action = "bridge_to_transfer"
            distractor_style = "target_return"
        elif (
            mode_calibration.progress_signal == "improving"
            and mode_calibration.support_bias > 0
            and mode_calibration.strategy_trajectory_state in {"accelerating", "consolidating", "insufficient"}
        ):
            if baseline_band != PracticeDifficultyBand.support:
                difficulty_band = _raise_practice_band(difficulty_band)
            progression_action = "advance_after_improvement"
            distractor_style = "near_transfer"
        elif mode_calibration.progress_signal == "declining":
            difficulty_band = PracticeDifficultyBand.support
            progression_action = "stabilize_after_decline"
            distractor_style = "misconception_contrast"
        elif mode_calibration.strategy_trajectory_state in {"plateaued", "volatile"}:
            difficulty_band = _cap_practice_band(difficulty_band, PracticeDifficultyBand.on_grade)
            progression_action = "vary_support_before_stretch"
            distractor_style = "scaffolded_near_miss"
        elif difficulty_band == PracticeDifficultyBand.stretch:
            progression_action = "advance_to_stretch"
            distractor_style = "near_transfer"
        elif difficulty_band == PracticeDifficultyBand.support:
            progression_action = "hold_support"
            distractor_style = "misconception_contrast"
        else:
            progression_action = "hold_on_grade"
            distractor_style = "single_contrast"
    elif difficulty_band == PracticeDifficultyBand.stretch:
        progression_action = "advance_to_stretch"
        distractor_style = "near_transfer"
    elif difficulty_band == PracticeDifficultyBand.support:
        progression_action = "hold_support"
        distractor_style = "misconception_contrast"
    else:
        progression_action = "hold_on_grade"

    primary_hint = _primary_target_hint(request)
    if (
        primary_hint is not None
        and primary_hint.misconception_ids
        and distractor_style == "single_contrast"
    ):
        distractor_style = "misconception_contrast"

    distractor_focus, target_misconception_ids, remediation_anchor = _practice_distractor_focus(
        request=request,
        distractor_style=distractor_style,
        progression_action=progression_action,
    )
    distractor_family, distractor_support_intensity, distractor_rationale = _practice_distractor_family(
        profile=profile,
        request=request,
        distractor_style=distractor_style,
        progression_action=progression_action,
        mode_calibration=mode_calibration,
    )
    distractor_blueprint, distractor_slots, answer_check_focus = _practice_distractor_blueprint(
        request=request,
        distractor_style=distractor_style,
        progression_action=progression_action,
        support_intensity=distractor_support_intensity,
    )

    return PracticeProgressionPlan(
        difficulty_band=difficulty_band,
        progression_action=progression_action,
        distractor_style=distractor_style,
        distractor_family=distractor_family,
        distractor_support_intensity=distractor_support_intensity,
        distractor_focus=distractor_focus,
        distractor_blueprint=distractor_blueprint,
        distractor_slots=distractor_slots,
        answer_check_focus=answer_check_focus,
        target_misconception_ids=target_misconception_ids,
        remediation_anchor=remediation_anchor,
        distractor_rationale=distractor_rationale,
        calibration_applied=difficulty_band != baseline_band,
    )


def plan_worked_example_progression(
    *,
    profile: LearnerProfile,
    request: GenerationRequest,
    mode_calibration: GenerationModeCalibration | None,
) -> WorkedExampleProgressionPlan:
    baseline_fading = select_worked_example_fading(profile, request)
    fading = apply_support_bias_to_fading(baseline_fading, mode_calibration)
    progression_action = "steady_release"
    fade_focus = "one parallel step after the example"

    if mode_calibration is not None:
        if mode_calibration.session_phase in {"stabilize", "repair"}:
            fading = WorkedExampleFading.full
            progression_action = "rebuild_with_full_model"
            fade_focus = "every reasoning step before learner completion"
        elif mode_calibration.session_phase == "consolidate":
            fading = WorkedExampleFading.completion
            progression_action = "partial_release"
            fade_focus = "only the final target-aligned step hidden from the learner"
        elif mode_calibration.session_phase == "bridge":
            fading = WorkedExampleFading.completion
            progression_action = "bridge_release"
            fade_focus = "a near-target example with the transfer move left unfinished"
        elif mode_calibration.session_phase == "transfer_check":
            fading = _raise_fading(fading)
            progression_action = "independent_transfer"
            fade_focus = "a quick cue before independent target completion"
        elif mode_calibration.progress_signal == "declining":
            fading = WorkedExampleFading.full
            progression_action = "stabilize_with_modeling"
            fade_focus = "every reasoning step before learner completion"
        elif mode_calibration.strategy_trajectory_state in {"plateaued", "volatile"}:
            fading = _cap_fading(fading, WorkedExampleFading.completion)
            progression_action = "vary_support_release"
            fade_focus = "a partially faded example with one decision left for the learner"
        elif mode_calibration.progress_signal == "improving" and mode_calibration.support_bias > 0:
            fading = _raise_fading(fading)
            progression_action = "accelerate_fade"
            fade_focus = "a quick cue before independent target completion"
        elif fading == WorkedExampleFading.full:
            progression_action = "hold_full_model"
            fade_focus = "every reasoning step before learner completion"
        elif fading == WorkedExampleFading.completion:
            progression_action = "partial_release"
            fade_focus = "only the final target-aligned step hidden from the learner"
        else:
            progression_action = "independent_transfer"
            fade_focus = "a quick cue before independent target completion"
    elif fading == WorkedExampleFading.full:
        progression_action = "hold_full_model"
        fade_focus = "every reasoning step before learner completion"
    elif fading == WorkedExampleFading.completion:
        progression_action = "partial_release"
        fade_focus = "only the final target-aligned step hidden from the learner"
    else:
        progression_action = "independent_transfer"
        fade_focus = "a quick cue before independent target completion"

    visible_step_roles, hidden_step_role, transfer_move = _worked_example_roles(
        request=request,
        fading=fading,
        progression_action=progression_action,
    )
    transfer_plan = _worked_example_transfer_plan(
        request=request,
        progression_action=progression_action,
        hidden_step_role=hidden_step_role,
        transfer_move=transfer_move,
    )
    step_outline, learner_release = _worked_example_step_outline(
        request=request,
        visible_step_roles=visible_step_roles,
        hidden_step_role=hidden_step_role,
        progression_action=progression_action,
        transfer_move=transfer_move,
        transfer_plan=transfer_plan,
    )
    release_stage, learner_release_intensity, release_transition, release_rationale = _worked_example_release_plan(
        profile=profile,
        fading=fading,
        progression_action=progression_action,
        visible_step_roles=visible_step_roles,
        hidden_step_role=hidden_step_role,
        transfer_move=transfer_move,
        mode_calibration=mode_calibration,
    )

    return WorkedExampleProgressionPlan(
        fading=fading,
        progression_action=progression_action,
        fade_focus=fade_focus,
        release_stage=release_stage,
        learner_release_intensity=learner_release_intensity,
        release_transition=release_transition,
        visible_step_roles=visible_step_roles,
        hidden_step_role=hidden_step_role,
        transfer_move=transfer_move,
        transfer_plan=transfer_plan,
        step_outline=step_outline,
        learner_release=learner_release,
        release_rationale=release_rationale,
        calibration_applied=fading != baseline_fading,
    )


def _worked_example_guidance(
    fading: WorkedExampleFading,
    fade_focus: str,
    *,
    release_stage: str,
    learner_release_intensity: str,
    release_transition: str,
    visible_step_roles: list[str],
    hidden_step_role: str,
    transfer_move: str,
    transfer_plan: dict[str, str],
    step_outline: list[str],
    learner_release: str,
    release_rationale: str,
) -> str:
    visible_roles = ", ".join(visible_step_roles)
    outline_text = "; ".join(step_outline)
    transfer_summary = (
        f"Preserve: {transfer_plan.get('preserve', 'the same structure')}. "
        f"Change: {transfer_plan.get('change', transfer_move)}. "
        f"Learner-owned move: {transfer_plan.get('learner_owned_move', hidden_step_role)}. "
        f"Check prompt: {transfer_plan.get('check_prompt', 'have the learner name the structural carryover')}."
    )
    if fading == WorkedExampleFading.full:
        return (
            "Generate one fully worked example with step-by-step reasoning, then ask the learner to explain why the final step works. "
            f"Keep the fade focus on {fade_focus}. Name the visible step roles ({visible_roles}) and reserve {hidden_step_role} for the learner. "
            f"Use release stage {release_stage.replace('_', ' ')} with {learner_release_intensity.replace('_', ' ')} release. "
            f"Transition the learner from {release_transition}. "
            f"Use this step outline: {outline_text}. "
            f"Learner release: {learner_release}. "
            f"Use the example to prepare this transfer move: {transfer_move}. "
            f"{transfer_summary} "
            f"Release rationale: {release_rationale}."
        )
    if fading == WorkedExampleFading.completion:
        return (
            "Generate one mostly worked example, then leave the final step for the learner to complete with a clear cue. "
            f"Keep the fade focus on {fade_focus}. Name the visible step roles ({visible_roles}) and reserve {hidden_step_role} for the learner. "
            f"Use release stage {release_stage.replace('_', ' ')} with {learner_release_intensity.replace('_', ' ')} release. "
            f"Transition the learner from {release_transition}. "
            f"Use this step outline: {outline_text}. "
            f"Learner release: {learner_release}. "
            f"Use the example to prepare this transfer move: {transfer_move}. "
            f"{transfer_summary} "
            f"Release rationale: {release_rationale}."
        )
    return (
        "Generate one concise example as a cue, then shift quickly to independent learner completion of a parallel step. "
        f"Keep the fade focus on {fade_focus}. Name the visible step roles ({visible_roles}) and reserve {hidden_step_role} for the learner. "
        f"Use release stage {release_stage.replace('_', ' ')} with {learner_release_intensity.replace('_', ' ')} release. "
        f"Transition the learner from {release_transition}. "
        f"Use this step outline: {outline_text}. "
        f"Learner release: {learner_release}. "
        f"Use the example to prepare this transfer move: {transfer_move}. "
        f"{transfer_summary} "
        f"Release rationale: {release_rationale}."
    )


def _worked_steps_visible(fading: WorkedExampleFading) -> int:
    mapping = {
        WorkedExampleFading.full: 3,
        WorkedExampleFading.completion: 2,
        WorkedExampleFading.independent: 1,
    }
    return mapping[fading]


def _append_socratic_guidance(
    guidance: str,
    *,
    mode_calibration: GenerationModeCalibration | None,
) -> str:
    if (
        mode_calibration is None
        or mode_calibration.session_assessment_count <= 0
        or mode_calibration.session_source == "insufficient"
    ):
        return guidance
    if mode_calibration.socratic_steering_action == "repair_then_model":
        return (
            f"{guidance} Start from the exact prerequisite gap surfaced in the recent Socratic turn and make the corrected reasoning explicit before asking for independence."
        )
    if mode_calibration.session_arc_action == "bridge_with_target":
        return (
            f"{guidance} Keep this as a guided bridge on the current target, then end with one light application that prepares the learner for transfer."
        )
    if mode_calibration.session_arc_action == "restate_then_apply":
        return (
            f"{guidance} Ask the learner to restate the repaired idea briefly, then apply it once in a closely related case."
        )
    if mode_calibration.session_arc_action == "reprobe_new_angle":
        return (
            f"{guidance} Change the representation or comparison and avoid adding another full scaffold in the same wording."
        )
    if mode_calibration.socratic_steering_action == "clarify_then_check":
        return (
            f"{guidance} Address the exact wording or reasoning ambiguity surfaced in the recent Socratic follow-up, then end with one short self-explanation check."
        )
    if mode_calibration.socratic_steering_action == "verify_transfer":
        return (
            f"{guidance} Keep the final cue light and use a nearby transfer context so the learner has to apply the idea, not restate it."
        )
    if mode_calibration.socratic_steering_action == "probe_from_new_angle":
        return f"{guidance} Use a fresh representation or comparison so the next step does not simply repeat the last Socratic wording."
    return guidance


def _practice_distractor_focus(
    *,
    request: GenerationRequest,
    distractor_style: str,
    progression_action: str,
) -> tuple[str, list[str], str | None]:
    hint = _primary_target_hint(request)
    if hint is None:
        return _default_practice_distractor_focus(distractor_style, progression_action), [], None

    misconception_ids = hint.misconception_ids[:1]
    misconception_label = hint.misconception_labels[0] if hint.misconception_labels else None
    remediation_anchor = hint.remediation_hints[0] if hint.remediation_hints else None
    concept_anchor = hint.kc_name
    if misconception_label is None:
        return _default_practice_distractor_focus(distractor_style, progression_action), misconception_ids, remediation_anchor

    style_map = {
        "misconception_contrast": (
            f"Include one distractor that mirrors the common misconception '{misconception_label}' around {concept_anchor} without reusing the learner's exact wording."
        ),
        "scaffolded_near_miss": (
            f"Include one near miss that brushes against '{misconception_label}' for {concept_anchor} and one cleaner structural contrast."
        ),
        "target_return": (
            f"Use one bridge distractor that revisits '{misconception_label}' before returning the learner to {concept_anchor}."
        ),
        "near_transfer": (
            f"Use one nearby-transfer distractor that changes the surface context but still checks against '{misconception_label}' in {concept_anchor}."
        ),
        "single_contrast": (
            f"Make the main contrast expose '{misconception_label}' in {concept_anchor} instead of relying on a generic wrong answer."
        ),
    }
    return style_map.get(
        distractor_style,
        _default_practice_distractor_focus(distractor_style, progression_action),
    ), misconception_ids, remediation_anchor


def _default_practice_distractor_focus(distractor_style: str, progression_action: str) -> str:
    style_map = {
        "misconception_contrast": "Contrast one likely wrong move with one clearly correct structural alternative.",
        "scaffolded_near_miss": "Use one close near miss and one simpler structural contrast so the learner has to discriminate, not guess.",
        "target_return": "Use one bridge option that almost works before returning the learner to the exact target move.",
        "near_transfer": "Use one distractor that changes the surface story but preserves the same underlying decision.",
        "single_contrast": "Use one concise contrast that makes the target structure visible without adding noise.",
    }
    return style_map.get(
        distractor_style,
        f"Use distractors that support {progression_action.replace('_', ' ')} without adding random variation.",
    )


def _practice_distractor_blueprint(
    *,
    request: GenerationRequest,
    distractor_style: str,
    progression_action: str,
    support_intensity: str,
) -> tuple[list[dict[str, str]], list[str], str]:
    hint = _primary_target_hint(request)
    concept_anchor = hint.kc_name if hint is not None else "the target concept"
    nearby_anchor = hint.nearby_kc_names[0] if hint is not None and hint.nearby_kc_names else "a nearby parallel case"
    misconception_label = hint.misconception_labels[0] if hint is not None and hint.misconception_labels else "the likely misconception"
    misconception_description = (
        hint.misconception_descriptions[0]
        if hint is not None and hint.misconception_descriptions
        else "the most common wrong structural move"
    )
    remediation_hint = (
        hint.remediation_hints[0]
        if hint is not None and hint.remediation_hints
        else f"restate the corrected structure in {concept_anchor} before choosing"
    )
    surface_shift = {
        "explicit": "same_representation",
        "moderate": "light_surface_shift",
        "light": "nearby_context_shift",
    }.get(support_intensity, "light_surface_shift")
    slot_map = {
        "misconception_contrast": [
            {
                "slot": "misconception_mirror",
                "role": "mirror the tempting wrong move",
                "surface_shift": surface_shift,
                "structural_target": f"preserve the correct structure in {concept_anchor}",
                "temptation_basis": f"{misconception_label} around {concept_anchor}",
                "repair_cue": remediation_hint,
            },
            {
                "slot": "structural_contrast",
                "role": "show the clean structural contrast",
                "surface_shift": surface_shift,
                "structural_target": f"keep the comparison anchored in {concept_anchor}",
                "temptation_basis": misconception_description,
                "repair_cue": f"name what the correct structure preserves in {concept_anchor}",
            },
        ],
        "scaffolded_near_miss": [
            {
                "slot": "near_miss",
                "role": "include one almost-correct option",
                "surface_shift": surface_shift,
                "structural_target": f"discriminate the final structural move in {concept_anchor}",
                "temptation_basis": misconception_description,
                "repair_cue": remediation_hint,
            },
            {
                "slot": "clean_contrast",
                "role": "add one cleaner comparison case",
                "surface_shift": surface_shift,
                "structural_target": f"make the decisive structure of {concept_anchor} visible",
                "temptation_basis": f"a simplified contrast around {concept_anchor}",
                "repair_cue": f"state the decisive clue that keeps {concept_anchor} correct",
            },
        ],
        "target_return": [
            {
                "slot": "bridge_return",
                "role": "start from the nearby repair case and return",
                "surface_shift": surface_shift,
                "structural_target": f"carry the repaired move from {nearby_anchor} back to {concept_anchor}",
                "temptation_basis": f"drifting from {nearby_anchor} without returning to {concept_anchor}",
                "repair_cue": remediation_hint,
            },
            {
                "slot": "repair_anchor",
                "role": "anchor the repaired move explicitly",
                "surface_shift": "same_representation",
                "structural_target": f"hold the corrected structure in {concept_anchor}",
                "temptation_basis": misconception_label,
                "repair_cue": remediation_hint,
            },
        ],
        "near_transfer": [
            {
                "slot": "surface_swap",
                "role": "change the story while keeping the structure",
                "surface_shift": surface_shift,
                "structural_target": f"preserve the same decision in {concept_anchor}",
                "temptation_basis": f"surface cues that distract from {concept_anchor}",
                "repair_cue": f"name what stayed structurally the same in {concept_anchor}",
            },
            {
                "slot": "structural_echo",
                "role": "echo the deep structure in a nearby context",
                "surface_shift": "nearby_context_shift",
                "structural_target": f"apply {concept_anchor} through {nearby_anchor}",
                "temptation_basis": f"treating {nearby_anchor} as a different structure entirely",
                "repair_cue": f"track the shared structure between {concept_anchor} and {nearby_anchor}",
            },
        ],
        "single_contrast": [
            {
                "slot": "main_contrast",
                "role": "expose one concise tempting contrast",
                "surface_shift": surface_shift,
                "structural_target": f"keep the key move visible in {concept_anchor}",
                "temptation_basis": f"{misconception_label} around {concept_anchor}",
                "repair_cue": remediation_hint,
            },
        ],
    }
    answer_check_map = {
        "misconception_contrast": f"Ask the learner to explain why the correct answer avoids {misconception_label} in {concept_anchor}.",
        "scaffolded_near_miss": f"Ask the learner to name the small difference between the near miss and the correct structure in {concept_anchor}.",
        "target_return": f"Ask the learner to explain how the repaired idea from {nearby_anchor} returns to {concept_anchor}.",
        "near_transfer": f"Ask the learner to name what stayed structurally the same even though the context changed from {concept_anchor} to {nearby_anchor}.",
        "single_contrast": f"Ask the learner to state the decisive structural clue that makes the correct choice work in {concept_anchor}.",
    }
    blueprint = slot_map.get(
        distractor_style,
        [
            {
                "slot": "main_contrast",
                "role": "support the target contrast cleanly",
                "surface_shift": surface_shift,
                "structural_target": f"support {progression_action.replace('_', ' ')} in {concept_anchor}",
                "temptation_basis": f"a tempting wrong move around {concept_anchor}",
                "repair_cue": remediation_hint,
            }
        ],
    )
    return (
        blueprint,
        [f"{entry['slot']}: {entry['role']}" for entry in blueprint],
        answer_check_map.get(
            distractor_style,
            f"Ask the learner to justify the key move that supports {progression_action.replace('_', ' ')}.",
        ),
    )


def _practice_distractor_family(
    *,
    profile: LearnerProfile,
    request: GenerationRequest,
    distractor_style: str,
    progression_action: str,
    mode_calibration: GenerationModeCalibration | None,
) -> tuple[str, str, str]:
    support_intensity, rationale = _practice_support_intensity(
        profile=profile,
        progression_action=progression_action,
        mode_calibration=mode_calibration,
    )
    family_map = {
        "misconception_contrast": "misconception_mirror_pair",
        "scaffolded_near_miss": "scaffolded_near_miss_pair",
        "target_return": "bridge_back_pair",
        "near_transfer": "surface_swap_transfer_pair",
        "single_contrast": "single_structural_contrast",
    }
    family = family_map.get(distractor_style, "single_structural_contrast")
    hint = _primary_target_hint(request)
    if hint is not None and hint.misconception_labels and distractor_style == "misconception_contrast":
        support_intensity = "explicit" if support_intensity == "moderate" else support_intensity
    if hint is not None and hint.misconception_labels:
        rationale = f"{rationale} Ground the wrong answer family in {hint.misconception_labels[0]}."
    return family, support_intensity, rationale


def _practice_support_intensity(
    *,
    profile: LearnerProfile,
    progression_action: str,
    mode_calibration: GenerationModeCalibration | None,
) -> tuple[str, str]:
    if mode_calibration is not None and mode_calibration.session_phase in {"stabilize", "repair"}:
        return (
            "explicit",
            "Same-session repair is still active, so distractors should keep the comparison space tight and visibly contrast the corrected move.",
        )
    if _needs_reliable_support(profile=profile, mode_calibration=mode_calibration):
        return (
            "explicit",
            "Reliable durable load or metacognitive signals still point to support need, so distractors should stay close to the misconception and avoid noisy variation.",
        )
    if progression_action in {"repair_rebuild", "hold_support", "stabilize_after_decline"}:
        return (
            "explicit",
            "The current progression still calls for support, so distractors should make the corrected move unmistakable before asking for freer discrimination.",
        )
    if progression_action in {"advance_after_improvement", "advance_to_stretch"} or _ready_for_reliable_release(
        profile=profile,
        mode_calibration=mode_calibration,
    ):
        return (
            "light",
            "Recent stable recovery supports lighter distractors, so the learner has to discriminate the structure without heavy scaffolding.",
        )
    return (
        "moderate",
        "Signals are mixed, so distractors should still guide the key contrast without over-modeling every wrong move.",
    )


def _worked_example_roles(
    *,
    request: GenerationRequest,
    fading: WorkedExampleFading,
    progression_action: str,
) -> tuple[list[str], str, str]:
    hint = _primary_target_hint(request)
    concept_anchor = hint.kc_name if hint is not None else "the target concept"
    nearby_anchor = hint.nearby_kc_names[0] if hint is not None and hint.nearby_kc_names else "a nearby parallel case"

    if progression_action in {"rebuild_with_full_model", "stabilize_with_modeling", "hold_full_model"}:
        return ["setup", "reasoning", "check"], "self-explanation", f"explain why the repaired reasoning works in {concept_anchor}"
    if progression_action == "bridge_release":
        return ["setup", "worked bridge"], "target return", f"carry the repaired idea from {nearby_anchor} back into {concept_anchor}"
    if progression_action in {"independent_transfer", "accelerate_fade"} or fading == WorkedExampleFading.independent:
        return ["cue"], "independent application", f"apply {concept_anchor} in {nearby_anchor}"
    return ["setup", "worked step"], "target completion", f"finish the final {concept_anchor} move independently"


def _worked_example_step_outline(
    *,
    request: GenerationRequest,
    visible_step_roles: list[str],
    hidden_step_role: str,
    progression_action: str,
    transfer_move: str,
    transfer_plan: dict[str, str],
) -> tuple[list[str], str]:
    hint = _primary_target_hint(request)
    concept_anchor = hint.kc_name if hint is not None else "the target concept"
    nearby_anchor = hint.nearby_kc_names[0] if hint is not None and hint.nearby_kc_names else "a nearby parallel case"
    role_map = {
        "setup": f"setup: establish the representation or givens for {concept_anchor}",
        "reasoning": f"reasoning: model the key structural relationship that makes {concept_anchor} work",
        "check": f"check: verify the result with a quick explanation tied back to {concept_anchor}",
        "worked step": f"worked step: show the first target-aligned move in {concept_anchor}",
        "worked bridge": f"worked bridge: demonstrate the same idea in {nearby_anchor} before returning to {concept_anchor}",
        "cue": f"cue: give only the lightest setup needed to remind the learner how {concept_anchor} starts",
    }
    step_outline = [role_map.get(role, f"{role}: keep the step concise and aligned to {concept_anchor}") for role in visible_step_roles]
    if hidden_step_role == "self-explanation":
        learner_release = f"self-explanation: ask the learner to explain why the repaired reasoning now works in {concept_anchor}."
    elif hidden_step_role == "target return":
        learner_release = f"target return: ask the learner to carry the repaired idea from {nearby_anchor} back into {concept_anchor}."
    elif hidden_step_role == "independent application":
        learner_release = f"independent application: ask the learner to apply {concept_anchor} independently in {nearby_anchor}."
    else:
        learner_release = f"target completion: ask the learner to finish the final move in {concept_anchor} and justify it briefly."
    if progression_action == "bridge_release":
        learner_release = (
            f"{learner_release} Keep the bridge explicit so the learner sees how the example returns from {nearby_anchor} to {concept_anchor}."
        )
    if progression_action == "independent_transfer":
        learner_release = f"{learner_release} Keep the final cue light and point toward this transfer move: {transfer_move}."
    if transfer_plan.get("check_prompt"):
        learner_release = f"{learner_release} Check prompt: {transfer_plan['check_prompt']}."
    return step_outline, learner_release


def _worked_example_transfer_plan(
    *,
    request: GenerationRequest,
    progression_action: str,
    hidden_step_role: str,
    transfer_move: str,
) -> dict[str, str]:
    hint = _primary_target_hint(request)
    concept_anchor = hint.kc_name if hint is not None else "the target concept"
    nearby_anchor = hint.nearby_kc_names[0] if hint is not None and hint.nearby_kc_names else concept_anchor
    bridge_context = nearby_anchor if progression_action in {"bridge_release", "independent_transfer", "accelerate_fade"} else concept_anchor
    if progression_action == "bridge_release":
        preserve = f"the repaired structure in {concept_anchor} stays the same"
        change = f"the example now bridges through {nearby_anchor} before returning to {concept_anchor}"
        check_prompt = f"name what stayed the same and carry the repaired move from {nearby_anchor} back to {concept_anchor}"
    elif progression_action in {"independent_transfer", "accelerate_fade"}:
        preserve = f"the same deep structure of {concept_anchor} stays in place"
        change = f"the learner now applies it in {nearby_anchor} with lighter cueing"
        check_prompt = f"name what stayed structurally the same and complete the {hidden_step_role}"
    else:
        preserve = f"the same target structure of {concept_anchor} stays visible"
        change = f"the learner now owns the last move in {concept_anchor}"
        check_prompt = f"state the structural carryover and complete the {hidden_step_role}"
    return {
        "source_context": concept_anchor,
        "bridge_context": bridge_context,
        "preserve": preserve,
        "change": change,
        "learner_owned_move": hidden_step_role,
        "check_prompt": check_prompt,
    }


def _worked_example_release_plan(
    *,
    profile: LearnerProfile,
    fading: WorkedExampleFading,
    progression_action: str,
    visible_step_roles: list[str],
    hidden_step_role: str,
    transfer_move: str,
    mode_calibration: GenerationModeCalibration | None,
) -> tuple[str, str, str, str]:
    visible_text = " -> ".join(visible_step_roles)
    release_transition = f"{visible_text} -> {hidden_step_role}"
    if progression_action in {"rebuild_with_full_model", "stabilize_with_modeling", "hold_full_model"}:
        return (
            "full_model_then_self_explain",
            "high_support",
            release_transition,
            "Keep the learner release on explanation rather than production because the current support need is still high.",
        )
    if progression_action == "bridge_release":
        return (
            "bridge_example_then_target_return",
            "guided_bridge",
            release_transition,
            f"Use the visible bridge step to move from the repaired case into {transfer_move} without pretending the learner is ready for a cold transfer.",
        )
    if fading == WorkedExampleFading.independent or progression_action in {"accelerate_fade", "independent_transfer"}:
        rationale = (
            "Stable recovery and challenge readiness support a light release, so the learner should own the transfer move after a minimal cue."
            if _ready_for_reliable_release(profile=profile, mode_calibration=mode_calibration)
            else "The learner is ready for a light release, so the example should quickly hand off the transfer move."
        )
        return (
            "cue_then_transfer",
            "light_release",
            release_transition,
            rationale,
        )
    rationale = (
        "Reliable support signals are still present, so the final learner-owned step should be narrow and clearly cued."
        if _needs_reliable_support(profile=profile, mode_calibration=mode_calibration)
        else "Keep one clear learner-owned completion step so support fades by role rather than by removing the whole example."
    )
    return (
        "completion_then_justify",
        "guided_release",
        release_transition,
        rationale,
    )


def _primary_target_hint(request: GenerationRequest) -> TargetKcGenerationHint | None:
    if not request.target_kc_hints:
        return None
    return request.target_kc_hints[0]


def _average_target_mastery(profile: LearnerProfile, request: GenerationRequest) -> float:
    if request.target_kc_ids:
        values = [profile.knowledge_state.kc_mastery.get(kc_id, 0.0) for kc_id in request.target_kc_ids]
    elif request.target_lo_ids:
        values = [profile.knowledge_state.lo_mastery.get(lo_id, 0.0) for lo_id in request.target_lo_ids]
    else:
        values = list(profile.knowledge_state.kc_mastery.values()) or [0.5]
    return sum(values) / len(values)


def _needs_reliable_support(
    *,
    profile: LearnerProfile,
    mode_calibration: GenerationModeCalibration | None,
) -> bool:
    if profile.cognitive_load.total_load >= 0.76:
        return True
    if mode_calibration is None:
        return False
    if (
        mode_calibration.state_profile_source != "insufficient"
        and mode_calibration.state_profile_load_reliability >= 0.58
        and mode_calibration.state_profile_overload_risk >= 0.64
    ):
        return True
    return (
        mode_calibration.state_profile_source != "insufficient"
        and mode_calibration.state_profile_metacognitive_reliability >= 0.58
        and mode_calibration.state_profile_confidence_calibration <= 0.42
        and mode_calibration.state_profile_help_seeking in {"medium", "high"}
    ) or (
        mode_calibration.trait_profile_source != "insufficient"
        and mode_calibration.trait_profile_working_memory_reliability >= 0.68
        and mode_calibration.trait_profile_challenge_tolerance < 0.48
        and mode_calibration.trait_profile_challenge_evidence_strength >= 0.52
    )


def _ready_for_reliable_release(
    *,
    profile: LearnerProfile,
    mode_calibration: GenerationModeCalibration | None,
) -> bool:
    if mode_calibration is None:
        return False
    if (
        mode_calibration.state_profile_source != "insufficient"
        and mode_calibration.state_profile_recovery_stability >= 0.68
        and mode_calibration.state_profile_metacognitive_reliability >= 0.58
        and mode_calibration.state_profile_total_load <= 0.5
        and profile.metacognitive_state.help_seeking == SignalLevel.low
    ):
        return True
    return (
        mode_calibration.trait_profile_source != "insufficient"
        and mode_calibration.trait_profile_trait_stability >= 0.72
        and mode_calibration.trait_profile_challenge_tolerance >= 0.66
        and mode_calibration.trait_profile_challenge_evidence_strength >= 0.58
    )


def _cap_practice_band(
    current: PracticeDifficultyBand,
    ceiling: PracticeDifficultyBand,
) -> PracticeDifficultyBand:
    order = [
        PracticeDifficultyBand.support,
        PracticeDifficultyBand.on_grade,
        PracticeDifficultyBand.stretch,
    ]
    return order[min(order.index(current), order.index(ceiling))]


def _raise_practice_band(current: PracticeDifficultyBand) -> PracticeDifficultyBand:
    order = [
        PracticeDifficultyBand.support,
        PracticeDifficultyBand.on_grade,
        PracticeDifficultyBand.stretch,
    ]
    return order[min(len(order) - 1, order.index(current) + 1)]


def _cap_fading(
    current: WorkedExampleFading,
    ceiling: WorkedExampleFading,
) -> WorkedExampleFading:
    order = [
        WorkedExampleFading.full,
        WorkedExampleFading.completion,
        WorkedExampleFading.independent,
    ]
    return order[min(order.index(current), order.index(ceiling))]


def _raise_fading(current: WorkedExampleFading) -> WorkedExampleFading:
    order = [
        WorkedExampleFading.full,
        WorkedExampleFading.completion,
        WorkedExampleFading.independent,
    ]
    return order[min(len(order) - 1, order.index(current) + 1)]
