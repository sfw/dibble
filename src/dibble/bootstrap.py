from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dibble.config import Settings
from dibble.plugins.contracts import RouterPlugin
from dibble.services.admin_config import AdminConfigService
from dibble.services.admin_academic_catalog import AdminAcademicCatalogService
from dibble.services.alignment_edge_store import (
    SQLiteAlignmentEdgeStore,
    SQLiteAlignmentReviewDecisionStore,
)
from dibble.services.admin_section_membership_service import (
    AdminSectionMembershipService,
)
from dibble.services.setup_config import SetupConfigService
from dibble.services.setup_model_catalog import SetupModelCatalogService
from dibble.plugins.loader import build_generation_plugins, build_modality_plugins
from dibble.services.assignment_store import SQLiteAssignmentStore
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import AuthService
from dibble.services.auth_sessions import SQLiteAuthSessionStore
from dibble.services.user_store import SQLiteUserStore
from dibble.services.calibrated_router import CalibratedRouter
from dibble.services.content_warmer import ContentWarmer
from dibble.services.cross_signal_consistency import CrossSignalConsistencyService
from dibble.services.content_workflow import ContentWorkflowService
from dibble.services.curriculum_content_library_store import (
    SQLiteCurriculumContentLibraryStore,
)
from dibble.services.curriculum_impact_analysis_store import (
    SQLiteCurriculumImpactAnalysisStore,
)
from dibble.services.curriculum_framework_store import SQLiteCurriculumFrameworkStore
from dibble.services.curriculum_import_adapters import (
    default_curriculum_import_adapters,
)
from dibble.services.curriculum_migration_plan_store import (
    SQLiteCurriculumMigrationPlanStore,
)
from dibble.services.curriculum_snapshot_diff_store import (
    SQLiteCurriculumSnapshotDiffStore,
)
from dibble.services.classroom_store import SQLiteClassroomStore
from dibble.services.classroom_membership_store import SQLiteClassroomMembershipStore
from dibble.services.course_store import SQLiteCourseStore
from dibble.services.cognitive_trait_inference import CognitiveTraitInferenceService
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.strand_store import SQLiteStrandStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.autonomous_teacher_harness import AutonomousTeacherHarness
from dibble.services.modality_routing_prior_store import SQLiteModalityRoutingPriorStore
from dibble.services.outcome_driven_adaptation import OutcomeDrivenAdaptationService
from dibble.services.planning_adaptation import PlanningAdaptationService
from dibble.services.rollout_decision_service import RolloutDecisionService
from dibble.services.rollout_evaluation import RolloutEvaluationService
from dibble.services.rollout_policy_store import SQLiteRolloutPolicyStore
from dibble.services.harness.assessment_evidence import AssessmentEvidenceHarness
from dibble.services.harness.content_generation import ContentGenerationHarness
from dibble.services.harness.content_library import (
    LibraryFirstCurriculumContentLibrary,
    LocalStubCloudLibraryClient,
    RemoteReadyCloudLibraryClient,
)
from dibble.services.harness.curriculum_evolution import CurriculumEvolutionHarness
from dibble.services.harness.curriculum_intake_harness import CurriculumIntakeHarness
from dibble.services.harness.curriculum_planning import CurriculumPlanningHarness
from dibble.services.harness.learner_profile import LearnerProfileHarness
from dibble.services.harness.modality_routing import ModalityRoutingHarness
from dibble.services.harness.within_session_control import WithinSessionControlHarness
from dibble.services.surplus_practice_cache import SurplusPracticeCache
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.framework_import_artifact_store import (
    SQLiteFrameworkImportArtifactStore,
)
from dibble.services.framework_import_store import SQLiteFrameworkImportStore
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.knowledge_state_migration import KnowledgeStateMigrator
from dibble.services.learning_calibration_profiles import (
    LearningCalibrationProfileRecorder,
)
from dibble.services.learning_progress_profiles import LearningProgressProfileRecorder
from dibble.services.learning_run_summary_recorder import LearningRunSummaryRecorder
from dibble.services.learner_state_signal import LearnerStateSignalService
from dibble.services.learning_state_recorder import LearningStateProfileRecorder
from dibble.services.learning_trait_profiles import (
    LearnerTraitProfileSignalService,
    LearningTraitProfileRecorder,
)
from dibble.services.learner_strategy_signal import LearnerStrategySignalService
from dibble.services.learning_strategy_recorder import LearningStrategyProfileRecorder
from dibble.services.learner_state_calibration import LearnerStateCalibrator
from dibble.services.mastery_quality_gate_outcomes import (
    MasteryQualityGateOutcomeTracker,
)
from dibble.services.mastery_quality_gate_signals import (
    MasteryQualityGateSignalService,
)
from dibble.services.mastery_snapshot_service import MasterySnapshotService
from dibble.services.mastery_snapshot_store import SQLiteMasterySnapshotStore
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.learner_goal_store import SQLiteLearnerGoalStore
from dibble.services.learner_history_service import LearnerHistoryService
from dibble.services.household_service import HouseholdService
from dibble.services.household_store import SQLiteHouseholdStore
from dibble.services.learner_progression_service import LearnerProgressionService
from dibble.services.learner_summary_service import LearnerSummaryService
from dibble.services.learner_workspace_service import LearnerWorkspaceService
from dibble.services.learner_relationship_state_store import (
    SQLiteLearnerRelationshipStateStore,
)
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.misconception_remediation_outcome_signals import (
    MisconceptionRemediationOutcomeSignalService,
)
from dibble.services.misconception_remediation_outcomes import (
    MisconceptionRemediationOutcomeTracker,
)
from dibble.services.misconception_profiles import (
    LearningMisconceptionProfileRecorder,
    LearningMisconceptionProfileResolver,
)
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.operational_trace_store import SQLiteOperationalTraceStore
from dibble.services.parent_notification_store import SQLiteParentNotificationStore
from dibble.services.observation_profile_update import ObservationProfileUpdater
from dibble.services.ordinary_mastery_profiles import (
    OrdinaryMasteryProfileRecorder,
    OrdinaryMasterySignalService,
)
from dibble.services.predictive_content_invalidator import PredictiveContentInvalidator
from dibble.services.predictive_content_warming import PredictiveContentWarmer
from dibble.services.predictive_warm_queue_store import SQLitePredictiveWarmQueueStore
from dibble.services.predictive_warm_scheduler import PredictiveWarmScheduler
from dibble.services.progression_outcome_signals import ProgressionOutcomeSignalService
from dibble.services.progression_outcome_tracker import ProgressionOutcomeTracker
from dibble.services.resource_state_transitions import OutcomeStateTransitionTracker
from dibble.services.progression_ownership import ProgressionOwnershipService
from dibble.services.provider_health import SQLiteProviderHealthStore
from dibble.services.published_curriculum_snapshot_store import (
    SQLitePublishedCurriculumSnapshotStore,
)
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.protocols import (
    AssignmentStore,
    AuditStore,
    ClassroomStore,
    ClassroomMembershipStore,
    CourseStore,
    HouseholdStore,
    LearnerGoalStore,
    LearnerRelationshipStateStore,
    ModalityRoutingPriorStore,
    OutcomeStore,
    ParentNotificationStore,
    SessionControlStore,
    StrandStore,
    GeneratedContentStore,
    KnowledgeComponentStore,
    ObservationStore,
    ProfileStore,
    TrajectoryStore,
    SocraticSessionStore,
    UserStore,
)
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.remediation_session_store import SQLiteRemediationSessionStore
from dibble.services.remediation_workflows import RemediationWorkflowCoordinator
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.services.socratic_assessment import SocraticAssessmentService
from dibble.services.socratic_conversation_signals import (
    SocraticConversationSignalService,
)
from dibble.services.socratic_evidence import SocraticEvidenceScorer
from dibble.services.socratic_policy import SocraticTurnPolicy
from dibble.services.socratic_profile_update import SocraticProfileUpdater
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.services.teacher_classroom_service import TeacherSectionService
from dibble.services.teacher_intervention_actions import (
    TeacherInterventionActionService,
)
from dibble.services.telemetry import TelemetryService
from dibble.services.trajectory_planner import TrajectoryPlanner
from dibble.services.learner_state_prediction_outcomes import (
    LearnerStatePredictionOutcomeTracker,
)
from dibble.services.learner_state_prediction_signals import (
    LearnerStatePredictionSignalService,
)
from dibble.services.within_session_adaptation import WithinSessionAdaptationService
from dibble.services.within_session_controller_store import (
    SQLiteWithinSessionControllerStore,
)
from dibble.services.session_control_store import SQLiteSessionControlStore
from dibble.services.trajectory_store import SQLiteTrajectoryStore
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


@dataclass(slots=True)
class ApplicationServices:
    assignment_store: AssignmentStore
    profile_store: ProfileStore
    classroom_store: ClassroomStore
    course_store: CourseStore
    classroom_membership_store: ClassroomMembershipStore
    outcome_store: OutcomeStore
    strand_store: StrandStore
    knowledge_component_store: KnowledgeComponentStore
    audit_store: AuditStore
    generated_content_store: GeneratedContentStore
    curriculum_content_library_store: SQLiteCurriculumContentLibraryStore
    modality_routing_prior_store: ModalityRoutingPriorStore
    observation_store: ObservationStore
    learner_goal_store: LearnerGoalStore
    trajectory_store: TrajectoryStore
    session_control_store: SessionControlStore
    household_store: HouseholdStore
    rollout_policy_store: SQLiteRolloutPolicyStore
    auth_service: AuthService
    telemetry_service: TelemetryService
    operational_observability_service: OperationalObservabilityService
    rollout_decision_service: RolloutDecisionService
    rollout_evaluation_service: RolloutEvaluationService
    generation_engine: GenerationEngine
    content_warmer: ContentWarmer
    content_workflow_service: ContentWorkflowService
    outcome_driven_adaptation_service: OutcomeDrivenAdaptationService
    learner_profile_harness: LearnerProfileHarness
    assessment_evidence_harness: AssessmentEvidenceHarness
    modality_routing_harness: ModalityRoutingHarness
    content_generation_harness: ContentGenerationHarness
    curriculum_intake_harness: CurriculumIntakeHarness
    curriculum_evolution_harness: CurriculumEvolutionHarness
    curriculum_planning_harness: CurriculumPlanningHarness
    within_session_control_harness: WithinSessionControlHarness
    autonomous_teacher_harness: AutonomousTeacherHarness
    remediation_planner: RemediationPlanner
    socratic_assessment_service: SocraticAssessmentService
    socratic_profile_updater: SocraticProfileUpdater
    observation_profile_updater: ObservationProfileUpdater
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
    ordinary_mastery_profile_recorder: OrdinaryMasteryProfileRecorder
    learner_flow_service: LearnerFlowService
    learner_history_service: LearnerHistoryService
    learner_progression_service: LearnerProgressionService
    learner_summary_service: LearnerSummaryService
    learner_workspace_service: LearnerWorkspaceService
    teacher_section_service: TeacherSectionService
    teacher_intervention_action_service: TeacherInterventionActionService
    household_service: HouseholdService
    generation_mode_calibrator: GenerationModeCalibrator
    predictive_content_invalidator: PredictiveContentInvalidator
    predictive_warm_scheduler: PredictiveWarmScheduler
    mastery_snapshot_service: MasterySnapshotService
    progression_outcome_tracker: ProgressionOutcomeTracker
    misconception_remediation_outcome_tracker: MisconceptionRemediationOutcomeTracker
    outcome_state_transition_tracker: OutcomeStateTransitionTracker
    mastery_quality_gate_outcome_tracker: MasteryQualityGateOutcomeTracker
    learner_state_prediction_outcome_tracker: LearnerStatePredictionOutcomeTracker
    learner_state_prediction_signal_service: LearnerStatePredictionSignalService
    within_session_adaptation_service: WithinSessionAdaptationService
    router_plugin: RouterPlugin
    user_store: UserStore
    learner_relationship_state_store: LearnerRelationshipStateStore
    parent_notification_store: ParentNotificationStore
    admin_config_service: AdminConfigService
    admin_academic_catalog_service: AdminAcademicCatalogService
    admin_section_membership_service: AdminSectionMembershipService
    setup_config_service: SetupConfigService
    setup_model_catalog_service: SetupModelCatalogService
    provider_health_store: SQLiteProviderHealthStore
    operational_trace_store: SQLiteOperationalTraceStore


def build_application_services(
    settings: Settings,
    *,
    settings_loader: Callable[[], Settings],
) -> ApplicationServices:
    ensure_database(settings.database_path)
    conn = create_connection(settings.database_path)

    assignment_store = SQLiteAssignmentStore(conn)
    profile_store = SQLiteProfileStore(conn)
    course_store = SQLiteCourseStore(conn)
    classroom_store = SQLiteClassroomStore(conn)
    classroom_membership_store = SQLiteClassroomMembershipStore(conn)
    outcome_store = SQLiteOutcomeStore(conn)
    strand_store = SQLiteStrandStore(conn)
    knowledge_component_store = SQLiteKnowledgeComponentStore(conn)
    curriculum_framework_store = SQLiteCurriculumFrameworkStore(conn)
    framework_import_store = SQLiteFrameworkImportStore(conn)
    framework_import_artifact_store = SQLiteFrameworkImportArtifactStore(conn)
    published_curriculum_snapshot_store = SQLitePublishedCurriculumSnapshotStore(conn)
    curriculum_snapshot_diff_store = SQLiteCurriculumSnapshotDiffStore(conn)
    curriculum_impact_analysis_store = SQLiteCurriculumImpactAnalysisStore(conn)
    curriculum_migration_plan_store = SQLiteCurriculumMigrationPlanStore(conn)
    alignment_edge_store = SQLiteAlignmentEdgeStore(conn)
    alignment_review_decision_store = SQLiteAlignmentReviewDecisionStore(conn)
    audit_store = SQLiteAuditStore(conn)
    generated_content_store = SQLiteGeneratedContentStore(conn)
    curriculum_content_library_store = SQLiteCurriculumContentLibraryStore(conn)
    predictive_warm_queue_store = SQLitePredictiveWarmQueueStore(conn)
    observation_store = SQLiteObservationStore(conn)
    socratic_session_store = SQLiteSocraticSessionStore(conn)
    remediation_session_store = SQLiteRemediationSessionStore(conn)
    within_session_controller_store = SQLiteWithinSessionControllerStore(conn)
    learner_goal_store = SQLiteLearnerGoalStore(conn)
    trajectory_store = SQLiteTrajectoryStore(conn)
    session_control_store = SQLiteSessionControlStore(conn)
    provider_health_store = SQLiteProviderHealthStore(conn)
    operational_trace_store = SQLiteOperationalTraceStore(conn)
    user_store = SQLiteUserStore(conn)
    household_store = SQLiteHouseholdStore(conn)
    rollout_policy_store = SQLiteRolloutPolicyStore(conn)
    learner_relationship_state_store = SQLiteLearnerRelationshipStateStore(conn)
    parent_notification_store = SQLiteParentNotificationStore(conn)
    modality_routing_prior_store = SQLiteModalityRoutingPriorStore(conn)
    rollout_decision_service = RolloutDecisionService(
        policy_store=rollout_policy_store,
        user_store=user_store,
    )
    auth_service = AuthService.from_settings(
        settings,
        session_store=SQLiteAuthSessionStore(conn),
        user_store=user_store,
    )
    plugins = build_generation_plugins(
        settings, outcome_store=outcome_store, connection=conn
    )
    modality_plugins = build_modality_plugins()
    learner_strategy_signal_service = LearnerStrategySignalService(
        audit_store=audit_store
    )
    learner_state_signal_service = LearnerStateSignalService(audit_store=audit_store)
    learner_trait_profile_signal_service = LearnerTraitProfileSignalService(
        audit_store=audit_store
    )
    ordinary_mastery_signal_service = OrdinaryMasterySignalService(
        audit_store=audit_store
    )
    learner_state_prediction_signal_service = LearnerStatePredictionSignalService(
        audit_store=audit_store
    )
    progression_outcome_signal_service = ProgressionOutcomeSignalService(
        audit_store=audit_store
    )
    mastery_quality_gate_signal_service = MasteryQualityGateSignalService(
        audit_store=audit_store
    )
    within_session_adaptation_service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=within_session_controller_store,
    )
    router_plugin = CalibratedRouter(
        base_router=plugins.router,
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
        strategy_signal_service=learner_strategy_signal_service,
        within_session_adaptation_service=within_session_adaptation_service,
    )
    surplus_practice_cache = SurplusPracticeCache(
        generated_content_store=generated_content_store,
        cache_ttl_seconds=settings.generation_cache_ttl_seconds,
    )
    local_curriculum_content_library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(curriculum_content_library_store),
        remote_client=RemoteReadyCloudLibraryClient(
            endpoint=settings.cloud_library_endpoint,
            enabled=settings.cloud_library_enabled,
            api_key=settings.cloud_library_api_key,
            timeout_seconds=settings.cloud_library_timeout_seconds,
            retry_attempts=settings.cloud_library_retry_attempts,
        ),
    )
    generation_engine = GenerationEngine(
        retriever=plugins.retriever,
        router=router_plugin,
        provider=plugins.provider,
        validator=plugins.validator,
        generated_content_store=generated_content_store,
        content_library=local_curriculum_content_library,
        surplus_practice_cache=surplus_practice_cache,
        cache_ttl_seconds=settings.generation_cache_ttl_seconds,
    )
    modality_routing_harness = ModalityRoutingHarness(
        router=router_plugin,
        modality_plugins=modality_plugins,
        prior_store=modality_routing_prior_store,
        audit_store=audit_store,
        rollout_decision_service=rollout_decision_service,
    )
    operational_observability_service = OperationalObservabilityService(
        trace_store=operational_trace_store,
        provider_health_store=provider_health_store,
        curriculum_migration_plan_store=curriculum_migration_plan_store,
        learner_relationship_state_store=learner_relationship_state_store,
        user_store=user_store,
        content_library=local_curriculum_content_library,
        rollout_decision_service=rollout_decision_service,
    )
    local_curriculum_content_library.observability_service = (
        operational_observability_service
    )
    local_curriculum_content_library.rollout_decision_service = rollout_decision_service
    content_generation_harness = ContentGenerationHarness(
        generation_engine=generation_engine,
        modality_routing_harness=modality_routing_harness,
        modality_plugins=modality_plugins,
        operational_observability_service=operational_observability_service,
    )
    misconception_remediation_outcome_signal_service = (
        MisconceptionRemediationOutcomeSignalService(audit_store=audit_store)
    )
    remediation_planner = RemediationPlanner(
        knowledge_component_store,
        MisconceptionDetector(
            knowledge_component_store,
            observation_store=observation_store,
            audit_store=audit_store,
            misconception_profile_resolver=LearningMisconceptionProfileResolver(),
            remediation_outcome_signal_service=misconception_remediation_outcome_signal_service,
        ),
    )
    remediation_workflow_coordinator = RemediationWorkflowCoordinator(
        session_store=remediation_session_store,
    )
    socratic_assessment_service = SocraticAssessmentService(
        content_generation_harness=content_generation_harness,
        session_store=socratic_session_store,
        evidence_scorer=SocraticEvidenceScorer(outcome_store),
        turn_policy=SocraticTurnPolicy(),
    )
    socratic_profile_updater = SocraticProfileUpdater(
        knowledge_state_migrator=KnowledgeStateMigrator(
            knowledge_component_store=knowledge_component_store
        )
    )
    observation_profile_updater = ObservationProfileUpdater(
        knowledge_state_migrator=KnowledgeStateMigrator(
            knowledge_component_store=knowledge_component_store
        ),
        ordinary_mastery_signal_service=ordinary_mastery_signal_service,
    )
    learner_profile_harness = LearnerProfileHarness(
        profile_store=profile_store,
        observation_profile_updater=observation_profile_updater,
        socratic_profile_updater=socratic_profile_updater,
    )
    progression_ownership_service = ProgressionOwnershipService(
        knowledge_component_store=knowledge_component_store,
        strategy_signal_service=learner_strategy_signal_service,
        within_session_adaptation_service=within_session_adaptation_service,
        observation_store=observation_store,
        audit_store=audit_store,
        observation_profile_updater=observation_profile_updater,
        ordinary_mastery_signal_service=ordinary_mastery_signal_service,
        progression_outcome_signal_service=progression_outcome_signal_service,
    )
    state_inference_service = LearnerStateInferenceService(
        state_profile_signal_service=learner_state_signal_service
    )
    cognitive_trait_inference_service = CognitiveTraitInferenceService(
        trait_profile_signal_service=learner_trait_profile_signal_service
    )
    learner_state_calibrator = LearnerStateCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
        state_signal_service=learner_state_signal_service,
    )
    assessment_evidence_harness = AssessmentEvidenceHarness(
        profile_store=profile_store,
        observation_store=observation_store,
        state_inference_service=state_inference_service,
        learner_state_calibrator=learner_state_calibrator,
        cognitive_trait_inference_service=cognitive_trait_inference_service,
        socratic_assessment_service=socratic_assessment_service,
    )
    socratic_conversation_signal_service = SocraticConversationSignalService(
        audit_store=audit_store
    )
    generation_mode_calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(
            audit_store=audit_store
        ),
        strategy_signal_service=learner_strategy_signal_service,
        within_session_adaptation_service=within_session_adaptation_service,
        state_signal_service=learner_state_signal_service,
        trait_profile_signal_service=learner_trait_profile_signal_service,
        socratic_conversation_signal_service=socratic_conversation_signal_service,
    )
    learning_run_summary_recorder = LearningRunSummaryRecorder(audit_store=audit_store)
    learning_calibration_profile_recorder = LearningCalibrationProfileRecorder(
        audit_store=audit_store
    )
    learning_progress_profile_recorder = LearningProgressProfileRecorder(
        audit_store=audit_store
    )
    learning_strategy_profile_recorder = LearningStrategyProfileRecorder(
        audit_store=audit_store
    )
    learning_state_profile_recorder = LearningStateProfileRecorder(
        audit_store=audit_store
    )
    learning_trait_profile_recorder = LearningTraitProfileRecorder(
        audit_store=audit_store
    )
    ordinary_mastery_profile_recorder = OrdinaryMasteryProfileRecorder(
        audit_store=audit_store
    )
    mastery_snapshot_store = SQLiteMasterySnapshotStore(conn)
    mastery_snapshot_service = MasterySnapshotService(
        snapshot_store=mastery_snapshot_store
    )
    learner_flow_service = LearnerFlowService(
        audit_store=audit_store,
        generated_content_store=generated_content_store,
        socratic_session_store=socratic_session_store,
        remediation_session_store=remediation_session_store,
        within_session_controller_store=within_session_controller_store,
        session_control_store=session_control_store,
    )
    learner_history_service = LearnerHistoryService(
        generated_content_store=generated_content_store,
        socratic_session_store=socratic_session_store,
        remediation_session_store=remediation_session_store,
    )
    learner_progression_service = LearnerProgressionService(
        profile_store=profile_store,
        outcome_store=outcome_store,
        knowledge_component_store=knowledge_component_store,
        learner_flow_service=learner_flow_service,
        ordinary_mastery_signal_service=ordinary_mastery_signal_service,
        quality_gate_signal_service=mastery_quality_gate_signal_service,
    )
    curriculum_intake_harness = CurriculumIntakeHarness(
        framework_store=curriculum_framework_store,
        framework_import_store=framework_import_store,
        framework_import_artifact_store=framework_import_artifact_store,
        published_snapshot_store=published_curriculum_snapshot_store,
        alignment_edge_store=alignment_edge_store,
        alignment_review_decision_store=alignment_review_decision_store,
        course_store=course_store,
        strand_store=strand_store,
        outcome_store=outcome_store,
        knowledge_component_store=knowledge_component_store,
        adapters=tuple(default_curriculum_import_adapters()),
        operational_observability_service=operational_observability_service,
    )
    curriculum_planning_harness = CurriculumPlanningHarness(
        profile_store=profile_store,
        outcome_store=outcome_store,
        learner_goal_store=learner_goal_store,
        trajectory_store=trajectory_store,
        learner_progression_service=learner_progression_service,
        trajectory_planner=TrajectoryPlanner(
            kc_sequence_planner=progression_ownership_service.kc_sequence_planner,
            progression_ownership_service=progression_ownership_service,
        ),
        planning_adaptation_service=PlanningAdaptationService(
            audit_store=audit_store,
            prior_store=modality_routing_prior_store,
            strategy_signal_service=learner_strategy_signal_service,
            state_signal_service=learner_state_signal_service,
        ),
    )
    curriculum_evolution_harness = CurriculumEvolutionHarness(
        published_snapshot_store=published_curriculum_snapshot_store,
        framework_import_artifact_store=framework_import_artifact_store,
        alignment_edge_store=alignment_edge_store,
        curriculum_snapshot_diff_store=curriculum_snapshot_diff_store,
        curriculum_impact_analysis_store=curriculum_impact_analysis_store,
        curriculum_migration_plan_store=curriculum_migration_plan_store,
        profile_store=profile_store,
        learner_goal_store=learner_goal_store,
        trajectory_store=trajectory_store,
        assignment_store=assignment_store,
        classroom_store=classroom_store,
        course_store=course_store,
        curriculum_content_library_store=curriculum_content_library_store,
        operational_observability_service=operational_observability_service,
        rollout_decision_service=rollout_decision_service,
    )
    within_session_control_harness = WithinSessionControlHarness(
        curriculum_planning_harness=curriculum_planning_harness,
        session_control_store=session_control_store,
        operational_observability_service=operational_observability_service,
    )
    cross_signal_consistency_service = CrossSignalConsistencyService()
    learner_summary_service = LearnerSummaryService(
        profile_store=profile_store,
        audit_store=audit_store,
        strategy_signal_service=learner_strategy_signal_service,
        state_signal_service=learner_state_signal_service,
        trait_profile_signal_service=learner_trait_profile_signal_service,
        state_prediction_signal_service=learner_state_prediction_signal_service,
        cross_signal_consistency_service=cross_signal_consistency_service,
        learner_flow_service=learner_flow_service,
        learner_progression_service=learner_progression_service,
    )
    autonomous_teacher_harness = AutonomousTeacherHarness(
        learner_summary_service=learner_summary_service,
        curriculum_planning_harness=curriculum_planning_harness,
        within_session_control_harness=within_session_control_harness,
        learner_relationship_state_store=learner_relationship_state_store,
        parent_notification_store=parent_notification_store,
        user_store=user_store,
        audit_store=audit_store,
        modality_routing_prior_store=modality_routing_prior_store,
        operational_observability_service=operational_observability_service,
        rollout_decision_service=rollout_decision_service,
    )
    outcome_driven_adaptation_service = OutcomeDrivenAdaptationService(
        audit_store=audit_store,
        prior_store=modality_routing_prior_store,
        curriculum_content_library_store=curriculum_content_library_store,
        rollout_decision_service=rollout_decision_service,
    )
    rollout_evaluation_service = RolloutEvaluationService(audit_store=audit_store)
    teacher_intervention_action_service = TeacherInterventionActionService(
        audit_store=audit_store,
        learner_flow_service=learner_flow_service,
    )
    teacher_section_service = TeacherSectionService(
        learner_summary_service=learner_summary_service,
        teacher_intervention_action_service=teacher_intervention_action_service,
        classroom_membership_store=classroom_membership_store,
        user_store=user_store,
    )
    misconception_profile_recorder = LearningMisconceptionProfileRecorder(
        audit_store=audit_store
    )
    progression_outcome_tracker = ProgressionOutcomeTracker(audit_store=audit_store)
    outcome_state_transition_tracker = OutcomeStateTransitionTracker(
        audit_store=audit_store
    )
    mastery_quality_gate_outcome_tracker = MasteryQualityGateOutcomeTracker(
        audit_store=audit_store
    )
    misconception_remediation_outcome_tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store,
        remediation_session_store=remediation_session_store,
    )
    learner_state_prediction_outcome_tracker = LearnerStatePredictionOutcomeTracker(
        audit_store=audit_store
    )
    content_warmer = ContentWarmer(
        profile_store,
        generation_engine,
        knowledge_component_store=knowledge_component_store,
        generation_mode_calibrator=generation_mode_calibrator,
        progression_ownership_service=progression_ownership_service,
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
        observation_store=observation_store,
        knowledge_component_store=knowledge_component_store,
        generated_content_store=generated_content_store,
        router=router_plugin,
        generation_engine=generation_engine,
        modality_routing_harness=modality_routing_harness,
        content_generation_harness=content_generation_harness,
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
        within_session_control_harness=within_session_control_harness,
        observation_profile_updater=observation_profile_updater,
        progression_ownership_service=progression_ownership_service,
    )
    learner_workspace_service = LearnerWorkspaceService(
        learner_summary_service=learner_summary_service,
        content_workflow_service=content_workflow_service,
        socratic_assessment_service=socratic_assessment_service,
        curriculum_planning_harness=curriculum_planning_harness,
        within_session_control_harness=within_session_control_harness,
        autonomous_teacher_harness=autonomous_teacher_harness,
    )
    household_service = HouseholdService(
        household_store=household_store,
        user_store=user_store,
        autonomous_teacher_harness=autonomous_teacher_harness,
        parent_notification_store=parent_notification_store,
        curriculum_planning_harness=curriculum_planning_harness,
        audit_store=audit_store,
        operational_observability_service=operational_observability_service,
    )

    return ApplicationServices(
        assignment_store=assignment_store,
        profile_store=profile_store,
        classroom_store=classroom_store,
        course_store=course_store,
        classroom_membership_store=classroom_membership_store,
        outcome_store=outcome_store,
        strand_store=strand_store,
        knowledge_component_store=knowledge_component_store,
        audit_store=audit_store,
        generated_content_store=generated_content_store,
        curriculum_content_library_store=curriculum_content_library_store,
        modality_routing_prior_store=modality_routing_prior_store,
        observation_store=observation_store,
        learner_goal_store=learner_goal_store,
        trajectory_store=trajectory_store,
        session_control_store=session_control_store,
        household_store=household_store,
        rollout_policy_store=rollout_policy_store,
        auth_service=auth_service,
        telemetry_service=TelemetryService(
            audit_store,
            generated_content_store,
            provider_health_store,
            predictive_warm_queue_store=predictive_warm_queue_store,
        ),
        operational_observability_service=operational_observability_service,
        rollout_decision_service=rollout_decision_service,
        rollout_evaluation_service=rollout_evaluation_service,
        generation_engine=generation_engine,
        content_warmer=content_warmer,
        content_workflow_service=content_workflow_service,
        outcome_driven_adaptation_service=outcome_driven_adaptation_service,
        learner_profile_harness=learner_profile_harness,
        assessment_evidence_harness=assessment_evidence_harness,
        modality_routing_harness=modality_routing_harness,
        content_generation_harness=content_generation_harness,
        curriculum_intake_harness=curriculum_intake_harness,
        curriculum_evolution_harness=curriculum_evolution_harness,
        curriculum_planning_harness=curriculum_planning_harness,
        within_session_control_harness=within_session_control_harness,
        autonomous_teacher_harness=autonomous_teacher_harness,
        remediation_planner=remediation_planner,
        socratic_assessment_service=socratic_assessment_service,
        socratic_profile_updater=socratic_profile_updater,
        observation_profile_updater=observation_profile_updater,
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
        ordinary_mastery_profile_recorder=ordinary_mastery_profile_recorder,
        learner_flow_service=learner_flow_service,
        learner_history_service=learner_history_service,
        learner_progression_service=learner_progression_service,
        learner_summary_service=learner_summary_service,
        learner_workspace_service=learner_workspace_service,
        teacher_section_service=teacher_section_service,
        teacher_intervention_action_service=teacher_intervention_action_service,
        household_service=household_service,
        generation_mode_calibrator=generation_mode_calibrator,
        predictive_content_invalidator=predictive_content_invalidator,
        predictive_warm_scheduler=predictive_warm_scheduler,
        mastery_snapshot_service=mastery_snapshot_service,
        progression_outcome_tracker=progression_outcome_tracker,
        outcome_state_transition_tracker=outcome_state_transition_tracker,
        mastery_quality_gate_outcome_tracker=mastery_quality_gate_outcome_tracker,
        misconception_remediation_outcome_tracker=misconception_remediation_outcome_tracker,
        learner_state_prediction_outcome_tracker=learner_state_prediction_outcome_tracker,
        learner_state_prediction_signal_service=learner_state_prediction_signal_service,
        within_session_adaptation_service=within_session_adaptation_service,
        router_plugin=router_plugin,
        user_store=user_store,
        learner_relationship_state_store=learner_relationship_state_store,
        parent_notification_store=parent_notification_store,
        admin_config_service=AdminConfigService(
            settings,
            settings_loader=settings_loader,
        ),
        admin_academic_catalog_service=AdminAcademicCatalogService(
            course_store=course_store,
            classroom_store=classroom_store,
            classroom_membership_store=classroom_membership_store,
        ),
        admin_section_membership_service=AdminSectionMembershipService(
            classroom_store=classroom_store,
            classroom_membership_store=classroom_membership_store,
            user_store=user_store,
        ),
        setup_config_service=SetupConfigService(
            settings,
            user_store=user_store,
            settings_loader=settings_loader,
        ),
        setup_model_catalog_service=SetupModelCatalogService(),
        provider_health_store=provider_health_store,
        operational_trace_store=operational_trace_store,
    )
