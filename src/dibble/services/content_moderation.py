from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import GeneratedBlock, GenerationRequest, ModerationResult


@dataclass(slots=True)
class ContentModerationService:
    request_term_categories: dict[str, tuple[str, str]] | None = None
    response_term_categories: dict[str, tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        if self.request_term_categories is None:
            self.request_term_categories = {
                "ignore safety": ("unsafe_instruction", "Request asked to bypass safety guidance."),
                "shame": ("abusive_tone", "Request asked for shaming or degrading language."),
                "humiliate": ("abusive_tone", "Request asked for humiliating language."),
                "diagnose": ("sensitive_advice", "Request asked for diagnosis-oriented content."),
                "kill": ("violence", "Request included violent wording outside normal classroom support."),
                "suicide": ("self_harm", "Request included self-harm wording."),
                "self-harm": ("self_harm", "Request included self-harm wording."),
            }
        if self.response_term_categories is None:
            self.response_term_categories = {
                "ignore safety": ("unsafe_instruction", "Generated content attempted to bypass safety guidance."),
                "shame": ("abusive_tone", "Generated content used shaming language."),
                "humiliate": ("abusive_tone", "Generated content used humiliating language."),
                "punish": ("abusive_tone", "Generated content suggested punitive treatment of the learner."),
                "diagnose": ("sensitive_advice", "Generated content drifted into diagnosis-oriented language."),
                "kill": ("violence", "Generated content included violent wording."),
                "suicide": ("self_harm", "Generated content included self-harm wording."),
                "self-harm": ("self_harm", "Generated content included self-harm wording."),
                "weapon": ("violence", "Generated content included weapon-oriented wording."),
            }

    def moderate_request(self, request: GenerationRequest) -> ModerationResult:
        text = " ".join(
            part
            for part in [
                request.learner_prompt or "",
                " ".join(request.curriculum_context),
            ]
            if part
        )
        return self._moderate_text(text=text, stage="request", term_categories=self.request_term_categories or {})

    def moderate_blocks(self, blocks: list[GeneratedBlock]) -> ModerationResult:
        text = " ".join(f"{block.title} {block.body}" for block in blocks)
        return self._moderate_text(text=text, stage="response", term_categories=self.response_term_categories or {})

    def build_fallback_blocks(
        self,
        *,
        request: GenerationRequest,
        grounding_titles: list[str],
        moderation: ModerationResult,
    ) -> list[GeneratedBlock]:
        focus = ", ".join(request.target_kc_ids or request.target_lo_ids or ["the current lesson"])
        grounding_text = ", ".join(grounding_titles) if grounding_titles else "the current curriculum context"
        categories = ", ".join(moderation.categories) if moderation.categories else "safety review"
        reason_text = moderation.reasons[0] if moderation.reasons else "The request or generated draft needs a safer reframe."
        return [
            GeneratedBlock(
                kind="summary",
                title="Safe learning reset",
                body=(
                    f"Let's keep the next step focused on {focus} and grounded in {grounding_text}. "
                    f"A moderation check paused the previous draft for {categories}."
                ),
            ),
            GeneratedBlock(
                kind="instruction",
                title="Teacher-safe next step",
                body=(
                    f"Reframe the lesson as a calm, supportive explanation or practice step for {focus}. "
                    f"Avoid unsafe or degrading wording. Note: {reason_text}"
                ),
            ),
        ]

    def _moderate_text(
        self,
        *,
        text: str,
        stage: str,
        term_categories: dict[str, tuple[str, str]],
    ) -> ModerationResult:
        normalized = text.lower()
        categories: list[str] = []
        reasons: list[str] = []
        for term, (category, reason) in term_categories.items():
            if term not in normalized:
                continue
            if category not in categories:
                categories.append(category)
            if reason not in reasons:
                reasons.append(reason)
        if not categories:
            return ModerationResult()
        return ModerationResult(
            status="flagged",
            stage=stage,
            categories=categories,
            reasons=reasons,
        )
