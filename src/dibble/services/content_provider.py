from __future__ import annotations

from collections.abc import Iterator

from dibble.models.generation import (
    AdaptiveRouteDecision,
    GeneratedBlock,
    GeneratedBlockChunk,
    GenerationRequest,
    GroundingReference,
)
from dibble.models.profile import LearnerProfile
from dibble.services.generation_modes import build_generation_mode_plan
from dibble.services.grounding_context import (
    summarize_grounding_excerpts,
    summarize_grounding_titles,
)
from dibble.services.streaming import iter_block_chunks


class MockLLMProvider:
    def __init__(self) -> None:
        self.last_used_descriptor = {
            "provider_name": "mock",
            "model_used": "mock-deterministic",
        }

    def generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> list[GeneratedBlock]:
        plan = build_generation_mode_plan(profile, request, route)
        focus = ", ".join(
            request.target_kc_ids or request.target_lo_ids or ["current lesson"]
        )
        grounding_summary = summarize_grounding_titles(grounding)
        grounding_excerpt = summarize_grounding_excerpts(
            grounding, max_items=1, max_chars=72
        )
        prompt_fragment = request.learner_prompt or "Use a supportive, concise tone."
        instruction_close = self._instruction_close(
            pace_preference=profile.learning_preferences.pace_preference.value,
            prompt_fragment=prompt_fragment,
        )

        return [
            GeneratedBlock(
                kind="summary",
                title="Learning focus",
                body=(
                    f"Grade {profile.grade_level} focus: {focus}. "
                    f"Use {grounding_summary}. Cue: {grounding_excerpt}."
                ),
            ),
            *self._intent_blocks(
                request=request,
                route=route,
                plan=plan,
                focus=focus,
                grounding_excerpt=grounding_excerpt,
                grounding_summary=grounding_summary,
                instruction_close=instruction_close,
            ),
        ]

    def stream_generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> Iterator[GeneratedBlockChunk]:
        return iter_block_chunks(self.generate(profile, request, route, grounding))

    def _intent_blocks(
        self,
        *,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        plan,
        focus: str,
        grounding_excerpt: str,
        grounding_summary: str,
        instruction_close: str,
    ) -> list[GeneratedBlock]:
        if plan.content_type.value == "practice_problem":
            distractor_focus = str(
                plan.request_context.get(
                    "practice_distractor_focus", "a clear structural contrast"
                )
            )
            distractor_family = str(
                plan.request_context.get(
                    "practice_distractor_family", "single_structural_contrast"
                )
            )
            support_intensity = str(
                plan.request_context.get(
                    "practice_distractor_support_intensity", "moderate"
                )
            )
            distractor_blueprint = (
                plan.request_context.get("practice_distractor_blueprint") or []
            )
            blueprint_entry = (
                distractor_blueprint[0]
                if isinstance(distractor_blueprint, list) and distractor_blueprint
                else {}
            )
            blueprint_text = (
                f"Lead with {blueprint_entry.get('slot', 'main_contrast')} and repair via {blueprint_entry.get('repair_cue', 'the corrected move')}."
                if isinstance(blueprint_entry, dict)
                else ""
            )
            return [
                GeneratedBlock(
                    kind="practice",
                    title="Try a problem",
                    body=(
                        f"Try one {plan.request_context['difficulty_band']}-difficulty {focus} problem from {grounding_summary}. "
                        f"Cue: {grounding_excerpt}. Use {distractor_family} distractors at {support_intensity} intensity around {distractor_focus}. "
                        f"{blueprint_text}"
                    ),
                ),
                GeneratedBlock(
                    kind="instruction",
                    title="Check your thinking",
                    body=(
                        f"Give {route.scaffolding_level} support for {focus}. "
                        f"Cue: {grounding_excerpt}. "
                        f"{instruction_close}"
                    ),
                ),
            ]

        if plan.content_type.value == "worked_example":
            fading = str(plan.request_context["fading_strategy"])
            release_stage = str(
                plan.request_context.get(
                    "worked_example_release_stage", "completion_then_justify"
                )
            )
            release_transition = str(
                plan.request_context.get(
                    "worked_example_release_transition", "worked step -> learner step"
                )
            )
            visible_roles = ", ".join(
                plan.request_context.get("worked_example_visible_step_roles", [])
            )
            hidden_step_role = str(
                plan.request_context.get(
                    "worked_example_hidden_step_role", "the next step"
                )
            )
            transfer_move = str(
                plan.request_context.get(
                    "worked_example_transfer_move", "a nearby application"
                )
            )
            transfer_plan = (
                plan.request_context.get("worked_example_transfer_plan") or {}
            )
            preserve = str(transfer_plan.get("preserve", "the same structure"))
            change = str(transfer_plan.get("change", transfer_move))
            learner_owned_move = str(
                transfer_plan.get("learner_owned_move", hidden_step_role)
            )
            return [
                GeneratedBlock(
                    kind="worked_example",
                    title="See it solved",
                    body=(
                        f"Model {focus} with {grounding_summary}. Cue: {grounding_excerpt}. "
                        f"Use {fading} fading at {release_stage}. Visible roles: {visible_roles}. "
                        f"Transition: {release_transition}. Preserve: {preserve}. Change: {change}."
                    ),
                ),
                GeneratedBlock(
                    kind="instruction",
                    title="Now you try",
                    body=(
                        f"Let the learner do {learner_owned_move}. "
                        f"Stay aligned to {grounding_summary}. "
                        f"{instruction_close}"
                    ),
                ),
            ]

        if plan.content_type.value == "assessment_probe":
            return [
                GeneratedBlock(
                    kind="instruction",
                    title="Think aloud",
                    body=(
                        f"In your own words, how would you explain {focus} using {grounding_summary}? "
                        f"Cue: {grounding_excerpt}. "
                        "What evidence supports your thinking?"
                    ),
                ),
            ]

        return [
            GeneratedBlock(
                kind="instruction",
                title=f"{route.intervention_type.value.replace('_', ' ').title()} response",
                body=(
                    f"Give {route.scaffolding_level} support for {focus}. "
                    f"Cue: {grounding_excerpt}. "
                    f"{instruction_close}"
                ),
            ),
        ]

    def _instruction_close(self, *, pace_preference: str, prompt_fragment: str) -> str:
        prompt_clause = prompt_fragment.strip().rstrip(".!?")
        if not prompt_clause:
            return f"Honor the learner's pace preference of {pace_preference}."
        prompt_clause = prompt_clause[0].lower() + prompt_clause[1:]
        return f"Honor the learner's pace preference of {pace_preference} and {prompt_clause}."
