from __future__ import annotations

from dataclasses import dataclass

from dibble.config import Settings
from dibble.plugins.loader import build_generation_plugins
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import AuthService
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.telemetry import TelemetryService
from dibble.storage import ensure_database


@dataclass(slots=True)
class ApplicationServices:
    profile_store: SQLiteProfileStore
    curriculum_store: SQLiteCurriculumStore
    audit_store: SQLiteAuditStore
    auth_service: AuthService
    telemetry_service: TelemetryService
    generation_engine: GenerationEngine
    router_plugin: object


def build_application_services(settings: Settings) -> ApplicationServices:
    ensure_database(settings.database_path)

    profile_store = SQLiteProfileStore(settings.database_path)
    curriculum_store = SQLiteCurriculumStore(settings.database_path)
    audit_store = SQLiteAuditStore(settings.database_path)
    auth_service = AuthService.from_settings(settings)
    plugins = build_generation_plugins(settings, curriculum_store=curriculum_store)
    generation_engine = GenerationEngine(
        retriever=plugins.retriever,
        router=plugins.router,
        provider=plugins.provider,
        validator=plugins.validator,
    )

    return ApplicationServices(
        profile_store=profile_store,
        curriculum_store=curriculum_store,
        audit_store=audit_store,
        auth_service=auth_service,
        telemetry_service=TelemetryService(audit_store),
        generation_engine=generation_engine,
        router_plugin=plugins.router,
    )
