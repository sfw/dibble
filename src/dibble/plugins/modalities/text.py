from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import CurriculumContentRequest


@dataclass(frozen=True, slots=True)
class TextModalityPlugin:
    plugin_id: str = "text"
    modality: str = "text"
    composition_mode: str = "single"

    def apply(
        self,
        *,
        request: CurriculumContentRequest,
        accessibility_requirements: list[str],
    ) -> CurriculumContentRequest:
        return request


def build() -> TextModalityPlugin:
    return TextModalityPlugin()
