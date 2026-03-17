from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.models.assessment import SocraticEvidenceStrength
from dibble.models.observations import LearnerObservation, ObservationSupportLevel, ObservationTaskType
from dibble.models.profile import LearnerProfile
from dibble.models.remediation import RemediationWorkflowSession, RemediationWorkflowStep
from dibble.services.knowledge_state_migration import KnowledgeStateMigrator


def _clamp(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _blend(prior: float, observed: float, weight: float) -> float:
    return (prior * (1.0 - weight)) + (observed * weight)


@dataclass(frozen=True, slots=True)
class ObservationProfileUpdateResult:
    profile: LearnerProfile
    applied: bool
    inferred_mastery: float | None = None
    evidence_strength: SocraticEvidenceStrength | None = None
    kc_mastery_updates: dict[str, float] | None = None
    lo_mastery_updates: dict[str, float] | None = None
    propagated_kc_mastery_updates: dict[str, float] | None = None
    propagated_lo_mastery_updates: dict[str, float] | None = None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class RemediationProgressDecision:
    decision: str = "advance"
    rationale: str | None = None
    matched_observation_count: int = 0
    average_observed_mastery: float | None = None
    target_kc_ids: list[str] | None = None
    hold_step_index: int | None = None


@dataclass(slots=True)
class ObservationProfileUpdater:
    knowledge_state_migrator: KnowledgeStateMigrator | None = None

    def apply(self, profile: LearnerProfile, observation: LearnerObservation) -> ObservationProfileUpdateResult:
        if not self._eligible_for_writeback(observation):
            return ObservationProfileUpdateResult(
                profile=profile,
                applied=False,
                kc_mastery_updates={},
                lo_mastery_updates={},
                propagated_kc_mastery_updates={},
                propagated_lo_mastery_updates={},
                rationale="Observation was not specific enough for mastery writeback.",
            )

        inferred_mastery = self._infer_observed_mastery(observation)
        evidence_strength = self._evidence_strength(observation=observation, inferred_mastery=inferred_mastery)
        evidence_weight = self._evidence_weight(
            observation=observation,
            evidence_strength=evidence_strength,
            inferred_mastery=inferred_mastery,
        )
        new_kc_mastery = dict(profile.knowledge_state.kc_mastery)
        new_lo_mastery = dict(profile.knowledge_state.lo_mastery)

        kc_updates = self._apply_mastery_updates(
            current_values=new_kc_mastery,
            target_ids=observation.target_kc_ids,
            inferred_mastery=inferred_mastery,
            evidence_weight=evidence_weight,
            evidence_strength=evidence_strength,
        )
        lo_updates = self._apply_mastery_updates(
            current_values=new_lo_mastery,
            target_ids=observation.target_lo_ids,
            inferred_mastery=inferred_mastery,
            evidence_weight=evidence_weight,
            evidence_strength=evidence_strength,
        )
        migration_result = (
            self.knowledge_state_migrator.migrate(
                kc_mastery=new_kc_mastery,
                lo_mastery=new_lo_mastery,
                direct_kc_updates=kc_updates,
                direct_lo_updates=lo_updates,
                evidence_strength=evidence_strength,
            )
            if self.knowledge_state_migrator is not None
            else None
        )
        updated_profile = profile.model_copy(
            update={
                "knowledge_state": profile.knowledge_state.model_copy(
                    update={
                        "kc_mastery": new_kc_mastery,
                        "lo_mastery": new_lo_mastery,
                        "last_updated": datetime.now(timezone.utc),
                    }
                ),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return ObservationProfileUpdateResult(
            profile=updated_profile,
            applied=bool(kc_updates or lo_updates),
            inferred_mastery=inferred_mastery,
            evidence_strength=evidence_strength,
            kc_mastery_updates=kc_updates,
            lo_mastery_updates=lo_updates,
            propagated_kc_mastery_updates=(migration_result.kc_mastery_updates if migration_result is not None else {}),
            propagated_lo_mastery_updates=(migration_result.lo_mastery_updates if migration_result is not None else {}),
            rationale=self._writeback_rationale(observation=observation, inferred_mastery=inferred_mastery),
        )

    def evaluate_remediation_progress(
        self,
        *,
        session: RemediationWorkflowSession,
        observations: list[LearnerObservation],
    ) -> RemediationProgressDecision:
        current_index = session.current_step_index
        if current_index is None or current_index <= 0 or current_index >= len(session.steps):
            return RemediationProgressDecision()

        current_step = session.steps[current_index]
        if current_step.phase not in {"bridge", "return"}:
            return RemediationProgressDecision()

        prior_step = session.steps[current_index - 1]
        matched_observations = self._matching_remediation_observations(
            session=session,
            step=prior_step,
            observations=observations,
        )
        if not matched_observations:
            return RemediationProgressDecision()

        scores = [self._infer_observed_mastery(observation) for observation in matched_observations[:3]]
        average_score = round(sum(scores) / len(scores), 2) if scores else None
        strongest_evidence = max(
            (self._evidence_strength(observation=observation, inferred_mastery=score) for observation, score in zip(matched_observations, scores)),
            default=SocraticEvidenceStrength.insufficient,
            key=self._evidence_rank,
        )
        if average_score is None or (
            average_score < 0.58 and strongest_evidence != SocraticEvidenceStrength.demonstrated
        ):
            decision = "hold_repair_target" if prior_step.phase != "bridge" else "hold_bridge_target"
            rationale = (
                "Recent remediation evidence still looks weak, so the workflow should hold on the current repair target "
                "before advancing back toward transfer."
            )
            return RemediationProgressDecision(
                decision=decision,
                rationale=rationale,
                matched_observation_count=len(matched_observations),
                average_observed_mastery=average_score,
                target_kc_ids=prior_step.target_kc_ids,
                hold_step_index=current_index - 1,
            )
        return RemediationProgressDecision(
            decision="advance",
            rationale="Recent remediation evidence was strong enough to allow the workflow to advance.",
            matched_observation_count=len(matched_observations),
            average_observed_mastery=average_score,
            target_kc_ids=prior_step.target_kc_ids,
        )

    def _eligible_for_writeback(self, observation: LearnerObservation) -> bool:
        if observation.task_type not in {ObservationTaskType.practice, ObservationTaskType.remediation}:
            return False
        if not observation.target_kc_ids and not observation.target_lo_ids:
            return False
        if observation.learning_session_id is None and observation.generation_id is None:
            return False
        return True

    def _infer_observed_mastery(self, observation: LearnerObservation) -> float:
        completion_signal = 0.44 if observation.completed else 0.12
        confidence_signal = observation.confidence * 0.22
        support_signal = {
            ObservationSupportLevel.low: 0.12,
            ObservationSupportLevel.medium: 0.08,
            ObservationSupportLevel.high: 0.03,
        }[observation.support_level]
        hint_penalty = min(0.18, observation.hints_used * 0.04)
        error_penalty = min(0.24, observation.error_count * 0.06)
        pause_penalty = min(0.1, observation.pause_count * 0.02)
        pace_adjustment = self._pace_adjustment(observation)
        score = 0.16 + completion_signal + confidence_signal + support_signal + pace_adjustment
        score -= hint_penalty + error_penalty + pause_penalty
        return round(_clamp(score, lower=0.05, upper=0.95), 2)

    def _pace_adjustment(self, observation: LearnerObservation) -> float:
        if observation.expected_duration_ms is None or observation.expected_duration_ms <= 0:
            return 0.0
        ratio = observation.response_time_ms / observation.expected_duration_ms
        if ratio <= 0.9:
            return 0.05
        if ratio <= 1.3:
            return 0.02
        if ratio >= 2.0:
            return -0.05
        if ratio >= 1.6:
            return -0.03
        return 0.0

    def _evidence_strength(
        self,
        *,
        observation: LearnerObservation,
        inferred_mastery: float,
    ) -> SocraticEvidenceStrength:
        if (
            observation.completed
            and observation.error_count == 0
            and observation.hints_used <= 1
            and inferred_mastery >= 0.68
        ):
            return SocraticEvidenceStrength.demonstrated
        if observation.completed and observation.error_count <= 2 and inferred_mastery >= 0.42:
            return SocraticEvidenceStrength.emerging
        return SocraticEvidenceStrength.insufficient

    def _evidence_weight(
        self,
        *,
        observation: LearnerObservation,
        evidence_strength: SocraticEvidenceStrength,
        inferred_mastery: float,
    ) -> float:
        base_weight = {
            SocraticEvidenceStrength.insufficient: 0.14,
            SocraticEvidenceStrength.emerging: 0.24,
            SocraticEvidenceStrength.demonstrated: 0.34,
        }[evidence_strength]
        support_factor = {
            ObservationSupportLevel.low: 1.0,
            ObservationSupportLevel.medium: 0.9,
            ObservationSupportLevel.high: 0.78,
        }[observation.support_level]
        completion_bonus = 0.04 if observation.completed else 0.0
        confidence_bonus = max(0.0, observation.confidence - 0.5) * 0.06
        mastery_bonus = max(0.0, inferred_mastery - 0.6) * 0.08
        return min(0.42, (base_weight * support_factor) + completion_bonus + confidence_bonus + mastery_bonus)

    def _apply_mastery_updates(
        self,
        *,
        current_values: dict[str, float],
        target_ids: list[str],
        inferred_mastery: float,
        evidence_weight: float,
        evidence_strength: SocraticEvidenceStrength,
    ) -> dict[str, float]:
        updates: dict[str, float] = {}
        for target_id in target_ids:
            prior = current_values.get(target_id)
            if prior is None:
                updated_value = inferred_mastery
            else:
                adjusted_weight = evidence_weight
                if inferred_mastery < prior:
                    adjusted_weight *= {
                        SocraticEvidenceStrength.demonstrated: 0.28,
                        SocraticEvidenceStrength.emerging: 0.54,
                        SocraticEvidenceStrength.insufficient: 0.86,
                    }[evidence_strength]
                updated_value = _blend(prior, inferred_mastery, adjusted_weight)
            rounded = round(_clamp(updated_value), 2)
            current_values[target_id] = rounded
            updates[target_id] = rounded
        return updates

    def _matching_remediation_observations(
        self,
        *,
        session: RemediationWorkflowSession,
        step: RemediationWorkflowStep,
        observations: list[LearnerObservation],
    ) -> list[LearnerObservation]:
        matches: list[LearnerObservation] = []
        for observation in observations:
            if observation.learning_session_id != session.session_id:
                continue
            if observation.task_type not in {ObservationTaskType.practice, ObservationTaskType.remediation}:
                continue
            if step.generated_content_id is not None and observation.generation_id == step.generated_content_id:
                matches.append(observation)
                continue
            if set(observation.target_kc_ids).intersection(step.target_kc_ids):
                matches.append(observation)
        return matches

    def _evidence_rank(self, evidence_strength: SocraticEvidenceStrength) -> int:
        return {
            SocraticEvidenceStrength.insufficient: 0,
            SocraticEvidenceStrength.emerging: 1,
            SocraticEvidenceStrength.demonstrated: 2,
        }[evidence_strength]

    def _writeback_rationale(self, *, observation: LearnerObservation, inferred_mastery: float) -> str:
        if observation.task_type == ObservationTaskType.remediation:
            return (
                f"Linked remediation evidence suggested observed mastery around {inferred_mastery:.2f}, "
                "so the repair target was blended back into KC and LO mastery."
            )
        return (
            f"Linked practice evidence suggested observed mastery around {inferred_mastery:.2f}, "
            "so the active target was blended back into KC and LO mastery."
        )
