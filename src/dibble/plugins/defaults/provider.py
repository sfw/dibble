from __future__ import annotations

import sqlite3

from dibble.config import Settings
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.llm_provider import (
    LLMOrchestrationProvider,
    build_prompt_manager_from_settings,
)
from dibble.services.provider_health import SQLiteProviderHealthStore


def build(
    *, settings: Settings, connection: sqlite3.Connection
) -> LLMOrchestrationProvider:
    audit_store = SQLiteAuditStore(connection)
    return LLMOrchestrationProvider.from_settings(
        settings,
        health_store=SQLiteProviderHealthStore(connection),
        prompt_manager=build_prompt_manager_from_settings(
            settings, audit_store=audit_store
        ),
    )
