from __future__ import annotations

from collections.abc import Iterator

from dibble.models.generation import AdaptiveRouteDecision, GeneratedBlock, GeneratedBlockChunk, GenerationRequest
from dibble.models.profile import LearnerProfile
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
        grounding_titles: list[str],
    ) -> list[GeneratedBlock]:
        focus = ", ".join(request.target_kc_ids or request.target_lo_ids or ["current lesson"])
        grounding_text = ", ".join(grounding_titles) if grounding_titles else "available curriculum context"
        prompt_fragment = request.learner_prompt or "Use a supportive, concise tone."

        return [
            GeneratedBlock(
                kind="summary",
                title="Learning focus",
                body=f"For grade {profile.grade_level}, focus on {focus}. Ground the explanation in {grounding_text}.",
            ),
            *self._intent_blocks(
                request=request,
                route=route,
                focus=focus,
                grounding_text=grounding_text,
                pace_preference=profile.learning_preferences.pace_preference.value,
                prompt_fragment=prompt_fragment,
            ),
        ]

    def stream_generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> Iterator[GeneratedBlockChunk]:
        return iter_block_chunks(self.generate(profile, request, route, grounding_titles))

    def _intent_blocks(
        self,
        *,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        focus: str,
        grounding_text: str,
        pace_preference: str,
        prompt_fragment: str,
    ) -> list[GeneratedBlock]:
        if request.intent.value == "practice":
            return [
                GeneratedBlock(
                    kind="practice",
                    title="Try a problem",
                    body=(
                        f"Solve one {focus} problem using {grounding_text}. "
                        "Show one worked cue before the learner completes the final step."
                    ),
                ),
                GeneratedBlock(
                    kind="instruction",
                    title="Check your thinking",
                    body=(
                        f"Provide {route.scaffolding_level}-scaffold support for {focus} using {grounding_text}. "
                        f"Honor the learner's pace preference of {pace_preference}. {prompt_fragment}"
                    ),
                ),
            ]

        return [
            GeneratedBlock(
                kind="instruction",
                title=f"{route.intervention_type.value.replace('_', ' ').title()} response",
                body=(
                    f"Provide {route.scaffolding_level}-scaffold support for {focus} using {grounding_text}. "
                    f"Honor the learner's pace preference of {pace_preference}. {prompt_fragment}"
                ),
            ),
        ]
