"""LLM-backed safety check for learner-facing drafts.

A second moderation layer on top of the local keyword/category matcher: when
a secondary LLM client is configured, generated learner-facing content is
classified for child-safety concerns before delivery. Both verdicts (local
matcher and LLM) are recorded so post-pilot analysis can compare them. If the
LLM is unavailable the local matcher remains the sole authority — this layer
fails open to the existing behavior, never closed. (POC roadmap 1.4)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You review learning content that will be shown to a child aged 9-12 on a "
    "math learning platform. Classify whether the content is safe to show. "
    "Flag content containing: violence, self-harm, sexual content, hate or "
    "harassment, dangerous instructions, personal-data solicitation, shaming "
    "or demeaning language toward the learner, or off-topic adult themes. "
    "Ordinary math content, encouragement, and age-appropriate examples are "
    "safe. Respond with JSON only: "
    '{"safe": true|false, "categories": ["..."], "reason": "..."}'
)


class LLMSafetyVerdict(BaseModel):
    status: str = "skipped"  # safe | flagged | unavailable | skipped
    categories: list[str] = Field(default_factory=list)
    reason: str | None = None


@dataclass(slots=True)
class LLMSafetyChecker:
    """Wraps an OpenAI-compatible chat client (.complete) as a safety rater."""

    client: object | None = None
    max_text_chars: int = 6000

    def check_text(self, text: str) -> LLMSafetyVerdict:
        if self.client is None:
            return LLMSafetyVerdict(status="skipped")
        if not text.strip():
            return LLMSafetyVerdict(status="safe")
        try:
            completion = self.client.complete(  # type: ignore[attr-defined]
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=text[: self.max_text_chars],
            )
            return self._parse(completion.content)
        except Exception:  # noqa: BLE001 - fail open to the local matcher
            logger.warning("LLM safety check unavailable", exc_info=True)
            return LLMSafetyVerdict(status="unavailable")

    def _parse(self, content: str) -> LLMSafetyVerdict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 2:
                cleaned = "\n".join(lines[1:-1]).strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM safety check returned non-JSON verdict")
            return LLMSafetyVerdict(status="unavailable")
        if not isinstance(payload, dict) or "safe" not in payload:
            return LLMSafetyVerdict(status="unavailable")
        categories = [
            str(category)
            for category in payload.get("categories", [])
            if isinstance(category, (str, int))
        ]
        reason = payload.get("reason")
        return LLMSafetyVerdict(
            status="safe" if bool(payload["safe"]) else "flagged",
            categories=categories,
            reason=str(reason) if reason is not None else None,
        )
