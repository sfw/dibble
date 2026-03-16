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
from dibble.services.cognitive_trait_inference import CognitiveTraitInferenceService
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.knowledge_state_migration import KnowledgeStateMigrator
from dibble.services.learning_calibration_profiles import LearningCalibrationProfileRecorder
from dibble.services.learning_progress_profiles import LearningProgressProfileRecorder
from dibble.services.learning_run_summary_recorder import LearningRunSummaryRecorder
from dibble.services.learning_state_profiles import (
    LearnerStateSignalService,
    LearningStateProfileRecorder,
)
from dibble.services.learning_trait_profiles import (
    LearnerTraitProfileSignalService,
    LearningTraitProfileRecorder,
)
from dibble.services.learner_strategy_profiles import (
    LearnerStrategySignalService,
    LearningStrategyProfileRecorder,
)
from dibble.services.learner_state_calibration import LearnerStateCalibrator
from dibble.services.learner_summary_service import LearnerSummaryService
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.misconception_profiles import (
    LearningMisconceptionProfileRecorder,
    LearningMisconceptionProfileResolver,
)
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.predictive_content_invalidator import PredictiveContentInvalidator
from dibble.services.predictive_content_warming import PredictiveContentWarmer
from dibble.services.predictive_warm_queue_store import SQLitePredictiveWarmQueueStore
from dibble.services.predictive_warm_scheduler import PredictiveWarmScheduler
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
from dibble.services.remediation_session_store import SQLiteRemediationSessionStore
from dibble.services.remediation_workflows import RemediationWorkflowCoordinator
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.services.socratic_assessment import SocraticAssessmentService
from dibble.services.socratic_evidence import SocraticEvidenceScorer
from dibble.services.socratic_policy import SocraticTurnPolicy
from dibble.services.socratic_profile_update import SocraticProfileUpdater
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.services.telemetry import TelemetryService
from dibble.services.within_session_adaptation import WithinSessionAdaptationService
from dibble.services.within_session_controller_store import SQLiteWithinSessionControllerStore
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
    cognitive_trait_inference_service: CognitiveTraitInferenceService
    learner_state_calibrator: LearnerStateCalibrator
    learning_run_summary_recorder: LearningRunSummaryRecorder
    learning_calibration_profile_recorder: LearningCalibrationProfileRecorder
    learning_progress_profile_recorder: LearningProgressProfileRecorder
    learning_strategy_profile_recorder: LearningStrategyProfileRecorder
    learning_state_profile_recorder: LearningStateProfileRecorder
    learning_trait_profile_recorder: LearningTraitProfileRecorder
    learner_summary_service: LearnerSummaryService
    generation_mode_calibrator: GenerationModeCalibrator
    predictive_content_invalidator: PredictiveContentInvalidator
    predictive_warm_scheduler: PredictiveWarmScheduler
    within_session_adaptation_service: WithinSessionAdaptationService
    router_plugin: RouterPlugin


def build_application_services(settings: Settings) -> ApplicationServices:
    ensure_database(settings.database_path)

    profile_store = SQLiteProfileStore(settings.database_path)
    curriculum_store = SQLiteCurriculumStore(settings.database_path)
    knowledge_component_store = SQLiteKnowledgeComponentStore(settings.database_path)
    audit_store = SQLiteAuditStore(settings.database_path)
    generated_content_store = SQLiteGeneratedContentStore(settings.database_path)
    predictive_warm_queue_store = SQLitePredictiveWarmQueueStore(settings.database_path)
    observation_store = SQLiteObservationStore(settings.database_path)
    socratic_session_store = SQLiteSocraticSessionStore(settings.database_path)
    remediation_session_store = SQLiteRemediationSessionStore(settings.database_path)
    within_session_controller_store = SQLiteWithinSessionControllerStore(settings.database_path)
    provider_health_store = SQLiteProviderHealthStore(settings.database_path)
    auth_service = AuthService.from_settings(
        settings,
        session_store=SQLiteAuthSessionStore(settings.database_path),
    )
    plugins = build_generation_plugins(settings, curriculum_store=curriculum_store)
    learner_strategy_signal_service = LearnerStrategySignalService(audit_store=audit_store)
    learner_state_signal_service = LearnerStateSignalService(audit_store=audit_store)
    learner_trait_profile_signal_service = LearnerTraitProfileSignalService(audit_store=audit_store)
    within_session_adaptation_service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=within_session_controller_store,
    )
    router_plugin = CalibratedRouter(
        base_router=plugins.router,
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=learner_strategy_signal_service,
        within_session_adaptation_service=within_session_adaptation_service,
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
        MisconceptionDetector(
            knowledge_component_store,
            audit_store=audit_store,
            misconception_profile_resolver=LearningMisconceptionProfileResolver(),
        ),
    )
    remediation_workflow_coordinator = RemediationWorkflowCoordinator(
        session_store=remediation_session_store,
    )
    socratic_assessment_service = SocraticAssessmentService(
        generation_engine=generation_engine,
        session_store=socratic_session_store,
        evidence_scorer=SocraticEvidenceScorer(curriculum_store),
        turn_policy=SocraticTurnPolicy(),
    )
    socratic_profile_updater = SocraticProfileUpdater(
        knowledge_state_migrator=KnowledgeStateMigrator(knowledge_component_store=knowledge_component_store)
    )
    state_inference_service = LearnerStateInferenceService(
        state_profile_signal_service=learner_state_signal_service
    )
    cognitive_trait_inference_service = CognitiveTraitInferenceService(
        trait_profile_signal_service=learner_trait_profile_signal_service
    )
    learner_state_calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        state_signal_service=learner_state_signal_service,
    )
    generation_mode_calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=learner_strategy_signal_service,
        within_session_adaptation_service=within_session_adaptation_service,
    )
    learning_run_summary_recorder = LearningRunSummaryRecorder(audit_store=audit_store)
    learning_calibration_profile_recorder = LearningCalibrationProfileRecorder(audit_store=audit_store)
    learning_progress_profile_recorder = LearningProgressProfileRecorder(audit_store=audit_store)
    learning_strategy_profile_recorder = LearningStrategyProfileRecorder(audit_store=audit_store)
    learning_state_profile_recorder = LearningStateProfileRecorder(audit_store=audit_store)
    learning_trait_profile_recorder = LearningTraitProfileRecorder(audit_store=audit_store)
    learner_summary_service = LearnerSummaryService(
        profile_store=profile_store,
        audit_store=audit_store,
        strategy_signal_service=learner_strategy_signal_service,
        state_signal_service=learner_state_signal_service,
        trait_profile_signal_service=learner_trait_profile_signal_service,
    )
    misconception_profile_recorder = LearningMisconceptionProfileRecorder(audit_store=audit_store)
    content_warmer = ContentWarmer(
        profile_store,
        generation_engine,
        knowledge_component_store=knowledge_component_store,
        generation_mode_calibrator=generation_mode_calibrator,
    )
    predictive_content_warmer = PredictiveContentWarmer(content_warmer=content_warmer)
    predictive_warm_scheduler = PredictiveWarmScheduler(
        queue_store=predictive_warm_queue_store,
        content_warmer=content_warmer,
        inline_process_limit=settings.predictive_warm_inline_process_limit,
    )
    predictive_content_invalidator = PredictiveContentInvalidator(
        generated_content_store=generated_content_store,
        audit_store=audit_store,
        predictive_warm_task_store=predictive_warm_queue_store,
    )
    content_workflow_service = ContentWorkflowService(
        profile_store=profile_store,
        knowledge_component_store=knowledge_component_store,
        router=router_plugin,
        generation_engine=generation_engine,
        content_warmer=content_warmer,
        generation_mode_calibrator=generation_mode_calibrator,
        predictive_content_warmer=predictive_content_warmer,
        predictive_warm_scheduler=predictive_warm_scheduler,
        remediation_planner=remediation_planner,
        remediation_workflow_coordinator=remediation_workflow_coordinator,
        strategy_signal_service=learner_strategy_signal_service,
        misconception_profile_recorder=misconception_profile_recorder,
        audit_store=audit_store,
        within_session_adaptation_service=within_session_adaptation_service,
    )

    return ApplicationServices(
        profile_store=profile_store,
        curriculum_store=curriculum_store,
        knowledge_component_store=knowledge_component_store,
        audit_store=audit_store,
        generated_content_store=generated_content_store,
        observation_store=observation_store,
        auth_service=auth_service,
        telemetry_service=TelemetryService(
            audit_store,
            generated_content_store,
            provider_health_store,
            predictive_warm_queue_store=predictive_warm_queue_store,
        ),
        generation_engine=generation_engine,
        content_warmer=content_warmer,
        content_workflow_service=content_workflow_service,
        remediation_planner=remediation_planner,
        socratic_assessment_service=socratic_assessment_service,
        socratic_profile_updater=socratic_profile_updater,
        socratic_session_store=socratic_session_store,
        state_inference_service=state_inference_service,
        cognitive_trait_inference_service=cognitive_trait_inference_service,
        learner_state_calibrator=learner_state_calibrator,
        learning_run_summary_recorder=learning_run_summary_recorder,
        learning_calibration_profile_recorder=learning_calibration_profile_recorder,
        learning_progress_profile_recorder=learning_progress_profile_recorder,
        learning_strategy_profile_recorder=learning_strategy_profile_recorder,
        learning_state_profile_recorder=learning_state_profile_recorder,
        learning_trait_profile_recorder=learning_trait_profile_recorder,
        learner_summary_service=learner_summary_service,
        generation_mode_calibrator=generation_mode_calibrator,
        predictive_content_invalidator=predictive_content_invalidator,
        predictive_warm_scheduler=predictive_warm_scheduler,
        within_session_adaptation_service=within_session_adaptation_service,
        router_plugin=router_plugin,
    )
