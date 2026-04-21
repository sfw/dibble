from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import CurriculumContentRequest


@dataclass(frozen=True, slots=True)
class NarrativeModalityPlugin:
    plugin_id: str = "narrative"
    modality: str = "narrative"
    composition_mode: str = "single"

    def apply(
        self,
        *,
        request: CurriculumContentRequest,
        accessibility_requirements: list[str],
    ) -> CurriculumContentRequest:
        constraints = dict(request.generation_constraints)
        constraints["modality_plugin_id"] = self.plugin_id
        constraints["modality"] = self.modality
        constraints["narrative_scene_count"] = 2
        updated_guidance = (
            f"{request.prompt_guidance} Present the concept as a short, teacher-like story "
            "with two scenes and a reflective closing question."
        ).strip()
        return request.model_copy(
            update={
                "prompt_guidance": updated_guidance,
                "generation_constraints": constraints,
            }
        )


def build() -> NarrativeModalityPlugin:
    return NarrativeModalityPlugin()
