from __future__ import annotations

from dibble.config import Settings
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.llm_provider import LLMOrchestrationProvider, build_prompt_manager_from_settings
from dibble.services.provider_health import SQLiteProviderHealthStore


def build(*, settings: Settings) -> LLMOrchestrationProvider:
    audit_store = SQLiteAuditStore(settings.database_path)
    return LLMOrchestrationProvider.from_settings(
        settings,
        health_store=SQLiteProviderHealthStore(settings.database_path),
        prompt_manager=build_prompt_manager_from_settings(settings, audit_store=audit_store),
    )
