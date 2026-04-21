from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.generation import AdaptiveRouteDecision, GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import ModalityPlugins, RouterPlugin


@dataclass(frozen=True, slots=True)
class ModalityDirective:
    modality: str
    plugin_id: str
    composition_mode: str
    plugin_ids: tuple[str, ...] = ("text",)


@dataclass(frozen=True, slots=True)
class TextModalityDirective(ModalityDirective):
    modality: str = "text"
    plugin_id: str = "text"
    composition_mode: str = "single"
    plugin_ids: tuple[str, ...] = ("text",)


@dataclass(frozen=True, slots=True)
class ModalityRoutingPlan:
    route: AdaptiveRouteDecision
    pedagogical_move: str
    directive: ModalityDirective = field(default_factory=TextModalityDirective)
    theme_family: str | None = None
    locale: str | None = None
    accessibility_requirements: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModalityRoutingHarness:
    router: RouterPlugin
    modality_plugins: ModalityPlugins

    def plan(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
    ) -> ModalityRoutingPlan:
        route = self.router.route(profile, request)
        directive = self._directive_for(profile=profile, request=request, route=route)
        return ModalityRoutingPlan(
            route=route,
            pedagogical_move=route.intervention_type.value,
            directive=directive,
            theme_family=(
                profile.learning_preferences.example_domain_preferences[0]
                if profile.learning_preferences.example_domain_preferences
                else None
            ),
            accessibility_requirements=list(profile.accommodations),
            rationale=list(route.reasons)
            + [f"modality:{directive.plugin_id}"],
        )

    def _directive_for(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
    ) -> ModalityDirective:
        plugin_id = "text"
        curriculum_context = " ".join(request.curriculum_context).lower()
        learner_prompt = (request.learner_prompt or "").lower()
        requested_content_type = (
            request.requested_content_type.value
            if request.requested_content_type is not None
            else None
        )
        explicit_visual_signal = any(
            token in (curriculum_context + " " + learner_prompt)
            for token in ("diagram", "visual", "model", "graph", "chart")
        )
        explicit_narrative_signal = any(
            token in (curriculum_context + " " + learner_prompt)
            for token in ("narrative", "story", "storytelling", "tell a story")
        )
        if requested_content_type == "worked_example" and explicit_visual_signal:
            plugin_id = "diagram"
        elif (
            explicit_narrative_signal
            and requested_content_type
            in {"micro_explanation", "remedial_micro_module", None}
            and route.intervention_type.value in {"reteach", "step_back"}
            and profile.cognitive_load.total_load <= 0.82
        ):
            plugin_id = "narrative"
        plugin = self.modality_plugins.plugins.get(
            plugin_id, self.modality_plugins.get("text")
        )
        return ModalityDirective(
            modality=plugin.modality,
            plugin_id=plugin.plugin_id,
            composition_mode=plugin.composition_mode,
            plugin_ids=tuple(item.plugin_id for item in self.modality_plugins.chain_for(plugin.plugin_id)),
        )
