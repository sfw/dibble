from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import (
    GeneratedBlock,
    GenerationRequest,
    GroundingReference,
    ModerationMatch,
    ModerationResult,
)
from dibble.services.grounding_context import summarize_grounding_titles


@dataclass(frozen=True, slots=True)
class ModerationRule:
    category: str
    reason: str
    severity: str = "block"


@dataclass(slots=True)
class ContentModerationService:
    request_term_categories: dict[str, ModerationRule] | None = None
    response_term_categories: dict[str, ModerationRule] | None = None

    def __post_init__(self) -> None:
        if self.request_term_categories is None:
            self.request_term_categories = {
                "ignore safety": ModerationRule("unsafe_instruction", "Request asked to bypass safety guidance."),
                "bypass safety": ModerationRule("unsafe_instruction", "Request asked to bypass safety guidance."),
                "shame": ModerationRule("abusive_tone", "Request asked for shaming or degrading language."),
                "humiliate": ModerationRule("abusive_tone", "Request asked for humiliating language."),
                "idiot": ModerationRule("abusive_tone", "Request used insulting language toward the learner."),
                "cheat": ModerationRule("academic_integrity", "Request asked for help cheating or bypassing the learner's own work."),
                "do the test": ModerationRule("academic_integrity", "Request asked the system to complete a test for the learner."),
                "just give the answer": ModerationRule("academic_integrity", "Request asked for answer-only help instead of instruction."),
                "only the answer": ModerationRule("academic_integrity", "Request asked for answer-only help instead of instruction."),
                "answer key": ModerationRule("academic_integrity", "Request asked for answer-key style help."),
                "submit this": ModerationRule("academic_integrity", "Request asked the system to submit or finish work for the learner."),
                "home address": ModerationRule("privacy_risk", "Request asked for personal location or contact details."),
                "their address": ModerationRule("privacy_risk", "Request asked for personal location or contact details."),
                "phone number": ModerationRule("privacy_risk", "Request asked for personal contact details."),
                "email address": ModerationRule("privacy_risk", "Request asked for personal contact details."),
                "password": ModerationRule("privacy_risk", "Request asked for credential or account details."),
                "social security": ModerationRule("privacy_risk", "Request asked for highly sensitive identity details."),
                "diagnose": ModerationRule("sensitive_advice", "Request asked for diagnosis-oriented content."),
                "therapy": ModerationRule("sensitive_advice", "Request asked for therapy-style advice beyond classroom support."),
                "kill": ModerationRule("violence", "Request included violent wording outside normal classroom support."),
                "weapon": ModerationRule("violence", "Request included weapon-oriented wording."),
                "suicide": ModerationRule("self_harm", "Request included self-harm wording."),
                "self-harm": ModerationRule("self_harm", "Request included self-harm wording."),
                "cut myself": ModerationRule("self_harm", "Request included self-harm wording."),
                "nude": ModerationRule("sexual_content", "Request included age-inappropriate sexual wording."),
            }
        if self.response_term_categories is None:
            self.response_term_categories = {
                "ignore safety": ModerationRule("unsafe_instruction", "Generated content attempted to bypass safety guidance."),
                "bypass safety": ModerationRule("unsafe_instruction", "Generated content attempted to bypass safety guidance."),
                "shame": ModerationRule("abusive_tone", "Generated content used shaming language."),
                "humiliate": ModerationRule("abusive_tone", "Generated content used humiliating language."),
                "punish": ModerationRule("abusive_tone", "Generated content suggested punitive treatment of the learner."),
                "idiot": ModerationRule("abusive_tone", "Generated content used insulting language."),
                "cheat": ModerationRule("academic_integrity", "Generated content encouraged cheating instead of learning."),
                "do the test": ModerationRule("academic_integrity", "Generated content offered to complete a test for the learner."),
                "just give the answer": ModerationRule("academic_integrity", "Generated content drifted into answer-only help."),
                "only the answer": ModerationRule("academic_integrity", "Generated content drifted into answer-only help."),
                "answer key": ModerationRule("academic_integrity", "Generated content drifted into answer-key style help."),
                "home address": ModerationRule("privacy_risk", "Generated content included personal address or location details."),
                "their address": ModerationRule("privacy_risk", "Generated content included personal address or location details."),
                "phone number": ModerationRule("privacy_risk", "Generated content included personal contact details."),
                "email address": ModerationRule("privacy_risk", "Generated content included personal contact details."),
                "password": ModerationRule("privacy_risk", "Generated content included credential-oriented details."),
                "social security": ModerationRule("privacy_risk", "Generated content included highly sensitive identity details."),
                "diagnose": ModerationRule("sensitive_advice", "Generated content drifted into diagnosis-oriented language."),
                "therapy": ModerationRule("sensitive_advice", "Generated content drifted into therapy-style advice."),
                "kill": ModerationRule("violence", "Generated content included violent wording."),
                "suicide": ModerationRule("self_harm", "Generated content included self-harm wording."),
                "self-harm": ModerationRule("self_harm", "Generated content included self-harm wording."),
                "weapon": ModerationRule("violence", "Generated content included weapon-oriented wording."),
                "cut myself": ModerationRule("self_harm", "Generated content included self-harm wording."),
                "nude": ModerationRule("sexual_content", "Generated content included age-inappropriate sexual wording."),
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
        grounding: list[GroundingReference],
        moderation: ModerationResult,
    ) -> list[GeneratedBlock]:
        focus = ", ".join(request.target_kc_ids or request.target_lo_ids or ["the current lesson"])
        grounding_text = summarize_grounding_titles(grounding)
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
        term_categories: dict[str, ModerationRule],
    ) -> ModerationResult:
        normalized = text.lower()
        categories: list[str] = []
        reasons: list[str] = []
        matched_terms: list[str] = []
        category_terms: dict[str, list[str]] = {}
        category_reasons: dict[str, str] = {}
        category_severities: dict[str, str] = {}
        for term, rule in term_categories.items():
            if term not in normalized:
                continue
            if term not in matched_terms:
                matched_terms.append(term)
            category_terms.setdefault(rule.category, []).append(term)
            category_reasons.setdefault(rule.category, rule.reason)
            category_severities.setdefault(rule.category, rule.severity)
            if rule.category not in categories:
                categories.append(rule.category)
            if rule.reason not in reasons:
                reasons.append(rule.reason)
        if not categories:
            return ModerationResult()
        severity = "block" if any(value == "block" for value in category_severities.values()) else "review"
        matches = [
            ModerationMatch(
                category=category,
                matched_terms=sorted(category_terms.get(category, [])),
                reason=category_reasons[category],
                severity=category_severities.get(category, severity),
            )
            for category in categories
        ]
        audit_message = (
            f"{stage.title()} moderation flagged {', '.join(categories)} and replaced the content with a teacher-safe fallback."
        )
        return ModerationResult(
            status="flagged",
            stage=stage,
            severity=severity,
            categories=categories,
            reasons=reasons,
            matched_terms=sorted(matched_terms),
            matches=matches,
            blocked=severity == "block",
            audit_message=audit_message,
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
