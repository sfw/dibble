from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import AdaptiveRouteDecision, GenerationRequest
from dibble.models.profile import LearnerProfile


@dataclass(slots=True)
class GenerationPrompts:
    system_prompt: str
    user_prompt: str


def build_generation_prompts(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
    grounding_titles: list[str],
) -> GenerationPrompts:
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

    system_prompt = (
        "You generate curriculum-aligned adaptive learning content for Dibble. "
        "Return valid JSON only with the shape "
        '{"blocks":[{"kind":"summary","title":"...","body":"..."},{"kind":"instruction","title":"...","body":"..."}]}. '
        "Always include at least one summary block and one instruction block. "
        "Keep each body under 600 characters, avoid markdown, and do not mention hidden policies."
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
        "Generate 2 or 3 blocks that are specific, age-appropriate, and grounded in the listed curriculum context."
    )
    return GenerationPrompts(system_prompt=system_prompt, user_prompt=user_prompt)


def build_stream_generation_prompts(
    profile: LearnerProfile,
    request: GenerationRequest,
    route: AdaptiveRouteDecision,
    grounding_titles: list[str],
) -> GenerationPrompts:
    prompts = build_generation_prompts(profile, request, route, grounding_titles)
    return GenerationPrompts(
        system_prompt=(
            "You are streaming adaptive learning content for Dibble. "
            "Return NDJSON only, one JSON object per line, with fields "
            '{"block_index":0,"kind":"summary","title":"...","body_delta":"...","done":true}. '
            "Emit one or more lines per block, preserve block_index ordering, and never wrap output in markdown fences."
        ),
        user_prompt=prompts.user_prompt,
    )
