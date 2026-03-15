from __future__ import annotations

from dibble.config import Settings
from dibble.services.llm_provider import LLMOrchestrationProvider


def build(*, settings: Settings) -> LLMOrchestrationProvider:
    return LLMOrchestrationProvider.from_settings(settings)
