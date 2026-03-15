from __future__ import annotations

from dataclasses import dataclass

from dibble.config import Settings
from dibble.plugins.contracts import RouterPlugin
from dibble.plugins.loader import build_generation_plugins
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import AuthService
from dibble.services.auth_sessions import SQLiteAuthSessionStore
from dibble.services.calibrated_router import CalibratedRouter
from dibble.services.content_warmer import ContentWarmer
from dibble.services.content_workflow import ContentWorkflowService
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.learning_run_summary_recorder import LearningRunSummaryRecorder
from dibble.services.learner_state_calibration import LearnerStateCalibrator
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.provider_health import SQLiteProviderHealthStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.protocols import (
    AuditStore,
    CurriculumStore,
    GeneratedContentStore,
    KnowledgeComponentStore,
    ObservationStore,
    ProfileStore,
    SocraticSessionStore,
)
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.services.socratic_assessment import SocraticAssessmentService
from dibble.services.socratic_evidence import SocraticEvidenceScorer
from dibble.services.socratic_policy import SocraticTurnPolicy
from dibble.services.socratic_profile_update import SocraticProfileUpdater
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.services.telemetry import TelemetryService
from dibble.storage import ensure_database


@dataclass(slots=True)
class ApplicationServices:
    profile_store: ProfileStore
    curriculum_store: CurriculumStore
    knowledge_component_store: KnowledgeComponentStore
    audit_store: AuditStore
    generated_content_store: GeneratedContentStore
    observation_store: ObservationStore
    auth_service: AuthService
    telemetry_service: TelemetryService
    generation_engine: GenerationEngine
    content_warmer: ContentWarmer
    content_workflow_service: ContentWorkflowService
    remediation_planner: RemediationPlanner
    socratic_assessment_service: SocraticAssessmentService
    socratic_profile_updater: SocraticProfileUpdater
    socratic_session_store: SocraticSessionStore
    state_inference_service: LearnerStateInferenceService
    learner_state_calibrator: LearnerStateCalibrator
    learning_run_summary_recorder: LearningRunSummaryRecorder
    router_plugin: RouterPlugin


def build_application_services(settings: Settings) -> ApplicationServices:
    ensure_database(settings.database_path)

    profile_store = SQLiteProfileStore(settings.database_path)
    curriculum_store = SQLiteCurriculumStore(settings.database_path)
    knowledge_component_store = SQLiteKnowledgeComponentStore(settings.database_path)
    audit_store = SQLiteAuditStore(settings.database_path)
    generated_content_store = SQLiteGeneratedContentStore(settings.database_path)
    observation_store = SQLiteObservationStore(settings.database_path)
    socratic_session_store = SQLiteSocraticSessionStore(settings.database_path)
    provider_health_store = SQLiteProviderHealthStore(settings.database_path)
    auth_service = AuthService.from_settings(
        settings,
        session_store=SQLiteAuthSessionStore(settings.database_path),
    )
    plugins = build_generation_plugins(settings, curriculum_store=curriculum_store)
    router_plugin = CalibratedRouter(
        base_router=plugins.router,
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
    )
    generation_engine = GenerationEngine(
        retriever=plugins.retriever,
        router=router_plugin,
        provider=plugins.provider,
        validator=plugins.validator,
        generated_content_store=generated_content_store,
        cache_ttl_seconds=settings.generation_cache_ttl_seconds,
    )
    remediation_planner = RemediationPlanner(
        knowledge_component_store,
        MisconceptionDetector(knowledge_component_store),
    )
    socratic_assessment_service = SocraticAssessmentService(
        generation_engine=generation_engine,
        session_store=socratic_session_store,
        evidence_scorer=SocraticEvidenceScorer(curriculum_store),
        turn_policy=SocraticTurnPolicy(),
    )
    socratic_profile_updater = SocraticProfileUpdater()
    state_inference_service = LearnerStateInferenceService()
    learner_state_calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
    )
    learning_run_summary_recorder = LearningRunSummaryRecorder(audit_store=audit_store)
    content_warmer = ContentWarmer(profile_store, generation_engine)
    content_workflow_service = ContentWorkflowService(
        profile_store=profile_store,
        router=router_plugin,
        generation_engine=generation_engine,
        content_warmer=content_warmer,
        remediation_planner=remediation_planner,
        audit_store=audit_store,
    )

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
        content_workflow_service=content_workflow_service,
        remediation_planner=remediation_planner,
        socratic_assessment_service=socratic_assessment_service,
        socratic_profile_updater=socratic_profile_updater,
        socratic_session_store=socratic_session_store,
        state_inference_service=state_inference_service,
        learner_state_calibrator=learner_state_calibrator,
        learning_run_summary_recorder=learning_run_summary_recorder,
        router_plugin=router_plugin,
    )
