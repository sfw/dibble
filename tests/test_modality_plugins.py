from __future__ import annotations

from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    CurriculumContentRequest,
    DeliveryMode,
    GenerationRequest,
    GroundingReference,
    InterventionType,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.loader import build_modality_plugins
from dibble.services.content_provider import MockLLMProvider
from dibble.services.harness.modality_routing import ModalityRoutingHarness
from dibble.services.llm_prompting import build_generation_prompts
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
    diagram_block = next(
        block for block in diagram_blocks if block.kind == "visual_representation"
    )
    assert "data-diagram-shape='target_invariant'" in diagram_block.body
    assert "<title>KC-1</title>" in diagram_block.body
    assert "data-role='caption'" in diagram_block.body


def test_diagram_plugin_constrains_supported_shapes_and_svg_contract():
    plugins = build_modality_plugins()

    diagram_request = plugins.get("diagram").apply(
        request=CurriculumContentRequest(
            grade_level="5",
            intent=ContentIntent.explanation,
            content_type=RequestedContentType.worked_example,
            target_kc_ids=["KC-1"],
            curriculum_context=["fraction model"],
        ),
        accessibility_requirements=["screen reader"],
    )

    assert diagram_request.generation_constraints["supported_diagram_shapes"] == [
        "compare_invariant",
        "target_invariant",
        "step_relationship",
    ]
    assert (
        diagram_request.generation_constraints["diagram_svg_contract"][
            "required_children"
        ]
        == ["title", "desc", "text[data-role=caption]"]
    )
    assert "data-diagram-shape" in diagram_request.prompt_guidance
    assert "foreignObject" in diagram_request.prompt_guidance


def test_diagram_prompt_contract_allows_only_visual_and_instruction_blocks():
    plugins = build_modality_plugins()
    route = _Router().route(None, None)
    diagram_request = plugins.get("diagram").apply(
        request=CurriculumContentRequest(
            grade_level="5",
            intent=ContentIntent.explanation,
            content_type=RequestedContentType.micro_explanation,
            target_kc_ids=["KC-1"],
            curriculum_context=["fraction model"],
        ),
        accessibility_requirements=[],
    )

    prompts = build_generation_prompts(
        diagram_request,
        route,
        [
            GroundingReference(
                outcome_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=2.0,
                matched_terms=["equivalent fractions"],
            )
        ],
    )

    assert "visual_representation and instruction" in prompts.system_prompt
    assert "summary, instruction, practice_problem" not in prompts.system_prompt
    assert "supported diagram contract" in prompts.system_prompt


def test_diagram_prompt_contract_wins_for_practice_problem_requests():
    plugins = build_modality_plugins()
    route = _Router().route(None, None)
    diagram_request = plugins.get("diagram").apply(
        request=CurriculumContentRequest(
            grade_level="5",
            intent=ContentIntent.practice,
            content_type=RequestedContentType.practice_problem,
            target_kc_ids=["KC-1"],
            curriculum_context=["fraction model"],
        ),
        accessibility_requirements=[],
    )

    prompts = build_generation_prompts(
        diagram_request,
        route,
        [
            GroundingReference(
                outcome_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=2.0,
                matched_terms=["equivalent fractions"],
            )
        ],
    )

    assert "visual_representation and instruction" in prompts.system_prompt
    assert '"kind":"practice_problem"' not in prompts.system_prompt
    assert "interaction.options" not in prompts.system_prompt
    assert "Generate exactly 2 blocks" in prompts.user_prompt


def test_modality_plugins_advertise_capabilities_and_composition_chain():
    plugins = build_modality_plugins()

    diagram = plugins.get("diagram")
    narrative = plugins.get("narrative")
    chain = plugins.chain_for("diagram")

    assert diagram.capabilities.required_artifact_types == ("diagram", "text")
    assert diagram.capabilities.composed_with == ("text",)
    assert narrative.capabilities.verifier_tags == (
        "narrative_coherence",
        "composition",
    )
    assert [plugin.plugin_id for plugin in chain] == ["diagram", "text"]
