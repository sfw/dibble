from __future__ import annotations

from dibble.models.generation import DeliveryMode, GenerationRequest, GenerationResponse
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
