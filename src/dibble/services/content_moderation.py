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
                "cheat": ("academic_integrity", "Request asked for help cheating or bypassing the learner's own work."),
                "do the test": ("academic_integrity", "Request asked the system to complete a test for the learner."),
                "just give the answer": ("academic_integrity", "Request asked for answer-only help instead of instruction."),
                "only the answer": ("academic_integrity", "Request asked for answer-only help instead of instruction."),
                "home address": ("privacy_risk", "Request asked for personal location or contact details."),
                "their address": ("privacy_risk", "Request asked for personal location or contact details."),
                "phone number": ("privacy_risk", "Request asked for personal contact details."),
                "diagnose": ("sensitive_advice", "Request asked for diagnosis-oriented content."),
                "kill": ("violence", "Request included violent wording outside normal classroom support."),
                "suicide": ("self_harm", "Request included self-harm wording."),
                "self-harm": ("self_harm", "Request included self-harm wording."),
                "nude": ("sexual_content", "Request included age-inappropriate sexual wording."),
            }
        if self.response_term_categories is None:
            self.response_term_categories = {
                "ignore safety": ("unsafe_instruction", "Generated content attempted to bypass safety guidance."),
                "shame": ("abusive_tone", "Generated content used shaming language."),
                "humiliate": ("abusive_tone", "Generated content used humiliating language."),
                "punish": ("abusive_tone", "Generated content suggested punitive treatment of the learner."),
                "cheat": ("academic_integrity", "Generated content encouraged cheating instead of learning."),
                "do the test": ("academic_integrity", "Generated content offered to complete a test for the learner."),
                "just give the answer": ("academic_integrity", "Generated content drifted into answer-only help."),
                "only the answer": ("academic_integrity", "Generated content drifted into answer-only help."),
                "home address": ("privacy_risk", "Generated content included personal address or location details."),
                "their address": ("privacy_risk", "Generated content included personal address or location details."),
                "phone number": ("privacy_risk", "Generated content included personal contact details."),
                "diagnose": ("sensitive_advice", "Generated content drifted into diagnosis-oriented language."),
                "kill": ("violence", "Generated content included violent wording."),
                "suicide": ("self_harm", "Generated content included self-harm wording."),
                "self-harm": ("self_harm", "Generated content included self-harm wording."),
                "weapon": ("violence", "Generated content included weapon-oriented wording."),
                "nude": ("sexual_content", "Generated content included age-inappropriate sexual wording."),
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
        coaching_note = self._fallback_coaching_note(moderation)
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
                    f"{coaching_note} Note: {reason_text}"
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
        matched_terms: list[str] = []
        for term, (category, reason) in term_categories.items():
            if term not in normalized:
                continue
            if term not in matched_terms:
                matched_terms.append(term)
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
            matched_terms=matched_terms,
        )

    def _fallback_coaching_note(self, moderation: ModerationResult) -> str:
        if "academic_integrity" in moderation.categories:
            return "Keep the help instructional: provide a hint, model, or worked example instead of doing the work for the learner."
        if "privacy_risk" in moderation.categories:
            return "Avoid asking for or repeating personal contact, location, or identity details."
        if "sexual_content" in moderation.categories:
            return "Keep the response classroom-appropriate and age-appropriate."
        if "violence" in moderation.categories or "self_harm" in moderation.categories:
            return "Keep the response calm, non-violent, and focused on safe classroom learning."
        return "Avoid unsafe or degrading wording."
