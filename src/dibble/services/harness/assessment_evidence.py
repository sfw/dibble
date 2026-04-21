from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.assessment import (
    SocraticAssessmentRequest,
    SocraticAssessmentResponse,
    SocraticAssessmentSession,
)
from dibble.models.observations import (
    InferredLearnerState,
    LearnerObservation,
    LearnerObservationCreate,
)
from dibble.models.profile import CognitiveTraitScore, LearnerProfile
from dibble.services.cognitive_trait_inference import CognitiveTraitInferenceService
from dibble.services.errors import LearnerProfileNotFoundError
from dibble.services.learner_state_calibration import LearnerStateCalibrator
from dibble.services.learner_state_calibration import LearnerStateCalibrationResult
from dibble.services.protocols import ObservationStore, ProfileStore
from dibble.services.socratic_assessment import SocraticAssessmentService
from dibble.services.state_inference import LearnerStateInferenceService


@dataclass(frozen=True, slots=True)
class RecordObservationEvidenceCommand:
    student_id: UUID
    observation: LearnerObservationCreate


@dataclass(frozen=True, slots=True)
class ObservationEvidenceResult:
    profile: LearnerProfile
    observation: LearnerObservation
    recent_observations: list[LearnerObservation]
    inferred_state: InferredLearnerState
    calibration: LearnerStateCalibrationResult
    inferred_cognitive_traits: dict[str, CognitiveTraitScore]


@dataclass(frozen=True, slots=True)
class RunSocraticAssessmentCommand:
    request: SocraticAssessmentRequest


@dataclass(frozen=True, slots=True)
class SocraticAssessmentHarnessResult:
    profile: LearnerProfile
    request: SocraticAssessmentRequest
    response: SocraticAssessmentResponse
    session: SocraticAssessmentSession | None


@dataclass(slots=True)
class AssessmentEvidenceHarness:
    profile_store: ProfileStore
    observation_store: ObservationStore
    state_inference_service: LearnerStateInferenceService
    learner_state_calibrator: LearnerStateCalibrator
    cognitive_trait_inference_service: CognitiveTraitInferenceService
    socratic_assessment_service: SocraticAssessmentService

    def record_observation_evidence(
        self,
        command: RecordObservationEvidenceCommand,
    ) -> ObservationEvidenceResult:
        profile = self.profile_store.get(command.student_id)
        if profile is None:
            raise LearnerProfileNotFoundError(command.student_id)

        persisted_observation = self.observation_store.append(
            student_id=str(command.student_id),
            observation=command.observation,
        )
        recent_observations = self.observation_store.list_recent(
            student_id=str(command.student_id)
        )
        inferred_state = self.state_inference_service.infer(
            student_id=command.student_id,
            observations=recent_observations,
        )
        calibration = self.learner_state_calibrator.calibrate(
            student_id=command.student_id,
            observation=command.observation,
            inferred_state=inferred_state,
        )
        inferred_cognitive_traits = self.cognitive_trait_inference_service.infer(
            student_id=command.student_id,
            observations=recent_observations,
            existing_traits=profile.cognitive_traits,
        )
        return ObservationEvidenceResult(
            profile=profile,
            observation=persisted_observation,
            recent_observations=recent_observations,
            inferred_state=calibration.state,
            calibration=calibration,
            inferred_cognitive_traits=inferred_cognitive_traits,
        )

    def run_socratic_assessment(
        self,
        command: RunSocraticAssessmentCommand,
    ) -> SocraticAssessmentHarnessResult:
        profile = self.profile_store.get(command.request.student_id)
        if profile is None:
            raise LearnerProfileNotFoundError(command.request.student_id)

        response = self.socratic_assessment_service.assess(profile, command.request)
        session = self.socratic_assessment_service.get_session(response.session_id)
        return SocraticAssessmentHarnessResult(
            profile=profile,
            request=command.request,
            response=response,
            session=session,
        )
