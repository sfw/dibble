from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from dibble.models.auth import AuthIdentity
from dibble.plugins.contracts import RouterPlugin
from dibble.services.auth import (
    AuthService,
    AuthenticationError,
    AuthorizationError,
)
from dibble.services.admin_config import AdminConfigService
from dibble.services.admin_academic_catalog import AdminAcademicCatalogService
from dibble.services.admin_section_membership_service import (
    AdminSectionMembershipService,
)
from dibble.services.content_warmer import ContentWarmer
from dibble.services.autonomous_teacher_harness import AutonomousTeacherHarness
from dibble.services.content_workflow import ContentWorkflowService
from dibble.services.household_service import HouseholdService
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.outcome_driven_adaptation import OutcomeDrivenAdaptationService
from dibble.services.protocols import ClassroomStore, CourseStore, UserStore
from dibble.services.protocols import ClassroomMembershipStore
from dibble.services.cognitive_trait_inference import CognitiveTraitInferenceService
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.harness.assessment_evidence import AssessmentEvidenceHarness
from dibble.services.harness.content_generation import ContentGenerationHarness
from dibble.services.harness.curriculum_evolution import CurriculumEvolutionHarness
from dibble.services.harness.curriculum_intake_harness import CurriculumIntakeHarness
from dibble.services.harness.curriculum_planning import CurriculumPlanningHarness
from dibble.services.harness.learner_profile import LearnerProfileHarness
from dibble.services.harness.modality_routing import ModalityRoutingHarness
from dibble.services.harness.within_session_control import WithinSessionControlHarness
from dibble.services.learning_calibration_profiles import (
    LearningCalibrationProfileRecorder,
)
from dibble.services.learning_progress_profiles import LearningProgressProfileRecorder
from dibble.services.learning_run_summary_recorder import LearningRunSummaryRecorder
from dibble.services.learning_state_recorder import LearningStateProfileRecorder
from dibble.services.learning_trait_profiles import LearningTraitProfileRecorder
from dibble.services.learning_strategy_recorder import LearningStrategyProfileRecorder
from dibble.services.learner_state_calibration import LearnerStateCalibrator
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.mastery_snapshot_service import MasterySnapshotService
from dibble.services.learner_history_service import LearnerHistoryService
from dibble.services.learner_progression_service import LearnerProgressionService
from dibble.services.learner_summary_service import LearnerSummaryService
from dibble.services.learner_workspace_service import LearnerWorkspaceService
from dibble.services.observation_profile_update import ObservationProfileUpdater
from dibble.services.ordinary_mastery_profiles import OrdinaryMasteryProfileRecorder
from dibble.services.predictive_content_invalidator import PredictiveContentInvalidator
from dibble.services.predictive_warm_scheduler import PredictiveWarmScheduler
from dibble.services.protocols import (
    AssignmentStore,
    AuditStore,
    CurriculumContentLibraryStore,
    KnowledgeComponentStore,
    ModalityRoutingPriorStore,
    ObservationStore,
    OutcomeStore,
    ProfileStore,
    RetentionReviewCandidateStore,
    SocraticSessionStore,
    StrandStore,
)
from dibble.services.retention_scheduler import RetentionSchedulerService
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.setup_config import SetupConfigService
from dibble.services.setup_model_catalog import SetupModelCatalogService
from dibble.services.socratic_assessment import SocraticAssessmentService
from dibble.services.socratic_profile_update import SocraticProfileUpdater
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.services.teacher_classroom_service import TeacherSectionService
from dibble.services.teacher_intervention_actions import (
    TeacherInterventionActionService,
)
from dibble.services.telemetry import TelemetryService
from dibble.services.within_session_adaptation import WithinSessionAdaptationService

ERROR_CODE_HEADER = "X-Dibble-Error-Code"


def api_error(
    *,
    status_code: int,
    detail: str,
    code: str,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    response_headers = {ERROR_CODE_HEADER: code}
    if headers:
        response_headers.update(headers)
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers=response_headers,
    )


def build_api_error_response(exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    error_code = exc.headers.get(ERROR_CODE_HEADER) if exc.headers is not None else None
    payload: dict[str, object] = {"detail": detail}
    if error_code:
        payload["code"] = error_code
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(payload),
        headers=exc.headers,
    )


class ApiServices(Protocol):
    assignment_store: AssignmentStore
    profile_store: ProfileStore
    classroom_store: ClassroomStore
    course_store: CourseStore
    classroom_membership_store: ClassroomMembershipStore
    outcome_store: OutcomeStore
    strand_store: StrandStore
    knowledge_component_store: KnowledgeComponentStore
    audit_store: AuditStore
    curriculum_content_library_store: CurriculumContentLibraryStore
    observation_store: ObservationStore
    auth_service: AuthService
    telemetry_service: TelemetryService
    operational_observability_service: OperationalObservabilityService
    router_plugin: RouterPlugin
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
    mastery_snapshot_service: MasterySnapshotService
    generation_mode_calibrator: GenerationModeCalibrator
    predictive_content_invalidator: PredictiveContentInvalidator
    predictive_warm_scheduler: PredictiveWarmScheduler
    retention_review_candidate_store: RetentionReviewCandidateStore
    retention_scheduler_service: RetentionSchedulerService
    within_session_adaptation_service: WithinSessionAdaptationService
    user_store: UserStore
    modality_routing_prior_store: ModalityRoutingPriorStore
    admin_config_service: AdminConfigService
    admin_academic_catalog_service: AdminAcademicCatalogService
    admin_section_membership_service: AdminSectionMembershipService
    setup_config_service: SetupConfigService
    setup_model_catalog_service: SetupModelCatalogService


@dataclass(slots=True)
class ApiContext:
    services: ApiServices

    def require_access(self, *allowed_roles: str):
        async def dependency(
            request: Request,
            api_key: str | None = Header(default=None, alias="X-API-Key"),
            authorization: str | None = Header(default=None, alias="Authorization"),
        ) -> AuthIdentity:
            bearer_token = None
            if authorization and authorization.lower().startswith("bearer "):
                bearer_token = authorization[7:].strip()
            try:
                session = self.services.auth_service.authorize(
                    provided_key=api_key,
                    bearer_token=bearer_token,
                    allowed_roles=tuple(allowed_roles) or ("viewer",),
                )
                identity = session.identity
                request.state.auth_identity = identity
                return identity
            except AuthenticationError as exc:
                self.services.audit_store.append(
                    event_type="auth.request",
                    status="denied",
                    payload={
                        "path": request.url.path,
                        "method": request.method,
                        "header_name": "X-API-Key",
                        "required_roles": list(allowed_roles or ("viewer",)),
                    },
                )
                raise api_error(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(exc),
                    code="auth_invalid_credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc
            except AuthorizationError as exc:
                identity = exc.identity
                self.services.audit_store.append(
                    event_type="auth.request",
                    status="forbidden",
                    payload={
                        "path": request.url.path,
                        "method": request.method,
                        "header_name": "X-API-Key",
                        "principal_id": identity.principal_id
                        if identity is not None
                        else None,
                        "role": identity.role if identity is not None else None,
                        "required_roles": list(allowed_roles or ("viewer",)),
                    },
                )
                raise api_error(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=str(exc),
                    code="auth_insufficient_role",
                ) from exc

        return dependency

    def deps(self, *roles: str):
        if not self.services.auth_service.enabled:
            return []
        return [Depends(self.require_access(*roles))]
