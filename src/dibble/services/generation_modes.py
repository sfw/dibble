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
    distractor_focus: str
    target_misconception_ids: list[str]
    remediation_anchor: str | None
    calibration_applied: bool


@dataclass(frozen=True, slots=True)
class WorkedExampleProgressionPlan:
    fading: WorkedExampleFading
    progression_action: str
    fade_focus: str
    visible_step_roles: list[str]
    hidden_step_role: str
    transfer_move: str
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
                "generated_step_count": mode_calibration.session_generated_step_count,
                "positive_streak": mode_calibration.session_positive_streak,
                "negative_streak": mode_calibration.session_negative_streak,
                "latest_prompt_style": mode_calibration.session_latest_prompt_style,
                "latest_next_action": mode_calibration.session_latest_next_action,
                "latest_evidence_strength": mode_calibration.session_latest_evidence_strength,
                "socratic_steering_action": mode_calibration.socratic_steering_action,
                "rationale": mode_calibration.session_rationale,
            }
        if mode_calibration.session_assessment_count > 0:
            request_context["socratic_follow_up"] = {
                "action": mode_calibration.socratic_steering_action,
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
        request_context["practice_distractor_focus"] = progression.distractor_focus
        request_context["practice_distractor_misconception_ids"] = progression.target_misconception_ids
        request_context["practice_distractor_remediation_hint"] = progression.remediation_anchor
        request_context["mode_calibration_applied"] = progression.calibration_applied
        prompt_guidance = (
            "Create one practice problem with a clear success target, one concise worked cue, "
            f"and a brief answer-check instruction. Tune the problem to {progression.difficulty_band.value} difficulty. "
            f"Use {progression.distractor_style.replace('_', ' ')} distractors and structure it for {progression.progression_action.replace('_', ' ')}. "
            f"Distractor focus: {progression.distractor_focus}."
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
        request_context["worked_example_visible_step_roles"] = progression.visible_step_roles
        request_context["worked_example_hidden_step_role"] = progression.hidden_step_role
        request_context["worked_example_transfer_move"] = progression.transfer_move
        request_context["mode_calibration_applied"] = progression.calibration_applied
        prompt_guidance = _append_socratic_guidance(
            _worked_example_guidance(
                progression.fading,
                progression.fade_focus,
                visible_step_roles=progression.visible_step_roles,
                hidden_step_role=progression.hidden_step_role,
                transfer_move=progression.transfer_move,
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

    distractor_focus, target_misconception_ids, remediation_anchor = _practice_distractor_focus(
        request=request,
        distractor_style=distractor_style,
        progression_action=progression_action,
    )

    return PracticeProgressionPlan(
        difficulty_band=difficulty_band,
        progression_action=progression_action,
        distractor_style=distractor_style,
        distractor_focus=distractor_focus,
        target_misconception_ids=target_misconception_ids,
        remediation_anchor=remediation_anchor,
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

    return WorkedExampleProgressionPlan(
        fading=fading,
        progression_action=progression_action,
        fade_focus=fade_focus,
        visible_step_roles=visible_step_roles,
        hidden_step_role=hidden_step_role,
        transfer_move=transfer_move,
        calibration_applied=fading != baseline_fading,
    )


def _worked_example_guidance(
    fading: WorkedExampleFading,
    fade_focus: str,
    *,
    visible_step_roles: list[str],
    hidden_step_role: str,
    transfer_move: str,
) -> str:
    visible_roles = ", ".join(visible_step_roles)
    if fading == WorkedExampleFading.full:
        return (
            "Generate one fully worked example with step-by-step reasoning, then ask the learner to explain why the final step works. "
            f"Keep the fade focus on {fade_focus}. Name the visible step roles ({visible_roles}) and reserve {hidden_step_role} for the learner. "
            f"Use the example to prepare this transfer move: {transfer_move}."
        )
    if fading == WorkedExampleFading.completion:
        return (
            "Generate one mostly worked example, then leave the final step for the learner to complete with a clear cue. "
            f"Keep the fade focus on {fade_focus}. Name the visible step roles ({visible_roles}) and reserve {hidden_step_role} for the learner. "
            f"Use the example to prepare this transfer move: {transfer_move}."
        )
    return (
        "Generate one concise example as a cue, then shift quickly to independent learner completion of a parallel step. "
        f"Keep the fade focus on {fade_focus}. Name the visible step roles ({visible_roles}) and reserve {hidden_step_role} for the learner. "
        f"Use the example to prepare this transfer move: {transfer_move}."
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
