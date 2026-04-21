from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import CurriculumContentRequest


@dataclass(frozen=True, slots=True)
class DiagramModalityPlugin:
    plugin_id: str = "diagram"
    modality: str = "diagram"
    composition_mode: str = "diagram_plus_text"

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
        updated_guidance = (
            f"{request.prompt_guidance} Include one simple, labeled visual representation "
            "using inline SVG plus a short caption that explains what the learner should notice."
        ).strip()
        return request.model_copy(
            update={
                "prompt_guidance": updated_guidance,
                "generation_constraints": constraints,
            }
        )


def build() -> DiagramModalityPlugin:
    return DiagramModalityPlugin()
