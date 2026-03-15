from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dibble.models.generation import (
    AdaptiveRouteDecision,
    GeneratedBlock,
    GenerationRequest,
    GroundingReference,
)
from dibble.models.profile import LearnerProfile


class RouterPlugin(Protocol):
    def route(self, profile: LearnerProfile, request: GenerationRequest) -> AdaptiveRouteDecision: ...


class RetrieverPlugin(Protocol):
    def retrieve(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        limit: int = 3,
    ) -> list[GroundingReference]: ...


class ProviderPlugin(Protocol):
    def generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> list[GeneratedBlock]: ...


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
