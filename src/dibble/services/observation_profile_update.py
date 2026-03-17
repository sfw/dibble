from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.models.assessment import SocraticEvidenceStrength
from dibble.models.generation import GenerationRequest
from dibble.models.observations import LearnerObservation, ObservationSupportLevel, ObservationTaskType
from dibble.models.profile import LearnerProfile, OrdinaryMasterySummary
from dibble.models.remediation import RemediationWorkflowSession, RemediationWorkflowStep
from dibble.services.knowledge_state_migration import KnowledgeStateMigrator
from dibble.services.ordinary_mastery_profiles import OrdinaryMasterySignalService


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
    linkage_source: str | None = None
    matched_observation_count: int = 0
    average_recent_observed_mastery: float | None = None
    evidence_confidence: float = 0.0
    kc_mastery_updates: dict[str, float] | None = None
    lo_mastery_updates: dict[str, float] | None = None
    propagated_kc_mastery_updates: dict[str, float] | None = None
    propagated_lo_mastery_updates: dict[str, float] | None = None
    durable_mastery_signal: str = "insufficient"
    durable_mastery_source: str = "insufficient"
    durable_mastery_confidence: float = 0.0
    durable_mastery_matched_observation_count: int = 0
    durable_mastery_average_observed_mastery: float | None = None
    durable_mastery_low_support_success_rate: float = 0.0
    durable_mastery_high_support_dependency_rate: float = 0.0
    durable_mastery_rationale: str | None = None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class RemediationProgressDecision:
    decision: str = "advance"
    rationale: str | None = None
    matched_observation_count: int = 0
    evidence_confidence: float = 0.0
    average_observed_mastery: float | None = None
    low_support_success_count: int = 0
    target_kc_ids: list[str] | None = None
    hold_step_index: int | None = None


@dataclass(frozen=True, slots=True)
class ProgressionEvidenceDecision:
    decision: str = "monitor"
    rationale: str | None = None
    matched_observation_count: int = 0
    matched_assessment_count: int = 0
    average_observed_mastery: float | None = None
    average_assessment_mastery: float | None = None
    confidence: float = 0.0
    target_kc_ids: list[str] | None = None


@dataclass(slots=True)
class ObservationProfileUpdater:
    knowledge_state_migrator: KnowledgeStateMigrator | None = None
    ordinary_mastery_signal_service: OrdinaryMasterySignalService | None = None

    def apply(
        self,
        profile: LearnerProfile,
        observation: LearnerObservation,
        *,
        recent_observations: list[LearnerObservation] | None = None,
    ) -> ObservationProfileUpdateResult:
        linkage_source = self._writeback_linkage_source(observation)
        if linkage_source is None:
            return ObservationProfileUpdateResult(
                profile=profile,
                applied=False,
                linkage_source=None,
                matched_observation_count=0,
                average_recent_observed_mastery=None,
                evidence_confidence=0.0,
                kc_mastery_updates={},
                lo_mastery_updates={},
                propagated_kc_mastery_updates={},
                propagated_lo_mastery_updates={},
                rationale="Observation was not specific enough for mastery writeback.",
            )

        inferred_mastery = self._infer_observed_mastery(observation)
        evidence_strength = self._evidence_strength(observation=observation, inferred_mastery=inferred_mastery)
        durable_mastery = self._durable_mastery_summary(profile=profile, observation=observation)
        supporting_observations = self._supporting_observations(
            observation=observation,
            observations=recent_observations or [observation],
        )
        observation_scores = [self._infer_observed_mastery(item) for item in supporting_observations]
        average_recent_mastery = (
            round(sum(observation_scores) / len(observation_scores), 2)
            if observation_scores
            else None
        )
        evidence_weight = self._evidence_weight(
            observation=observation,
            evidence_strength=evidence_strength,
            inferred_mastery=inferred_mastery,
            linkage_source=linkage_source,
            matched_observation_count=len(supporting_observations),
            average_recent_mastery=average_recent_mastery,
            low_support_success_count=self._low_support_success_count(supporting_observations),
            repeated_high_support_success_count=self._repeated_high_support_success_count(supporting_observations),
            durable_mastery=durable_mastery,
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
            linkage_source=linkage_source,
            matched_observation_count=len(supporting_observations),
            average_recent_observed_mastery=average_recent_mastery,
            evidence_confidence=self._evidence_confidence(
                matched_observation_count=len(supporting_observations),
                matched_assessment_count=0,
            ),
            kc_mastery_updates=kc_updates,
            lo_mastery_updates=lo_updates,
            propagated_kc_mastery_updates=(migration_result.kc_mastery_updates if migration_result is not None else {}),
            propagated_lo_mastery_updates=(migration_result.lo_mastery_updates if migration_result is not None else {}),
            durable_mastery_signal=durable_mastery.signal,
            durable_mastery_source=durable_mastery.source,
            durable_mastery_confidence=durable_mastery.confidence,
            durable_mastery_matched_observation_count=durable_mastery.matched_observation_count,
            durable_mastery_average_observed_mastery=durable_mastery.average_observed_mastery,
            durable_mastery_low_support_success_rate=durable_mastery.low_support_success_rate,
            durable_mastery_high_support_dependency_rate=durable_mastery.high_support_dependency_rate,
            durable_mastery_rationale=durable_mastery.rationale,
            rationale=self._writeback_rationale(
                observation=observation,
                inferred_mastery=inferred_mastery,
                matched_observation_count=len(supporting_observations),
            ),
        )

    def evaluate_progression_evidence(
        self,
        *,
        request: GenerationRequest,
        observations: list[LearnerObservation],
        assessment_payloads: list[dict[str, object]],
        session_sequence_action: str = "monitor",
        session_rationale: str | None = None,
    ) -> ProgressionEvidenceDecision:
        if request.learning_session_id is None or (not request.target_kc_ids and not request.target_lo_ids):
            return ProgressionEvidenceDecision()

        matched_observations = self._matching_progression_observations(
            request=request,
            observations=observations,
        )
        matched_assessments = self._matching_assessment_payloads(
            request=request,
            assessment_payloads=assessment_payloads,
        )
        if not matched_observations and not matched_assessments:
            return ProgressionEvidenceDecision()

        observation_scores = [self._infer_observed_mastery(item) for item in matched_observations]
        average_observed_mastery = (
            round(sum(observation_scores) / len(observation_scores), 2)
            if observation_scores
            else None
        )
        assessment_scores = [self._assessment_mastery_score(payload) for payload in matched_assessments]
        average_assessment_mastery = (
            round(sum(assessment_scores) / len(assessment_scores), 2)
            if assessment_scores
            else None
        )
        strong_assessment = any(
            self._assessment_is_transfer_ready(payload, score=score)
            for payload, score in zip(matched_assessments, assessment_scores)
        )
        low_support_success_count = sum(
            1 for observation, score in zip(matched_observations, observation_scores) if self._is_low_support_success(observation, score)
        )
        repeated_high_support_success_count = self._repeated_high_support_success_count(matched_observations)
        hold_decision = self._progression_hold_decision(session_sequence_action=session_sequence_action)
        session_transfer = session_sequence_action == "attempt_transfer"
        stage_requires_stronger_transfer = hold_decision in {"hold_repair_target", "hold_bridge_target"}
        confidence = self._evidence_confidence(
            matched_observation_count=len(matched_observations),
            matched_assessment_count=len(matched_assessments),
        )
        observation_transfer_threshold = 0.72 if stage_requires_stronger_transfer else 0.66
        transfer_ready = strong_assessment or (
            average_observed_mastery is not None
            and average_observed_mastery >= observation_transfer_threshold
            and low_support_success_count >= (2 if stage_requires_stronger_transfer else 1)
        )

        if transfer_ready or (
            session_transfer
            and average_observed_mastery is not None
            and average_observed_mastery >= 0.66
            and low_support_success_count >= 1
            and repeated_high_support_success_count == 0
        ):
            return ProgressionEvidenceDecision(
                decision="attempt_transfer",
                rationale=(
                    f"Recent same-session evidence on {request.learning_session_id} suggests the learner is ready to test transfer "
                    "before another support step."
                ),
                matched_observation_count=len(matched_observations),
                matched_assessment_count=len(matched_assessments),
                average_observed_mastery=average_observed_mastery,
                average_assessment_mastery=average_assessment_mastery,
                confidence=confidence,
                target_kc_ids=request.target_kc_ids,
            )

        weak_observation_signal = average_observed_mastery is not None and average_observed_mastery < (
            0.62 if stage_requires_stronger_transfer else 0.58
        )
        weak_assessment_signal = bool(matched_assessments) and not strong_assessment
        if (
            hold_decision is not None
            or weak_observation_signal
            or weak_assessment_signal
            or repeated_high_support_success_count > 0
            or (stage_requires_stronger_transfer and low_support_success_count < 2)
        ):
            decision = hold_decision or "hold_target"
            rationale = self._progression_hold_rationale(
                learning_session_id=request.learning_session_id,
                decision=decision,
                session_rationale=session_rationale,
            )
            return ProgressionEvidenceDecision(
                decision=decision,
                rationale=rationale,
                matched_observation_count=len(matched_observations),
                matched_assessment_count=len(matched_assessments),
                average_observed_mastery=average_observed_mastery,
                average_assessment_mastery=average_assessment_mastery,
                confidence=confidence,
                target_kc_ids=request.target_kc_ids,
            )

        return ProgressionEvidenceDecision(
            decision="monitor",
            rationale=(
                f"Recent same-session evidence on {request.learning_session_id} is mixed, so the backend should keep monitoring the current target."
            ),
            matched_observation_count=len(matched_observations),
            matched_assessment_count=len(matched_assessments),
            average_observed_mastery=average_observed_mastery,
            average_assessment_mastery=average_assessment_mastery,
            confidence=confidence,
            target_kc_ids=request.target_kc_ids,
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
        evidence_confidence = self._evidence_confidence(
            matched_observation_count=len(matched_observations),
            matched_assessment_count=0,
        )
        low_support_success_count = sum(
            1
            for observation, score in zip(matched_observations, scores)
            if self._is_low_support_success(observation, score)
        )
        medium_or_low_support_success_count = sum(
            1
            for observation, score in zip(matched_observations, scores)
            if observation.completed
            and observation.support_level in {ObservationSupportLevel.low, ObservationSupportLevel.medium}
            and observation.error_count <= 1
            and observation.hints_used <= 1
            and score >= 0.62
        )
        repeated_high_support_success_count = self._repeated_high_support_success_count(matched_observations)
        strongest_evidence = max(
            (self._evidence_strength(observation=observation, inferred_mastery=score) for observation, score in zip(matched_observations, scores)),
            default=SocraticEvidenceStrength.insufficient,
            key=self._evidence_rank,
        )
        if self._should_hold_remediation_step(
            current_step=session.steps[current_index],
            prior_step=prior_step,
            average_score=average_score,
            strongest_evidence=strongest_evidence,
            low_support_success_count=low_support_success_count,
            medium_or_low_support_success_count=medium_or_low_support_success_count,
            repeated_high_support_success_count=repeated_high_support_success_count,
        ):
            decision = "hold_repair_target" if prior_step.phase != "bridge" else "hold_bridge_target"
            rationale = self._remediation_hold_rationale(
                current_step=session.steps[current_index],
                prior_step=prior_step,
                average_score=average_score,
                low_support_success_count=low_support_success_count,
                medium_or_low_support_success_count=medium_or_low_support_success_count,
                repeated_high_support_success_count=repeated_high_support_success_count,
            )
            return RemediationProgressDecision(
                decision=decision,
                rationale=rationale,
                matched_observation_count=len(matched_observations),
                evidence_confidence=evidence_confidence,
                average_observed_mastery=average_score,
                low_support_success_count=low_support_success_count,
                target_kc_ids=prior_step.target_kc_ids,
                hold_step_index=current_index - 1,
            )
        return RemediationProgressDecision(
            decision="advance",
            rationale=self._remediation_advance_rationale(
                current_step=session.steps[current_index],
                prior_step=prior_step,
                low_support_success_count=low_support_success_count,
                medium_or_low_support_success_count=medium_or_low_support_success_count,
            ),
            matched_observation_count=len(matched_observations),
            evidence_confidence=evidence_confidence,
            average_observed_mastery=average_score,
            low_support_success_count=low_support_success_count,
            target_kc_ids=prior_step.target_kc_ids,
        )

    def _writeback_linkage_source(self, observation: LearnerObservation) -> str | None:
        if observation.task_type not in {ObservationTaskType.practice, ObservationTaskType.remediation}:
            return None
        if not observation.target_kc_ids and not observation.target_lo_ids:
            return None
        if observation.generation_id is not None:
            return "generation_linked"
        if observation.learning_session_id is not None:
            return "session_linked"
        if (
            observation.observed_content_type in {"practice_problem", "remedial_micro_module"}
            and observation.completed
            and observation.support_level != ObservationSupportLevel.high
            and observation.error_count <= 2
            and observation.confidence >= 0.55
        ):
            return "target_scoped_strong_observation"
        return None

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
        linkage_source: str,
        matched_observation_count: int,
        average_recent_mastery: float | None,
        low_support_success_count: int,
        repeated_high_support_success_count: int,
        durable_mastery: OrdinaryMasterySummary,
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
        linkage_factor = {
            "generation_linked": 1.0,
            "session_linked": 0.92,
            "target_scoped_strong_observation": 0.8,
        }.get(linkage_source, 0.75)
        completion_bonus = 0.04 if observation.completed else 0.0
        confidence_bonus = max(0.0, observation.confidence - 0.5) * 0.06
        mastery_bonus = max(0.0, inferred_mastery - 0.6) * 0.08
        consistency_bonus = 0.04 if (
            matched_observation_count >= 2
            and average_recent_mastery is not None
            and average_recent_mastery >= 0.62
        ) else 0.0
        support_dependence_penalty = 0.04 if repeated_high_support_success_count >= 2 else 0.0
        independent_consistency_bonus = 0.05 if (
            low_support_success_count >= 2
            and matched_observation_count >= 2
            and average_recent_mastery is not None
            and average_recent_mastery >= 0.68
        ) else 0.0
        if repeated_high_support_success_count >= 1 and observation.support_level == ObservationSupportLevel.high:
            support_dependence_penalty += 0.02
        durable_adjustment = 0.0
        if durable_mastery.signal == "durable_mastery":
            durable_adjustment += 0.04 if observation.support_level == ObservationSupportLevel.low else 0.01
        elif durable_mastery.signal == "emerging_mastery":
            durable_adjustment += 0.02 if observation.support_level != ObservationSupportLevel.high else 0.0
        elif durable_mastery.signal == "support_dependent":
            durable_adjustment -= 0.04 if observation.support_level == ObservationSupportLevel.high else 0.02
        elif durable_mastery.signal == "fragile" and observation.support_level != ObservationSupportLevel.low:
            durable_adjustment -= 0.03
        if durable_mastery.low_support_success_rate >= 0.6 and observation.support_level == ObservationSupportLevel.low:
            durable_adjustment += 0.01
        if durable_mastery.high_support_dependency_rate >= 0.6 and observation.support_level == ObservationSupportLevel.high:
            durable_adjustment -= 0.02
        durable_adjustment *= 0.6 + (durable_mastery.confidence * 0.4)
        return round(
            _clamp(
                (base_weight * support_factor * linkage_factor)
                + completion_bonus
                + confidence_bonus
                + mastery_bonus
                + consistency_bonus
                + independent_consistency_bonus
                - support_dependence_penalty
                + durable_adjustment,
                lower=0.08,
                upper=0.42,
            ),
            4,
        )

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

    def _supporting_observations(
        self,
        *,
        observation: LearnerObservation,
        observations: list[LearnerObservation],
    ) -> list[LearnerObservation]:
        matches = [
            item
            for item in observations
            if item.task_type in {ObservationTaskType.practice, ObservationTaskType.remediation}
            and self._targets_overlap(
                target_kc_ids=observation.target_kc_ids,
                observed_kc_ids=item.target_kc_ids,
                target_lo_ids=observation.target_lo_ids,
                observed_lo_ids=item.target_lo_ids,
            )
            and self._shares_link(anchor=observation, candidate=item)
        ]
        return matches[:3]

    def _matching_progression_observations(
        self,
        *,
        request: GenerationRequest,
        observations: list[LearnerObservation],
    ) -> list[LearnerObservation]:
        matches = [
            observation
            for observation in observations
            if observation.task_type in {ObservationTaskType.practice, ObservationTaskType.remediation}
            and observation.learning_session_id == request.learning_session_id
            and self._targets_overlap(
                target_kc_ids=request.target_kc_ids,
                observed_kc_ids=observation.target_kc_ids,
                target_lo_ids=request.target_lo_ids,
                observed_lo_ids=observation.target_lo_ids,
            )
        ]
        return matches[:3]

    def _matching_assessment_payloads(
        self,
        *,
        request: GenerationRequest,
        assessment_payloads: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        matches = [
            payload
            for payload in assessment_payloads
            if payload.get("learning_session_id") == request.learning_session_id
            and self._targets_overlap(
                target_kc_ids=request.target_kc_ids,
                observed_kc_ids=self._string_list(payload.get("target_kc_ids")),
                target_lo_ids=request.target_lo_ids,
                observed_lo_ids=self._string_list(payload.get("target_lo_ids")),
            )
        ]
        return matches[:2]

    def _shares_link(self, *, anchor: LearnerObservation, candidate: LearnerObservation) -> bool:
        if anchor.learning_session_id is not None and candidate.learning_session_id == anchor.learning_session_id:
            return True
        if anchor.generation_id is not None and candidate.generation_id == anchor.generation_id:
            return True
        return False

    def _targets_overlap(
        self,
        *,
        target_kc_ids: list[str],
        observed_kc_ids: list[str],
        target_lo_ids: list[str],
        observed_lo_ids: list[str],
    ) -> bool:
        if set(target_kc_ids).intersection(observed_kc_ids):
            return True
        if set(target_lo_ids).intersection(observed_lo_ids):
            return True
        return False

    def _repeated_high_support_success_count(self, observations: list[LearnerObservation]) -> int:
        return sum(
            1
            for observation in observations
            if observation.completed
            and observation.support_level == ObservationSupportLevel.high
            and observation.hints_used >= 2
        )

    def _low_support_success_count(self, observations: list[LearnerObservation]) -> int:
        return sum(
            1
            for observation in observations
            if self._is_low_support_success(
                observation,
                self._infer_observed_mastery(observation),
            )
        )

    def _is_low_support_success(self, observation: LearnerObservation, score: float) -> bool:
        return (
            observation.completed
            and observation.support_level == ObservationSupportLevel.low
            and observation.error_count <= 1
            and observation.hints_used <= 1
            and score >= 0.62
        )

    def _should_hold_remediation_step(
        self,
        *,
        current_step: RemediationWorkflowStep,
        prior_step: RemediationWorkflowStep,
        average_score: float | None,
        strongest_evidence: SocraticEvidenceStrength,
        low_support_success_count: int,
        medium_or_low_support_success_count: int,
        repeated_high_support_success_count: int,
    ) -> bool:
        if average_score is None:
            return True
        if repeated_high_support_success_count > 0:
            return True
        if prior_step.phase == "bridge":
            return not (
                average_score >= 0.68
                and low_support_success_count >= 1
                and strongest_evidence != SocraticEvidenceStrength.insufficient
            )
        if current_step.phase == "return":
            return not (
                average_score >= 0.64
                and medium_or_low_support_success_count >= 1
                and strongest_evidence != SocraticEvidenceStrength.insufficient
            )
        return not (
            average_score >= 0.6
            and (
                medium_or_low_support_success_count >= 1
                or strongest_evidence == SocraticEvidenceStrength.demonstrated
            )
        )

    def _remediation_hold_rationale(
        self,
        *,
        current_step: RemediationWorkflowStep,
        prior_step: RemediationWorkflowStep,
        average_score: float | None,
        low_support_success_count: int,
        medium_or_low_support_success_count: int,
        repeated_high_support_success_count: int,
    ) -> str:
        if repeated_high_support_success_count > 0:
            return (
                "Recent remediation success is still too support-heavy, so the workflow should stay on the current repair path "
                "before advancing."
            )
        if prior_step.phase == "bridge":
            return (
                f"Recent bridge evidence averaged {average_score:.2f} with {low_support_success_count} low-support success signal(s), "
                "so the workflow should hold the bridge target before the final transfer return."
            )
        if current_step.phase == "return":
            return (
                f"Recent repair evidence averaged {average_score:.2f} with {medium_or_low_support_success_count} medium-or-low-support success signal(s), "
                "so the workflow should stay on the repair target before returning to the target KC."
            )
        return (
            f"Recent repair evidence averaged {average_score:.2f}, so the workflow should hold on the current repair target "
            "before advancing."
        )

    def _remediation_advance_rationale(
        self,
        *,
        current_step: RemediationWorkflowStep,
        prior_step: RemediationWorkflowStep,
        low_support_success_count: int,
        medium_or_low_support_success_count: int,
    ) -> str:
        if prior_step.phase == "bridge":
            return (
                f"Recent bridge evidence included {low_support_success_count} low-support success signal(s), "
                "so the workflow can return to the target for transfer."
            )
        if current_step.phase == "return":
            return (
                f"Recent repair evidence included {medium_or_low_support_success_count} medium-or-low-support success signal(s), "
                "so the workflow can return to the target."
            )
        return "Recent remediation evidence was strong enough to allow the workflow to advance."

    def _progression_hold_decision(self, *, session_sequence_action: str) -> str | None:
        if session_sequence_action in {"hold_target", "hold_repair_target", "hold_bridge_target"}:
            return session_sequence_action
        return None

    def _progression_hold_rationale(
        self,
        *,
        learning_session_id: str | None,
        decision: str,
        session_rationale: str | None,
    ) -> str:
        if session_rationale is not None:
            return session_rationale
        session_fragment = learning_session_id or "the active session"
        if decision == "hold_bridge_target":
            return (
                f"Recent same-session evidence on {session_fragment} still needs one more guided bridge step "
                "before the backend should return to transfer."
            )
        if decision == "hold_repair_target":
            return (
                f"Recent same-session evidence on {session_fragment} still looks support-heavy or incomplete on the repair target, "
                "so the backend should stay in repair before returning to the target."
            )
        return (
            f"Recent same-session evidence on {session_fragment} still looks support-heavy or incomplete, "
            "so the backend should hold on the current target before transfer."
        )

    def _durable_mastery_summary(
        self,
        *,
        profile: LearnerProfile,
        observation: LearnerObservation,
    ) -> OrdinaryMasterySummary:
        if self.ordinary_mastery_signal_service is None:
            return OrdinaryMasterySummary()
        if not observation.target_kc_ids and not observation.target_lo_ids:
            return OrdinaryMasterySummary()
        return self.ordinary_mastery_signal_service.latest_for_student(
            student_id=profile.student_id,
            target_kc_ids=observation.target_kc_ids,
            target_lo_ids=observation.target_lo_ids,
        )

    def _assessment_mastery_score(self, payload: dict[str, object]) -> float:
        inferred_mastery = payload.get("inferred_mastery")
        if isinstance(inferred_mastery, (int, float)):
            return round(_clamp(float(inferred_mastery)), 2)
        evidence_score = payload.get("evidence_score")
        if isinstance(evidence_score, (int, float)):
            return round(_clamp(float(evidence_score)), 2)
        return 0.0

    def _assessment_is_transfer_ready(self, payload: dict[str, object], *, score: float) -> bool:
        evidence_strength = str(payload.get("evidence_strength", "insufficient"))
        return evidence_strength == "demonstrated" or score >= 0.72

    def _evidence_confidence(self, *, matched_observation_count: int, matched_assessment_count: int) -> float:
        return round(
            min(0.9, 0.28 + (matched_observation_count * 0.14) + (matched_assessment_count * 0.2)),
            2,
        )

    def _evidence_rank(self, evidence_strength: SocraticEvidenceStrength) -> int:
        return {
            SocraticEvidenceStrength.insufficient: 0,
            SocraticEvidenceStrength.emerging: 1,
            SocraticEvidenceStrength.demonstrated: 2,
        }[evidence_strength]

    def _writeback_rationale(
        self,
        *,
        observation: LearnerObservation,
        inferred_mastery: float,
        matched_observation_count: int,
    ) -> str:
        linkage_source = self._writeback_linkage_source(observation)
        linkage_fragment = {
            "generation_linked": "linked generation evidence",
            "session_linked": "same-session evidence",
            "target_scoped_strong_observation": "strong target-scoped observation evidence",
        }.get(linkage_source, "observation evidence")
        evidence_window = (
            f" across {matched_observation_count} recent linked observations"
            if matched_observation_count > 1
            else ""
        )
        if observation.task_type == ObservationTaskType.remediation:
            return (
                f"{linkage_fragment.capitalize()} suggested observed mastery around {inferred_mastery:.2f}, "
                f"so the repair target was blended back into KC and LO mastery{evidence_window}."
            )
        return (
            f"{linkage_fragment.capitalize()} suggested observed mastery around {inferred_mastery:.2f}, "
            f"so the active target was blended back into KC and LO mastery{evidence_window}."
        )

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None]
