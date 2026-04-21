from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from dibble.models.generation import (
    GenerationRequest,
    GenerationResponse,
    GenerationStreamEvent,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import ModalityPlugins
from dibble.services.generation_engine import GenerationEngine
from dibble.services.harness.facades import PreparedAuthoringRequest
from dibble.services.harness.modality_routing import (
    ModalityRoutingHarness,
    ModalityRoutingPlan,
)
from dibble.services.harness.policy import HarnessAuthoringPolicy


@dataclass(frozen=True, slots=True)
class PreparedContentGeneration:
    profile: LearnerProfile
    request: GenerationRequest
    routing_plan: ModalityRoutingPlan
    authoring: PreparedAuthoringRequest


@dataclass(slots=True)
class ContentGenerationHarness:
    generation_engine: GenerationEngine
    modality_routing_harness: ModalityRoutingHarness
    modality_plugins: ModalityPlugins

    def prepare_generation(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        routing_plan: ModalityRoutingPlan | None = None,
    ) -> PreparedContentGeneration:
        resolved_plan = routing_plan or self.modality_routing_harness.plan(
            profile=profile,
            request=request,
        )
        authoring = self.generation_engine.harness.authoring.prepare_request_for(
            profile=profile,
            request=request,
            route=resolved_plan.route,
        )
        modality_plugin = self.modality_plugins.get(resolved_plan.directive.plugin_id)
        request_context = dict(authoring.policy.request_context)
        request_context["selected_modality"] = resolved_plan.directive.modality
        request_context["modality_plugin_id"] = resolved_plan.directive.plugin_id
        request_context["modality_composition_mode"] = (
            resolved_plan.directive.composition_mode
        )
        generation_constraints = dict(authoring.policy.generation_constraints)
        if resolved_plan.directive.plugin_id != "text":
            generation_constraints["modality_plugin_id"] = (
                resolved_plan.directive.plugin_id
            )
            generation_constraints["selected_modality"] = (
                resolved_plan.directive.modality
            )
        authoring = PreparedAuthoringRequest(
            policy=HarnessAuthoringPolicy(
                content_type=authoring.policy.content_type,
                prompt_guidance=authoring.policy.prompt_guidance,
                request_context=request_context,
                generation_constraints=generation_constraints,
            ),
            curriculum_request=modality_plugin.apply(
                request=authoring.curriculum_request,
                accessibility_requirements=resolved_plan.accessibility_requirements,
            ),
        )
        return PreparedContentGeneration(
            profile=profile,
            request=request,
            routing_plan=resolved_plan,
            authoring=authoring,
        )

    def generate(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        routing_plan: ModalityRoutingPlan | None = None,
    ) -> GenerationResponse:
        prepared = self.prepare_generation(
            profile=profile,
            request=request,
            routing_plan=routing_plan,
        )
        return self.generate_prepared(prepared)

    def generate_prepared(
        self, prepared: PreparedContentGeneration
    ) -> GenerationResponse:
        return self.generation_engine.generate_prepared(
            profile=prepared.profile,
            request=prepared.request,
            route=prepared.routing_plan.route,
            prepared_authoring=prepared.authoring,
        )

    def stream_generate_prepared(
        self, prepared: PreparedContentGeneration
    ) -> Iterator[GenerationStreamEvent]:
        return self.generation_engine.stream_generate_prepared(
            profile=prepared.profile,
            request=prepared.request,
            route=prepared.routing_plan.route,
            prepared_authoring=prepared.authoring,
        )
