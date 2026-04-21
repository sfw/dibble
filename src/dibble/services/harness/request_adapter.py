from __future__ import annotations

from dibble.models.generation import (
    CurriculumContentRequest,
    GenerationModeCalibration,
    GenerationRequest,
    RequestedContentType,
)
from dibble.services.harness.policy import HarnessAuthoringPolicy


class CurriculumContentRequestAdapter:
    """Translates harness authoring policy into a provider-safe curriculum request."""

    def adapt(
        self,
        *,
        grade_level: str,
        request: GenerationRequest,
        policy: HarnessAuthoringPolicy,
    ) -> CurriculumContentRequest:
        return CurriculumContentRequest(
            grade_level=grade_level,
            intent=request.intent,
            content_type=policy.content_type,
            target_kc_ids=list(request.target_kc_ids),
            target_lo_ids=list(request.target_lo_ids),
            curriculum_context=list(request.curriculum_context),
            target_kc_hints=list(request.target_kc_hints),
            prompt_guidance=policy.prompt_guidance,
            generation_constraints=dict(policy.generation_constraints),
            adaptive_variant_hint=_adaptive_variant_hint(
                content_type=policy.content_type,
                mode_calibration=request.mode_calibration,
            ),
        )


def _adaptive_variant_hint(
    *,
    content_type: RequestedContentType,
    mode_calibration: GenerationModeCalibration | None,
) -> str | None:
    if mode_calibration is None:
        return None
    if content_type not in {
        RequestedContentType.micro_explanation,
        RequestedContentType.worked_example,
        RequestedContentType.practice_problem,
    }:
        return None
    if (
        mode_calibration.state_profile_source != "insufficient"
        and mode_calibration.state_profile_load_reliability >= 0.58
        and mode_calibration.state_profile_overload_risk >= 0.64
    ):
        return "guided_reflection"
    if (
        mode_calibration.trait_profile_source != "insufficient"
        and mode_calibration.trait_profile_trait_stability >= 0.72
        and mode_calibration.trait_profile_challenge_tolerance >= 0.66
        and content_type
        in {
            RequestedContentType.practice_problem,
            RequestedContentType.worked_example,
        }
    ):
        return "baseline"
    if (
        mode_calibration.socratic_profile_source != "insufficient"
        and mode_calibration.socratic_profile_confidence >= 0.56
    ):
        if mode_calibration.socratic_profile_signal in {
            "model_then_release",
            "clarify_then_check",
        }:
            return "guided_reflection"
        if mode_calibration.socratic_profile_signal in {
            "independent_check",
            "vary_representation",
        }:
            return "baseline"
    if (
        mode_calibration.session_source == "insufficient"
        or mode_calibration.session_confidence < 0.55
        or mode_calibration.session_assessment_count <= 0
    ):
        return None
    if mode_calibration.session_arc_action == "reprobe_new_angle":
        return "baseline"
    if mode_calibration.session_arc_action in {
        "model_repair",
        "restate_then_apply",
        "bridge_with_target",
    }:
        return "guided_reflection"
    if mode_calibration.socratic_steering_action in {
        "repair_then_model",
        "clarify_then_check",
        "restate_then_apply",
    }:
        return "guided_reflection"
    if mode_calibration.socratic_steering_action == "verify_transfer":
        return "baseline"
    return (
        "baseline"
        if mode_calibration.socratic_steering_action == "probe_from_new_angle"
        else None
    )
