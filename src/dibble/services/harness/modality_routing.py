from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.generation import AdaptiveRouteDecision, GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import RouterPlugin


@dataclass(frozen=True, slots=True)
class TextModalityDirective:
    modality: str = "text"
    plugin_id: str = "text"
    composition_mode: str = "single"


@dataclass(frozen=True, slots=True)
class ModalityRoutingPlan:
    route: AdaptiveRouteDecision
    pedagogical_move: str
    directive: TextModalityDirective = field(default_factory=TextModalityDirective)
    theme_family: str | None = None
    locale: str | None = None
    accessibility_requirements: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModalityRoutingHarness:
    router: RouterPlugin

    def plan(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
    ) -> ModalityRoutingPlan:
        route = self.router.route(profile, request)
        return ModalityRoutingPlan(
            route=route,
            pedagogical_move=route.intervention_type.value,
            theme_family=(
                profile.learning_preferences.example_domain_preferences[0]
                if profile.learning_preferences.example_domain_preferences
                else None
            ),
            accessibility_requirements=list(profile.accommodations),
            rationale=list(route.reasons),
        )
