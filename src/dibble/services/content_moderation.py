from __future__ import annotations

from dataclasses import dataclass
import re

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
            self.request_term_categories = self._build_default_request_terms()
        if self.response_term_categories is None:
            self.response_term_categories = self._build_default_response_terms()

    def _build_default_request_terms(self) -> dict[str, ModerationRule]:
        return self._build_term_categories(
            (
                (
                    ModerationRule(
                        "unsafe_instruction", "Request asked to bypass safety guidance."
                    ),
                    ["ignore safety", "bypass safety", "skip the safety rules"],
                ),
                (
                    ModerationRule(
                        "abusive_tone",
                        "Request asked for shaming or degrading language.",
                    ),
                    [
                        "shame",
                        "shaming",
                        "humiliate",
                        "embarrass",
                        "mock",
                        "idiot",
                        "stupid",
                    ],
                ),
                (
                    ModerationRule(
                        "academic_integrity",
                        "Request asked for help cheating or bypassing the learner's own work.",
                    ),
                    [
                        "cheat",
                        "do the test",
                        "take the test for me",
                        "just give the answer",
                        "just the answer",
                        "only the answer",
                        "answer key",
                        "submit this",
                        "solve it for me",
                        "do my homework",
                        "write my essay",
                        "complete this for me",
                    ],
                ),
                (
                    ModerationRule(
                        "privacy_risk",
                        "Request asked for personal or credential details.",
                    ),
                    [
                        "home address",
                        "their address",
                        "mailing address",
                        "phone number",
                        "email address",
                        "contact information",
                        "contact info",
                        "their full name",
                        "their last name",
                        "password",
                        "login",
                        "username",
                        "social security",
                        "credit card",
                    ],
                ),
                (
                    ModerationRule(
                        "sensitive_advice",
                        "Request asked for diagnosis-oriented or therapeutic advice.",
                    ),
                    ["diagnose", "diagnosis", "therapy", "therapist", "prescribe"],
                ),
                (
                    ModerationRule(
                        "violence",
                        "Request included violent or weapon-oriented wording.",
                    ),
                    ["kill", "weapon", "gun", "knife", "stab", "bomb"],
                ),
                (
                    ModerationRule("self_harm", "Request included self-harm wording."),
                    [
                        "suicide",
                        "suicidal",
                        "self-harm",
                        "self harm",
                        "cut myself",
                        "hurt myself",
                        "end my life",
                    ],
                ),
                (
                    ModerationRule(
                        "sexual_content",
                        "Request included age-inappropriate sexual wording.",
                    ),
                    ["nude", "naked", "porn", "sexual content", "sexually explicit"],
                ),
                (
                    ModerationRule(
                        "bias_stereotype",
                        "Request asked for biased or stereotype-based framing.",
                    ),
                    [
                        "girls are bad at math",
                        "boys are better at math",
                        "because she is a girl",
                        "because he is a boy",
                    ],
                ),
                (
                    ModerationRule(
                        "substance_use",
                        "Request included age-inappropriate substance-use wording.",
                    ),
                    ["beer", "vodka", "get drunk", "get high", "marijuana"],
                ),
            )
        )

    def _build_default_response_terms(self) -> dict[str, ModerationRule]:
        return self._build_term_categories(
            (
                (
                    ModerationRule(
                        "unsafe_instruction",
                        "Generated content attempted to bypass safety guidance.",
                    ),
                    ["ignore safety", "bypass safety", "skip the safety rules"],
                ),
                (
                    ModerationRule(
                        "abusive_tone",
                        "Generated content used shaming or degrading language.",
                    ),
                    [
                        "shame",
                        "shaming",
                        "humiliate",
                        "punish",
                        "embarrass",
                        "mock",
                        "idiot",
                        "stupid",
                    ],
                ),
                (
                    ModerationRule(
                        "academic_integrity",
                        "Generated content encouraged cheating instead of learning.",
                    ),
                    [
                        "cheat",
                        "do the test",
                        "take the test for me",
                        "just give the answer",
                        "just the answer",
                        "only the answer",
                        "answer key",
                        "solve it for me",
                        "complete this for me",
                    ],
                ),
                (
                    ModerationRule(
                        "privacy_risk",
                        "Generated content included personal or credential details.",
                    ),
                    [
                        "home address",
                        "their address",
                        "mailing address",
                        "phone number",
                        "email address",
                        "contact information",
                        "contact info",
                        "their full name",
                        "their last name",
                        "password",
                        "login",
                        "username",
                        "social security",
                        "credit card",
                    ],
                ),
                (
                    ModerationRule(
                        "sensitive_advice",
                        "Generated content drifted into diagnosis-oriented or therapeutic advice.",
                    ),
                    ["diagnose", "diagnosis", "therapy", "therapist", "prescribe"],
                ),
                (
                    ModerationRule(
                        "violence",
                        "Generated content included violent or weapon-oriented wording.",
                    ),
                    ["kill", "weapon", "gun", "knife", "stab", "bomb"],
                ),
                (
                    ModerationRule(
                        "self_harm", "Generated content included self-harm wording."
                    ),
                    [
                        "suicide",
                        "suicidal",
                        "self-harm",
                        "self harm",
                        "cut myself",
                        "hurt myself",
                        "end my life",
                    ],
                ),
                (
                    ModerationRule(
                        "sexual_content",
                        "Generated content included age-inappropriate sexual wording.",
                    ),
                    ["nude", "naked", "porn", "sexual content", "sexually explicit"],
                ),
                (
                    ModerationRule(
                        "bias_stereotype",
                        "Generated content used biased or stereotype-based framing.",
                    ),
                    [
                        "girls are bad at math",
                        "boys are better at math",
                        "because she is a girl",
                        "because he is a boy",
                    ],
                ),
                (
                    ModerationRule(
                        "substance_use",
                        "Generated content included age-inappropriate substance-use wording.",
                    ),
                    ["beer", "vodka", "get drunk", "get high", "marijuana"],
                ),
            )
        )

    def _build_term_categories(
        self,
        entries: tuple[tuple[ModerationRule, list[str]], ...],
    ) -> dict[str, ModerationRule]:
        term_categories: dict[str, ModerationRule] = {}
        for rule, terms in entries:
            for term in terms:
                term_categories[term] = rule
        return term_categories

    def moderate_request(self, request: GenerationRequest) -> ModerationResult:
        text = " ".join(
            part
            for part in [
                request.learner_prompt or "",
                " ".join(request.curriculum_context),
            ]
            if part
        )
        return self._moderate_text(
            text=text,
            stage="request",
            term_categories=self.request_term_categories or {},
        )

    def moderate_blocks(self, blocks: list[GeneratedBlock]) -> ModerationResult:
        text = " ".join(f"{block.title} {block.body}" for block in blocks)
        return self._moderate_text(
            text=text,
            stage="response",
            term_categories=self.response_term_categories or {},
        )

    def build_fallback_blocks(
        self,
        *,
        request: GenerationRequest,
        grounding: list[GroundingReference],
        moderation: ModerationResult,
    ) -> list[GeneratedBlock]:
        focus = ", ".join(
            request.target_kc_ids or request.target_lo_ids or ["the current lesson"]
        )
        grounding_text = summarize_grounding_titles(grounding)
        categories = (
            ", ".join(moderation.categories)
            if moderation.categories
            else "safety review"
        )
        reason_text = (
            moderation.reasons[0]
            if moderation.reasons
            else "The request or generated draft needs a safer reframe."
        )
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
        normalized = self._normalize_text(text)
        categories: list[str] = []
        reasons: list[str] = []
        matched_terms: list[str] = []
        category_terms: dict[str, list[str]] = {}
        category_reasons: dict[str, str] = {}
        category_severities: dict[str, str] = {}
        for term, rule in term_categories.items():
            if not self._contains_term(normalized_text=normalized, term=term):
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
        severity = (
            "block"
            if any(value == "block" for value in category_severities.values())
            else "review"
        )
        matches = [
            ModerationMatch(
                category=category,
                matched_terms=sorted(category_terms.get(category, [])),
                reason=category_reasons[category],
                severity=category_severities.get(category, severity),
            )
            for category in categories
        ]
        audit_message = f"{stage.title()} moderation flagged {', '.join(categories)} and replaced the content with a teacher-safe fallback."
        return ModerationResult(
            status="flagged",
            stage=stage,
            severity=severity,
            decision="flagged",
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
        if "bias_stereotype" in moderation.categories:
            return "Keep the response inclusive, neutral, and free from stereotype-based assumptions."
        if "substance_use" in moderation.categories:
            return "Keep examples and directions classroom-appropriate without normalizing substance use."
        if "sexual_content" in moderation.categories:
            return "Keep the response classroom-appropriate and age-appropriate."
        if "violence" in moderation.categories or "self_harm" in moderation.categories:
            return "Keep the response calm, non-violent, and focused on safe classroom learning."
        return "Avoid unsafe or degrading wording."

    def _contains_term(self, *, normalized_text: str, term: str) -> bool:
        normalized_term = self._normalize_text(term).strip()
        if not normalized_term:
            return False
        return f" {normalized_term} " in normalized_text

    def _normalize_text(self, value: str) -> str:
        collapsed = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        if not collapsed:
            return " "
        return f" {collapsed} "
