from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import CurriculumContentRequest
from dibble.plugins.contracts import ModalityCapabilityProfile


SUPPORTED_DIAGRAM_SHAPES = (
    "compare_invariant",
    "target_invariant",
    "step_relationship",
)


@dataclass(frozen=True, slots=True)
class DiagramModalityPlugin:
    plugin_id: str = "diagram"
    modality: str = "diagram"
    composition_mode: str = "diagram_plus_text"
    capabilities: ModalityCapabilityProfile = ModalityCapabilityProfile(
        primary_block_kinds=("visual_representation", "instruction"),
        required_artifact_types=("diagram", "text"),
        accessibility_metadata=("alt_text", "text_equivalent", "supports_screen_reader"),
        composed_with=("text",),
        verifier_tags=("diagram_accessibility", "composition"),
    )

    def apply(
        self,
        *,
        request: CurriculumContentRequest,
        accessibility_requirements: list[str],
    ) -> CurriculumContentRequest:
        constraints = dict(request.generation_constraints)
        constraints["modality_plugin_id"] = self.plugin_id
        constraints["modality"] = self.modality
        constraints["diagram_accessibility_requirements"] = list(
            accessibility_requirements
        )
        constraints["selected_modalities"] = ["diagram", "text"]
        constraints["supported_diagram_shapes"] = list(SUPPORTED_DIAGRAM_SHAPES)
        constraints["diagram_svg_contract"] = {
            "required_root_attributes": [
                "role=img",
                "aria-label",
                "data-diagram-shape",
            ],
            "required_children": ["title", "desc", "text[data-role=caption]"],
            "allowed_shapes": list(SUPPORTED_DIAGRAM_SHAPES),
            "allowed_elements": [
                "svg",
                "title",
                "desc",
                "rect",
                "line",
                "path",
                "text",
                "g",
                "defs",
                "marker",
            ],
        }
        updated_guidance = (
            f"{request.prompt_guidance} Include exactly one visual_representation block "
            "whose body is only inline SVG, plus one instruction block that explains "
            "what the learner should notice. Use only one supported diagram shape: "
            "compare_invariant for two side-by-side quantities with the same property, "
            "target_invariant for one target plus what stays true, or "
            "step_relationship for a short before-to-after relationship. The SVG root "
            "must include role='img', aria-label, viewBox, and data-diagram-shape set "
            "to one supported shape. Include child <title>, <desc>, and one visible "
            "<text data-role='caption'> caption. Use only svg/title/desc/rect/line/"
            "path/text/g/defs/marker elements; do not use style/script/image/"
            "foreignObject/animation/filter/use elements."
        ).strip()
        return request.model_copy(
            update={
                "prompt_guidance": updated_guidance,
                "generation_constraints": constraints,
            }
        )


def build() -> DiagramModalityPlugin:
    return DiagramModalityPlugin()
