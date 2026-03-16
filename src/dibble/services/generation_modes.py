from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    GenerationModeCalibration,
    GenerationRequest,
    PracticeDifficultyBand,
    RequestedContentType,
    WorkedExampleFading,
)
from dibble.models.profile import LearnerProfile, SignalLevel


@dataclass(frozen=True, slots=True)
class GenerationModePlan:
    content_type: RequestedContentType
    prompt_guidance: str
    request_context: dict[str, object]


def build_generation_mode_plan(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
) -> GenerationModePlan:
    mode_calibration = request.mode_calibration
    content_type, selection_mode, selection_rationale = select_content_type(profile, request, route)
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
                "rationale": mode_calibration.session_rationale,
            }
    if request.predictive_warm:
        request_context["is_predictive_warm"] = True
        if request.warm_reason is not None:
            request_context["warm_reason"] = request.warm_reason
        if request.source_generation_id is not None:
            request_context["source_generation_id"] = request.source_generation_id

    if content_type == RequestedContentType.practice_problem:
        baseline_difficulty_band = select_practice_difficulty_band(profile, request)
        difficulty_band = apply_support_bias_to_difficulty_band(baseline_difficulty_band, mode_calibration)
        request_context["difficulty_band"] = difficulty_band.value
        request_context["mode_calibration_applied"] = difficulty_band != baseline_difficulty_band
        prompt_guidance = (
            "Create one practice problem with a clear success target, one concise worked cue, "
            f"and a brief answer-check instruction. Tune the problem to {difficulty_band.value} difficulty."
        )
    elif content_type == RequestedContentType.worked_example:
        baseline_fading = select_worked_example_fading(profile, request)
        fading = apply_support_bias_to_fading(baseline_fading, mode_calibration)
        request_context["fading_strategy"] = fading.value
        request_context["worked_steps_visible"] = _worked_steps_visible(fading)
        request_context["mode_calibration_applied"] = fading != baseline_fading
        prompt_guidance = _worked_example_guidance(fading)
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
) -> tuple[RequestedContentType, str, str | None]:
    if request.requested_content_type is not None:
        return request.requested_content_type, "explicit", None

    default_type = resolve_content_type(request)
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


def _worked_example_guidance(fading: WorkedExampleFading) -> str:
    if fading == WorkedExampleFading.full:
        return (
            "Generate one fully worked example with step-by-step reasoning, then ask the learner to explain why the final step works."
        )
    if fading == WorkedExampleFading.completion:
        return (
            "Generate one mostly worked example, then leave the final step for the learner to complete with a clear cue."
        )
    return (
        "Generate one concise example as a cue, then shift quickly to independent learner completion of a parallel step."
    )


def _worked_steps_visible(fading: WorkedExampleFading) -> int:
    mapping = {
        WorkedExampleFading.full: 3,
        WorkedExampleFading.completion: 2,
        WorkedExampleFading.independent: 1,
    }
    return mapping[fading]


def _average_target_mastery(profile: LearnerProfile, request: GenerationRequest) -> float:
    if request.target_kc_ids:
        values = [profile.knowledge_state.kc_mastery.get(kc_id, 0.0) for kc_id in request.target_kc_ids]
    elif request.target_lo_ids:
        values = [profile.knowledge_state.lo_mastery.get(lo_id, 0.0) for lo_id in request.target_lo_ids]
    else:
        values = list(profile.knowledge_state.kc_mastery.values()) or [0.5]
    return sum(values) / len(values)
