from __future__ import annotations

from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    CurriculumContentRequest,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.loader import build_modality_plugins
from dibble.services.content_provider import MockLLMProvider
from dibble.services.harness.modality_routing import ModalityRoutingHarness
from tests.support import build_profile


class _Router:
    def route(self, profile, request):
        return AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["test"],
        )


def test_modality_routing_harness_selects_diagram_for_visual_curriculum_context():
    plugins = build_modality_plugins()
    harness = ModalityRoutingHarness(router=_Router(), modality_plugins=plugins)
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), frustration="low", total_load=0.2)
    )

    plan = harness.plan(
        profile=profile,
        request=GenerationRequest(
            student_id=profile.student_id,
            intent=ContentIntent.explanation,
            requested_content_type=RequestedContentType.worked_example,
            curriculum_context=["fraction model"],
        ),
    )

    assert plan.directive.plugin_id == "diagram"


def test_mock_provider_emits_narrative_and_diagram_blocks_for_new_modalities():
    plugins = build_modality_plugins()
    provider = MockLLMProvider()
    route = _Router().route(None, None)

    narrative_request = plugins.get("narrative").apply(
        request=CurriculumContentRequest(
            grade_level="5",
            intent=ContentIntent.explanation,
            content_type=RequestedContentType.micro_explanation,
            target_kc_ids=["KC-1"],
        ),
        accessibility_requirements=[],
    )
    diagram_request = plugins.get("diagram").apply(
        request=CurriculumContentRequest(
            grade_level="5",
            intent=ContentIntent.explanation,
            content_type=RequestedContentType.worked_example,
            target_kc_ids=["KC-1"],
            curriculum_context=["fraction model"],
        ),
        accessibility_requirements=[],
    )

    narrative_blocks = provider.generate(narrative_request, route, [])
    diagram_blocks = provider.generate(diagram_request, route, [])

    assert any(block.kind == "narrative" for block in narrative_blocks)
    assert any(block.kind == "visual_representation" for block in diagram_blocks)
