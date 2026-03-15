from __future__ import annotations

from collections.abc import Iterator

from dibble.models.generation import (
    DeliveryMode,
    GeneratedBlock,
    GenerationRequest,
    GenerationResponse,
    GenerationStreamEvent,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import ProviderPlugin, RetrieverPlugin, RouterPlugin, ValidatorPlugin


class GenerationEngine:
    def __init__(
        self,
        retriever: RetrieverPlugin,
        router: RouterPlugin,
        provider: ProviderPlugin,
        validator: ValidatorPlugin,
    ) -> None:
        self.retriever = retriever
        self.router = router
        self.provider = provider
        self.validator = validator

    def generate(self, profile: LearnerProfile, request: GenerationRequest) -> GenerationResponse:
        grounding = self.retriever.retrieve(profile, request)
        route = self.router.route(profile, request)
        blocks = self.provider.generate(profile, request, route, [item.title for item in grounding])
        return self._build_response(profile, request, route, grounding, blocks)

    def stream_generate(self, profile: LearnerProfile, request: GenerationRequest) -> Iterator[GenerationStreamEvent]:
        grounding = self.retriever.retrieve(profile, request)
        route = self.router.route(profile, request)
        yield GenerationStreamEvent(
            event="start",
            student_id=profile.student_id,
            route=route,
            grounding=grounding,
        )

        block_buffers: dict[int, GeneratedBlock] = {}
        for chunk in self.provider.stream_generate(profile, request, route, [item.title for item in grounding]):
            current = block_buffers.get(chunk.block_index)
            if current is None:
                current = GeneratedBlock(kind=chunk.kind, title=chunk.title, body="")
                block_buffers[chunk.block_index] = current

            current.body += chunk.body_delta
            yield GenerationStreamEvent(
                event="delta",
                student_id=profile.student_id,
                chunk=chunk,
            )

        blocks = [block_buffers[index] for index in sorted(block_buffers)]
        response = self._build_response(profile, request, route, grounding, blocks)
        yield GenerationStreamEvent(
            event="complete",
            student_id=profile.student_id,
            route=response.route,
            grounding=response.grounding,
            validation_issues=response.validation_issues,
            response=response,
        )

    def _build_response(self, profile: LearnerProfile, request: GenerationRequest, route, grounding, blocks: list[GeneratedBlock]) -> GenerationResponse:
        validation_issues = self.validator.validate(blocks, grounding)

        if validation_issues and not grounding:
            route.delivery_mode = DeliveryMode.static_fallback

        return GenerationResponse(
            student_id=profile.student_id,
            route=route,
            blocks=blocks,
            curriculum_context=request.curriculum_context,
            grounding=grounding,
            safety_notes=[
                "Generation is a scaffolded draft and should be validated against curriculum standards before student delivery.",
                "Profiles should avoid sensitive inference beyond declared accommodations and observable learning signals.",
            ],
            validation_issues=validation_issues,
        )
