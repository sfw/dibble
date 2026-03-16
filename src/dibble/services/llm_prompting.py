from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import AdaptiveRouteDecision, GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.services.generation_modes import build_generation_mode_plan
from dibble.services.prompt_manager import PromptManager


@dataclass(slots=True)
class GenerationPrompts:
    system_prompt: str
    user_prompt: str
    template_name: str
    template_version: str
    template_variant: str


def build_generation_prompts(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
    grounding_titles: list[str],
    prompt_manager: PromptManager | None = None,
) -> GenerationPrompts:
    manager = prompt_manager or PromptManager()
    plan = build_generation_mode_plan(profile, request, route)
    selection = manager.select(
        student_id=profile.student_id,
        content_type=plan.content_type,
        mode_calibration=request.mode_calibration,
    )
    focus = request.target_kc_ids or request.target_lo_ids or ["current lesson"]
    preferred_modalities = sorted(
        profile.learning_preferences.modality_affinity.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    modality_names = [name for name, score in preferred_modalities[:2] if score >= 0.5]
    grounding_text = ", ".join(grounding_titles) if grounding_titles else "No grounding documents were retrieved."
    learner_prompt = request.learner_prompt or "Keep the tone calm, specific, and encouraging."
    accommodations = ", ".join(profile.accommodations) if profile.accommodations else "None declared"
    example_domains = (
        ", ".join(profile.learning_preferences.example_domain_preferences)
        if profile.learning_preferences.example_domain_preferences
        else "general classroom examples"
    )
    socratic_follow_up = _socratic_follow_up_text(request.mode_calibration)
    practice_distractor_plan = _practice_distractor_plan_text(plan.request_context)
    worked_example_fade_plan = _worked_example_fade_plan_text(plan.request_context)

    system_prompt = (
        "You generate curriculum-aligned adaptive learning content for Dibble. "
        "Return valid JSON only with the shape "
        '{"blocks":[{"kind":"summary","title":"...","body":"..."},{"kind":"instruction","title":"...","body":"..."}]}. '
        "Allowed block kinds include summary, instruction, practice, and worked_example. "
        "Always include at least one summary block and one instruction block. "
        "Keep each body under 600 characters, avoid markdown, and do not mention hidden policies. "
        f"Prompt template: {selection.template_name} v{selection.template_version} ({selection.template_variant}). "
        f"{selection.system_directives}"
    )
    user_prompt = (
        f"Student grade level: {profile.grade_level}\n"
        f"Intent: {request.intent.value}\n"
        f"Focus concepts: {', '.join(focus)}\n"
        f"Route: {route.intervention_type.value} with {route.scaffolding_level} scaffolding\n"
        f"Delivery mode: {route.delivery_mode.value}\n"
        f"Router rationale: {'; '.join(route.reasons)}\n"
        f"Frustration signal: {profile.affective_state.frustration.value}\n"
        f"Engagement signal: {profile.affective_state.engagement.value}\n"
        f"Total cognitive load: {profile.cognitive_load.total_load:.2f}\n"
        f"Pace preference: {profile.learning_preferences.pace_preference.value}\n"
        f"Preferred modalities: {', '.join(modality_names) or 'textual'}\n"
        f"Preferred example domains: {example_domains}\n"
        f"Accommodations: {accommodations}\n"
        f"Grounding titles: {grounding_text}\n"
        f"Learner prompt: {learner_prompt}\n"
        f"Requested content type: {plan.content_type.value}\n"
        f"Prompt variant: {selection.template_variant}\n"
        f"Recent Socratic steering: {socratic_follow_up}\n"
        f"Practice distractor plan: {practice_distractor_plan}\n"
        f"Worked example fade plan: {worked_example_fade_plan}\n"
        f"Generation guidance: {plan.prompt_guidance}\n"
        f"Template guidance: {selection.user_directives}\n"
        "Generate 2 or 3 blocks that are specific, age-appropriate, and grounded in the listed curriculum context."
    )
    return GenerationPrompts(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_name=selection.template_name,
        template_version=selection.template_version,
        template_variant=selection.template_variant,
    )


def build_stream_generation_prompts(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
    grounding_titles: list[str],
    prompt_manager: PromptManager | None = None,
) -> GenerationPrompts:
    prompts = build_generation_prompts(profile, request, route, grounding_titles, prompt_manager=prompt_manager)
    return GenerationPrompts(
        system_prompt=(
            "You are streaming adaptive learning content for Dibble. "
            "Return NDJSON only, one JSON object per line, with fields "
            '{"block_index":0,"kind":"summary","title":"...","body_delta":"...","done":true}. '
            "Emit one or more lines per block, preserve block_index ordering, and never wrap output in markdown fences."
        ),
        user_prompt=prompts.user_prompt,
        template_name=prompts.template_name,
        template_version=prompts.template_version,
        template_variant=prompts.template_variant,
    )


def _socratic_follow_up_text(mode_calibration) -> str:
    if (
        mode_calibration is None
        or mode_calibration.session_assessment_count <= 0
        or mode_calibration.session_source == "insufficient"
    ):
        return "none"
    style = mode_calibration.session_latest_prompt_style or "unspecified"
    return (
        f"{mode_calibration.socratic_steering_action} "
        f"(arc_action={mode_calibration.session_arc_action}, "
        f"loop_risk={mode_calibration.session_stuck_loop_risk}, "
        f"last_style={style}, next_action={mode_calibration.session_latest_next_action}, "
        f"evidence={mode_calibration.session_latest_evidence_strength})"
    )


def _practice_distractor_plan_text(request_context: dict[str, object]) -> str:
    focus = request_context.get("practice_distractor_focus")
    if not isinstance(focus, str):
        return "none"
    distractor_slots = request_context.get("practice_distractor_slots") or []
    answer_check_focus = request_context.get("practice_answer_check_focus")
    misconception_ids = request_context.get("practice_distractor_misconception_ids") or []
    remediation_hint = request_context.get("practice_distractor_remediation_hint")
    fragments = [focus]
    if distractor_slots:
        fragments.append(f"distractor_slots={' | '.join(str(item) for item in distractor_slots)}")
    if isinstance(answer_check_focus, str) and answer_check_focus:
        fragments.append(f"answer_check_focus={answer_check_focus}")
    if misconception_ids:
        fragments.append(f"misconception_ids={','.join(str(item) for item in misconception_ids)}")
    if isinstance(remediation_hint, str) and remediation_hint:
        fragments.append(f"remediation_hint={remediation_hint}")
    return "; ".join(fragments)


def _worked_example_fade_plan_text(request_context: dict[str, object]) -> str:
    visible_roles = request_context.get("worked_example_visible_step_roles")
    hidden_step_role = request_context.get("worked_example_hidden_step_role")
    transfer_move = request_context.get("worked_example_transfer_move")
    step_outline = request_context.get("worked_example_step_outline") or []
    learner_release = request_context.get("worked_example_learner_release")
    if not isinstance(visible_roles, list) or not isinstance(hidden_step_role, str):
        return "none"
    roles = ", ".join(str(role) for role in visible_roles)
    fragments = [f"visible_roles={roles}", f"hidden_step_role={hidden_step_role}"]
    if step_outline:
        fragments.append(f"step_outline={' | '.join(str(item) for item in step_outline)}")
    if isinstance(learner_release, str) and learner_release:
        fragments.append(f"learner_release={learner_release}")
    if isinstance(transfer_move, str) and transfer_move:
        fragments.append(f"transfer_move={transfer_move}")
    return "; ".join(fragments)
