from __future__ import annotations

from dibble.models.generation import AdaptiveRouteDecision, GeneratedBlock, GenerationRequest
from dibble.models.profile import LearnerProfile


class MockLLMProvider:
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
            GeneratedBlock(
                kind="instruction",
                title=f"{route.intervention_type.value.replace('_', ' ').title()} response",
                body=(
                    f"Provide {route.scaffolding_level}-scaffold support for {focus}. "
                    f"Honor the learner's pace preference of {profile.learning_preferences.pace_preference.value}. "
                    f"{prompt_fragment}"
                ),
            ),
        ]
