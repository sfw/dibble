from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import CurriculumContentRequest
from dibble.plugins.contracts import ModalityCapabilityProfile


@dataclass(frozen=True, slots=True)
class TextModalityPlugin:
    plugin_id: str = "text"
    modality: str = "text"
    composition_mode: str = "single"
    capabilities: ModalityCapabilityProfile = ModalityCapabilityProfile(
        primary_block_kinds=("instruction", "summary", "worked_example"),
        required_artifact_types=("text",),
        accessibility_metadata=("text_equivalent",),
        verifier_tags=("instruction_presence", "readability"),
    )

    def apply(
        self,
        *,
        request: CurriculumContentRequest,
        accessibility_requirements: list[str],
    ) -> CurriculumContentRequest:
        return request


def build() -> TextModalityPlugin:
    return TextModalityPlugin()
