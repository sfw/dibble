from __future__ import annotations

from dataclasses import dataclass

from dibble.models.observations import InferredLearnerState
from dibble.models.profile import CognitiveTraitScore, LearnerProfile
from dibble.services.harness.assessment_evidence import (
    ObservationEvidenceResult,
    SocraticAssessmentHarnessResult,
)
from dibble.services.learner_state_calibration import LearnerStateCalibrationResult
from dibble.services.observation_profile_update import ObservationProfileUpdater
from dibble.services.observation_profile_update import ObservationProfileUpdateResult
from dibble.services.protocols import ProfileStore
from dibble.services.retention_scheduler import RetentionSchedulerService
from dibble.services.socratic_profile_update import SocraticProfileUpdater
from dibble.services.socratic_profile_update import SocraticProfileUpdateResult


@dataclass(frozen=True, slots=True)
class UpsertLearnerProfileCommand:
    profile: LearnerProfile


@dataclass(frozen=True, slots=True)
class UpsertLearnerProfileResult:
    profile: LearnerProfile
    applied: bool = True
    source: str = "declared_profile"


@dataclass(frozen=True, slots=True)
class ApplyObservationEvidenceCommand:
    evidence: ObservationEvidenceResult


@dataclass(frozen=True, slots=True)
class ApplyObservationEvidenceResult:
    profile: LearnerProfile
    inferred_state: InferredLearnerState
    inferred_cognitive_traits: dict[str, CognitiveTraitScore]
    calibration: LearnerStateCalibrationResult
    mastery_update: ObservationProfileUpdateResult


@dataclass(frozen=True, slots=True)
class ApplySocraticEvidenceCommand:
    assessment: SocraticAssessmentHarnessResult


@dataclass(frozen=True, slots=True)
class ApplySocraticEvidenceResult:
    profile: LearnerProfile
    profile_update: SocraticProfileUpdateResult


@dataclass(slots=True)
class LearnerProfileHarness:
    profile_store: ProfileStore
    observation_profile_updater: ObservationProfileUpdater
    socratic_profile_updater: SocraticProfileUpdater
    retention_scheduler: RetentionSchedulerService | None = None

    def upsert_profile(
        self, command: UpsertLearnerProfileCommand
    ) -> UpsertLearnerProfileResult:
        return UpsertLearnerProfileResult(
            profile=self.profile_store.upsert(command.profile)
        )

    def apply_observation_evidence(
        self,
        command: ApplyObservationEvidenceCommand,
    ) -> ApplyObservationEvidenceResult:
        evidence = command.evidence
        profile = evidence.profile.model_copy(
            update={
                "cognitive_traits": evidence.inferred_cognitive_traits,
                "affective_state": evidence.inferred_state.affective_state,
                "cognitive_load": evidence.inferred_state.cognitive_load,
                "metacognitive_state": evidence.inferred_state.metacognitive_state,
                "updated_at": (
                    evidence.inferred_state.last_observation_at or evidence.profile.updated_at
                ),
            }
        )
        mastery_update = self.observation_profile_updater.apply(
            profile,
            evidence.observation,
            recent_observations=evidence.recent_observations,
        )
        persisted_profile = self.profile_store.upsert(mastery_update.profile)
        if self.retention_scheduler is not None and mastery_update.applied:
            self.retention_scheduler.nominate_from_observation_writeback(
                learner_id=persisted_profile.student_id,
                observation=evidence.observation,
                mastery_update=mastery_update,
            )
        return ApplyObservationEvidenceResult(
            profile=persisted_profile,
            inferred_state=evidence.inferred_state,
            inferred_cognitive_traits=evidence.inferred_cognitive_traits,
            calibration=evidence.calibration,
            mastery_update=mastery_update,
        )

    def apply_socratic_evidence(
        self,
        command: ApplySocraticEvidenceCommand,
    ) -> ApplySocraticEvidenceResult:
        assessment = command.assessment
        profile_update = self.socratic_profile_updater.apply(
            assessment.profile,
            assessment.request,
            assessment.response,
            assessment.session,
        )
        persisted_profile = (
            self.profile_store.upsert(profile_update.profile)
            if profile_update.applied
            else assessment.profile
        )
        return ApplySocraticEvidenceResult(
            profile=persisted_profile,
            profile_update=profile_update,
        )
