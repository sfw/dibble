from __future__ import annotations

from dataclasses import dataclass

from dibble.config import Settings
from dibble.plugins.loader import build_generation_plugins
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import AuthService
from dibble.services.auth_sessions import SQLiteAuthSessionStore
from dibble.services.content_warmer import ContentWarmer
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.provider_health import SQLiteProviderHealthStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.services.telemetry import TelemetryService
from dibble.storage import ensure_database


@dataclass(slots=True)
class ApplicationServices:
    profile_store: SQLiteProfileStore
    curriculum_store: SQLiteCurriculumStore
    knowledge_component_store: SQLiteKnowledgeComponentStore
    audit_store: SQLiteAuditStore
    generated_content_store: SQLiteGeneratedContentStore
    observation_store: SQLiteObservationStore
    auth_service: AuthService
    telemetry_service: TelemetryService
    generation_engine: GenerationEngine
    content_warmer: ContentWarmer
    remediation_planner: RemediationPlanner
    state_inference_service: LearnerStateInferenceService
    router_plugin: object


def build_application_services(settings: Settings) -> ApplicationServices:
    ensure_database(settings.database_path)

    profile_store = SQLiteProfileStore(settings.database_path)
    curriculum_store = SQLiteCurriculumStore(settings.database_path)
    knowledge_component_store = SQLiteKnowledgeComponentStore(settings.database_path)
    audit_store = SQLiteAuditStore(settings.database_path)
    generated_content_store = SQLiteGeneratedContentStore(settings.database_path)
    observation_store = SQLiteObservationStore(settings.database_path)
    provider_health_store = SQLiteProviderHealthStore(settings.database_path)
    auth_service = AuthService.from_settings(
        settings,
        session_store=SQLiteAuthSessionStore(settings.database_path),
    )
    plugins = build_generation_plugins(settings, curriculum_store=curriculum_store)
    generation_engine = GenerationEngine(
        retriever=plugins.retriever,
        router=plugins.router,
        provider=plugins.provider,
        validator=plugins.validator,
        generated_content_store=generated_content_store,
        cache_ttl_seconds=settings.generation_cache_ttl_seconds,
    )
    remediation_planner = RemediationPlanner(
        knowledge_component_store,
        MisconceptionDetector(knowledge_component_store),
    )
    state_inference_service = LearnerStateInferenceService()
    content_warmer = ContentWarmer(profile_store, generation_engine)

    return ApplicationServices(
        profile_store=profile_store,
        curriculum_store=curriculum_store,
        knowledge_component_store=knowledge_component_store,
        audit_store=audit_store,
        generated_content_store=generated_content_store,
        observation_store=observation_store,
        auth_service=auth_service,
        telemetry_service=TelemetryService(audit_store, generated_content_store, provider_health_store),
        generation_engine=generation_engine,
        content_warmer=content_warmer,
        remediation_planner=remediation_planner,
        state_inference_service=state_inference_service,
        router_plugin=plugins.router,
    )
