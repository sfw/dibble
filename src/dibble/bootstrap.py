from __future__ import annotations

from dataclasses import dataclass

from dibble.config import Settings
from dibble.plugins.loader import build_generation_plugins
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.profile_store import SQLiteProfileStore
from dibble.storage import ensure_database


@dataclass(slots=True)
class ApplicationServices:
    profile_store: SQLiteProfileStore
    curriculum_store: SQLiteCurriculumStore
    generation_engine: GenerationEngine
    router_plugin: object


def build_application_services(settings: Settings) -> ApplicationServices:
    ensure_database(settings.database_path)

    profile_store = SQLiteProfileStore(settings.database_path)
    curriculum_store = SQLiteCurriculumStore(settings.database_path)
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
        generation_engine=generation_engine,
        router_plugin=plugins.router,
    )
