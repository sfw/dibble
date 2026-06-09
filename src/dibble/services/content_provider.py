from __future__ import annotations

from collections.abc import Iterator
from html import escape

from dibble.models.generation import (
    AdaptiveRouteDecision,
    CurriculumContentRequest,
    DeferredTextReveal,
    GeneratedBlock,
    GeneratedBlockChunk,
    GroundingReference,
    MultipleChoiceInteraction,
    MultipleChoiceOption,
)
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
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> list[GeneratedBlock]:
        focus = ", ".join(
            request.target_kc_ids or request.target_lo_ids or ["current lesson"]
        )
        grounding_summary = summarize_grounding_titles(grounding)
        grounding_excerpt = summarize_grounding_excerpts(
            grounding, max_items=1, max_chars=72
        )
        instruction_close = self._instruction_close(
            prompt_fragment=request.delivery_tone
        )

        return [
            GeneratedBlock(
                kind="summary",
                title="Learning focus",
                body=(
                    f"Grade {request.grade_level} focus: {focus}. "
                    f"Use {grounding_summary}. Cue: {grounding_excerpt}."
                ),
            ),
            *self._intent_blocks(
                request=request,
                route=route,
                focus=focus,
                grounding_excerpt=grounding_excerpt,
                grounding_summary=grounding_summary,
                instruction_close=instruction_close,
            ),
        ]

    def stream_generate(
        self,
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> Iterator[GeneratedBlockChunk]:
        return iter_block_chunks(self.generate(request, route, grounding))

    def _intent_blocks(
        self,
        *,
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        focus: str,
        grounding_excerpt: str,
        grounding_summary: str,
        instruction_close: str,
    ) -> list[GeneratedBlock]:
        modality_plugin_id = str(
            request.generation_constraints.get("modality_plugin_id", "text")
        )
        if request.content_type.value == "practice_problem":
            distractor_focus = str(
                request.generation_constraints.get(
                    "practice_distractor_focus", "a clear structural contrast"
                )
            )
            distractor_family = str(
                request.generation_constraints.get(
                    "practice_distractor_family", "single_structural_contrast"
                )
            )
            support_intensity = str(
                request.generation_constraints.get(
                    "practice_distractor_support_intensity", "moderate"
                )
            )
            distractor_blueprint = (
                request.generation_constraints.get("practice_distractor_blueprint") or []
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
                    kind="practice_problem",
                    title="Choose the next step",
                    body=(
                        f"Try one {request.generation_constraints.get('difficulty_band', 'on_grade')}-difficulty {focus} problem from {grounding_summary}. "
                        f"Watch for {distractor_focus}. Use the transfer move named in the cue."
                    ),
                    interaction=MultipleChoiceInteraction(
                        prompt=(
                            f"Which setup best preserves the right structure for {focus}?"
                        ),
                        options=[
                            MultipleChoiceOption(
                                option_id="A",
                                label="Option A",
                                body=(
                                    f"Tempting distractor around {distractor_focus}. "
                                    f"Use {distractor_family} at {support_intensity} intensity."
                                ),
                            ),
                            MultipleChoiceOption(
                                option_id="B",
                                label="Option B",
                                body=(
                                    f"Correct structural setup grounded in {grounding_excerpt}. "
                                    f"{blueprint_text}".strip()
                                ),
                            ),
                        ],
                        correct_option_id="B",
                        reveal=DeferredTextReveal(
                            prompt=(
                                "Explain why the correct setup preserves the intended structure."
                            ),
                            support=instruction_close,
                            placeholder="Name what the correct structure preserves.",
                        ),
                    ),
                ),
            ]

        if request.content_type.value == "worked_example":
            fading = str(request.generation_constraints.get("fading_strategy", "full"))
            release_stage = str(
                request.generation_constraints.get(
                    "worked_example_release_stage", "completion_then_justify"
                )
            )
            release_transition = str(
                request.generation_constraints.get(
                    "worked_example_release_transition", "worked step -> learner step"
                )
            )
            visible_roles = ", ".join(
                request.generation_constraints.get("worked_example_visible_step_roles", [])
            )
            hidden_step_role = str(
                request.generation_constraints.get(
                    "worked_example_hidden_step_role", "the next step"
                )
            )
            transfer_move = str(
                request.generation_constraints.get(
                    "worked_example_transfer_move", "a nearby application"
                )
            )
            transfer_plan = (
                request.generation_constraints.get("worked_example_transfer_plan") or {}
            )
            preserve = str(transfer_plan.get("preserve", "the same structure"))
            change = str(transfer_plan.get("change", transfer_move))
            learner_owned_move = str(
                transfer_plan.get("learner_owned_move", hidden_step_role)
            )
            blocks = [
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
            if modality_plugin_id == "diagram":
                blocks.insert(
                    1,
                    GeneratedBlock(
                        kind="visual_representation",
                        title=focus,
                        body=self._diagram_svg(
                            title=focus,
                            emphasis=preserve,
                            caption=grounding_excerpt,
                        ),
                    ),
                )
            return blocks

        if request.content_type.value == "assessment_probe":
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

        if modality_plugin_id == "narrative":
            return [
                GeneratedBlock(
                    kind="narrative",
                    title="A quick story",
                    body=(
                        f"A learner meets {focus} in a familiar moment. "
                        f"They notice {grounding_excerpt}. "
                        "The teacher names the pattern, slows down the tricky part, "
                        "and ends by asking the learner what stays the same."
                    ),
                ),
                GeneratedBlock(
                    kind="instruction",
                    title=f"{route.intervention_type.value.replace('_', ' ').title()} response",
                    body=(
                        f"Retell the key idea in your own words for {focus}. "
                        f"{instruction_close}"
                    ),
                ),
            ]
        if modality_plugin_id == "diagram":
            return [
                GeneratedBlock(
                    kind="visual_representation",
                    title=focus,
                    body=self._diagram_svg(
                        title=focus,
                        emphasis=grounding_summary,
                        caption=grounding_excerpt,
                    ),
                ),
                GeneratedBlock(
                    kind="instruction",
                    title=f"{route.intervention_type.value.replace('_', ' ').title()} response",
                    body=(
                        f"Name the visual pattern that matters for {focus}. "
                        f"Cue: {grounding_excerpt}. {instruction_close}"
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

    def _instruction_close(self, *, prompt_fragment: str | None) -> str:
        prompt_clause = (prompt_fragment or "use a supportive, concise tone").strip().rstrip(
            ".!?"
        )
        if not prompt_clause:
            return "Keep the instructional tone supportive and concise."
        prompt_clause = prompt_clause[0].lower() + prompt_clause[1:]
        return f"Keep the instructional tone supportive and concise, and {prompt_clause}."

    def _diagram_svg(self, *, title: str, emphasis: str, caption: str) -> str:
        safe_title = escape(title, quote=True)
        safe_emphasis = escape(emphasis, quote=True)
        safe_caption = escape(caption, quote=True)
        safe_label = f"{safe_title} target invariant diagram"
        safe_description = (
            f"{safe_title}: a target is connected to what stays true. "
            f"Caption: {safe_caption}"
        )
        return (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 420 180' role='img' "
            f"aria-label='{safe_label}' data-diagram-shape='target_invariant'>"
            f"<title>{safe_title}</title>"
            f"<desc>{safe_description}</desc>"
            "<rect x='12' y='24' width='180' height='28' rx='10' fill='#dbeafe' stroke='#2563eb'/>"
            "<rect x='228' y='24' width='180' height='28' rx='10' fill='#dcfce7' stroke='#15803d'/>"
            "<path d='M192 38 H228' stroke='#475569' stroke-width='3' marker-end='url(#arrow)'/>"
            "<rect x='48' y='96' width='324' height='44' rx='12' fill='#fff7ed' stroke='#ea580c'/>"
            "<text x='102' y='42' font-size='14' font-family='Arial' fill='#1e3a8a'>Target</text>"
            "<text x='258' y='42' font-size='14' font-family='Arial' fill='#166534'>What stays true</text>"
            f"<text x='50' y='122' font-size='14' font-family='Arial' fill='#9a3412'>{safe_emphasis}</text>"
            f"<text x='18' y='164' font-size='12' font-family='Arial' fill='#334155' data-role='caption'>{safe_caption}</text>"
            "<defs><marker id='arrow' markerWidth='10' markerHeight='10' refX='7' refY='3' orient='auto'>"
            "<path d='M0,0 L0,6 L9,3 z' fill='#475569'/></marker></defs>"
            "</svg>"
        )
