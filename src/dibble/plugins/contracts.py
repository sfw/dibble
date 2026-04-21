from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

from dibble.models.generation import (
    AdaptiveRouteDecision,
    CurriculumContentRequest,
    GeneratedBlock,
    GeneratedBlockChunk,
    GenerationRequest,
    GroundingReference,
)
from dibble.models.profile import LearnerProfile


class ModalityPlugin(Protocol):
    plugin_id: str
    modality: str
    composition_mode: str

    def apply(
        self,
        *,
        request: CurriculumContentRequest,
        accessibility_requirements: list[str],
    ) -> CurriculumContentRequest: ...


class RouterPlugin(Protocol):
    def route(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> AdaptiveRouteDecision: ...


class RetrieverPlugin(Protocol):
    def retrieve(
        self,
        request: CurriculumContentRequest,
        limit: int = 3,
    ) -> list[GroundingReference]: ...


class ProviderPlugin(Protocol):
    def generate(
        self,
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> list[GeneratedBlock]: ...

    def stream_generate(
        self,
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> Iterator[GeneratedBlockChunk]: ...


class ValidatorPlugin(Protocol):
    def validate(
        self,
        blocks: list[GeneratedBlock],
        grounding: list[GroundingReference],
    ) -> list[str]: ...


@dataclass(slots=True)
class GenerationPlugins:
    router: RouterPlugin
    retriever: RetrieverPlugin
    provider: ProviderPlugin
    validator: ValidatorPlugin


@dataclass(slots=True)
class ModalityPlugins:
    plugins: dict[str, ModalityPlugin]

    def get(self, plugin_id: str) -> ModalityPlugin:
        return self.plugins[plugin_id]
