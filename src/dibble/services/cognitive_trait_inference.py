from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.observations import LearnerObservation
from dibble.models.profile import CognitiveTraitScore, LearnerTraitProfileSummary
from dibble.services.learning_trait_profiles import LearnerTraitProfileSignalService


@dataclass(slots=True)
class CognitiveTraitInferenceService:
    trait_profile_signal_service: LearnerTraitProfileSignalService | None = None

    def infer(
        self,
        *,
        student_id: UUID | None = None,
        observations: list[LearnerObservation],
        existing_traits: dict[str, CognitiveTraitScore],
    ) -> dict[str, CognitiveTraitScore]:
        if not observations:
            return existing_traits

        updates: dict[str, CognitiveTraitScore] = {}
        processing_speed = self._processing_speed(observations)
        working_memory = self._working_memory(observations)
        spatial_reasoning = self._spatial_reasoning(observations)

        for name, inferred in (
            ("processing_speed", processing_speed),
            ("working_memory", working_memory),
            ("spatial_reasoning", spatial_reasoning),
        ):
            if inferred is None:
                continue
            updates[name] = self._merge(existing_traits.get(name), inferred)

        durable_profile = (
            self.trait_profile_signal_service.latest_for_student(student_id=student_id)
            if self.trait_profile_signal_service is not None and student_id is not None
            else LearnerTraitProfileSummary()
        )
        challenge_index = self._current_challenge_index(observations)
        evidence = self._current_trait_evidence(observations)
        if self._should_apply_durable_profile(
            durable_profile,
            challenge_index=challenge_index,
            evidence=evidence,
        ):
            for name, inferred in (
                ("processing_speed", durable_profile.processing_speed),
                ("working_memory", durable_profile.working_memory),
                ("spatial_reasoning", durable_profile.spatial_reasoning),
            ):
                if inferred is None:
                    continue
                reliability = self._trait_reliability(
                    profile=durable_profile, name=name
                )
                if not self._should_apply_durable_trait(
                    profile=durable_profile,
                    name=name,
                    reliability=reliability,
                    challenge_index=challenge_index,
                    evidence=evidence,
                ):
                    continue
                updates[name] = self._merge_with_durable(
                    name=name,
                    current=updates.get(name) or existing_traits.get(name),
                    durable=inferred,
                    profile=durable_profile,
                    reliability=reliability,
                    challenge_index=challenge_index,
                    evidence=evidence,
                )

        return {**existing_traits, **updates}

    def _processing_speed(
        self, observations: list[LearnerObservation]
    ) -> CognitiveTraitScore | None:
        ratios = [
            observation.response_time_ms
            / max(1, observation.expected_duration_ms or 15000)
            for observation in observations
        ]
        avg_ratio = sum(ratios) / len(ratios)
        completion_rate = sum(
            1 for observation in observations if observation.completed
        ) / len(observations)
        avg_pause_count = sum(
            observation.pause_count for observation in observations
        ) / len(observations)
        score = (
            0.7
            - max(avg_ratio - 1.0, 0.0) * 0.35
            + (completion_rate * 0.2)
            - min(avg_pause_count, 4.0) * 0.03
        )
        confidence = min(0.82, 0.35 + (len(observations) * 0.08))
        return CognitiveTraitScore(
            value=round(min(0.95, max(0.1, score)), 2), confidence=round(confidence, 2)
        )

    def _working_memory(
        self, observations: list[LearnerObservation]
    ) -> CognitiveTraitScore | None:
        avg_hints = sum(observation.hints_used for observation in observations) / len(
            observations
        )
        avg_errors = sum(observation.error_count for observation in observations) / len(
            observations
        )
        avg_switches = sum(
            observation.modality_switches for observation in observations
        ) / len(observations)
        challenge_rate = sum(
            1
            for observation in observations
            if observation.support_level.value == "low"
            and observation.task_type.value in {"practice", "assessment"}
        ) / len(observations)
        completion_rate = sum(
            1 for observation in observations if observation.completed
        ) / len(observations)
        score = (
            0.6
            + (completion_rate * 0.15)
            + (challenge_rate * 0.1)
            - min(avg_hints, 4.0) * 0.05
            - min(avg_errors, 4.0) * 0.05
            - min(avg_switches, 4.0) * 0.03
        )
        confidence = min(0.8, 0.3 + (len(observations) * 0.08))
        return CognitiveTraitScore(
            value=round(min(0.95, max(0.1, score)), 2), confidence=round(confidence, 2)
        )

    def _spatial_reasoning(
        self, observations: list[LearnerObservation]
    ) -> CognitiveTraitScore | None:
        relevant = [
            observation
            for observation in observations
            if observation.task_type.value
            in {"worked_example", "explanation", "remediation"}
        ]
        if not relevant:
            return None
        completion_rate = sum(
            1 for observation in relevant if observation.completed
        ) / len(relevant)
        avg_errors = sum(observation.error_count for observation in relevant) / len(
            relevant
        )
        avg_switches = sum(
            observation.modality_switches for observation in relevant
        ) / len(relevant)
        score = (
            0.55
            + (completion_rate * 0.18)
            - min(avg_errors, 3.0) * 0.06
            - min(avg_switches, 3.0) * 0.04
        )
        confidence = min(0.74, 0.28 + (len(relevant) * 0.1))
        return CognitiveTraitScore(
            value=round(min(0.95, max(0.1, score)), 2), confidence=round(confidence, 2)
        )

    def _merge(
        self,
        existing: CognitiveTraitScore | None,
        inferred: CognitiveTraitScore,
    ) -> CognitiveTraitScore:
        if existing is None:
            return inferred
        total_confidence = min(1.0, existing.confidence + inferred.confidence)
        if total_confidence <= 0.0:
            return inferred
        merged_value = (
            (existing.value * existing.confidence)
            + (inferred.value * inferred.confidence)
        ) / (existing.confidence + inferred.confidence)
        return CognitiveTraitScore(
            value=round(merged_value, 2),
            confidence=round(total_confidence / 2.0, 2),
            assessed_at=inferred.assessed_at,
        )

    def _should_apply_durable_profile(
        self,
        profile: LearnerTraitProfileSummary,
        *,
        challenge_index: float,
        evidence: "_TraitEvidence",
    ) -> bool:
        return (
            profile.source != "insufficient"
            and profile.signal in {"stable", "tentative"}
            and profile.matched_session_count >= 2
            and profile.matched_observation_count >= 4
            and profile.trait_stability >= 0.48
            and max(
                profile.processing_speed_reliability,
                profile.working_memory_reliability,
                profile.spatial_reasoning_reliability,
            )
            >= 0.44
            and not (
                evidence.current_reliability >= 0.6
                and evidence.challenge_exposure >= 0.6
                and challenge_index >= 0.72
                and profile.challenge_tolerance < 0.55
            )
            and not (
                evidence.current_reliability >= 0.7
                and evidence.challenge_exposure >= 0.6
                and challenge_index >= 0.72
                and profile.signal == "tentative"
            )
            and not (
                profile.signal == "tentative"
                and challenge_index >= 0.72
                and profile.challenge_tolerance < 0.45
            )
        )

    def _should_apply_durable_trait(
        self,
        *,
        profile: LearnerTraitProfileSummary,
        name: str,
        reliability: float,
        challenge_index: float,
        evidence: "_TraitEvidence",
    ) -> bool:
        if reliability < 0.44:
            return False
        if (
            name == "working_memory"
            and evidence.current_reliability >= 0.62
            and evidence.challenge_exposure >= 0.55
            and challenge_index >= 0.65
            and profile.challenge_evidence_strength < 0.48
        ):
            return False
        if (
            profile.signal == "tentative"
            and reliability < 0.52
            and evidence.current_reliability >= 0.62
        ):
            return False
        return True

    def _trait_reliability(
        self, *, profile: LearnerTraitProfileSummary, name: str
    ) -> float:
        return {
            "processing_speed": profile.processing_speed_reliability,
            "working_memory": profile.working_memory_reliability,
            "spatial_reasoning": profile.spatial_reasoning_reliability,
        }.get(name, 0.0)

    def _merge_with_durable(
        self,
        *,
        name: str,
        current: CognitiveTraitScore | None,
        durable: CognitiveTraitScore,
        profile: LearnerTraitProfileSummary,
        reliability: float,
        challenge_index: float,
        evidence: "_TraitEvidence",
    ) -> CognitiveTraitScore:
        if current is None:
            return durable
        durable_weight = (
            0.08
            + (durable.confidence * 0.16)
            + (profile.trait_stability * 0.1)
            + (reliability * 0.18)
        )
        if challenge_index >= 0.6:
            durable_weight += 0.06 if profile.challenge_tolerance >= 0.6 else -0.08
        elif challenge_index <= 0.3 and profile.challenge_tolerance >= 0.7:
            durable_weight += 0.03
        if name == "working_memory":
            durable_weight += profile.challenge_evidence_strength * 0.1
        elif name == "processing_speed":
            durable_weight += reliability * 0.04
        elif name == "spatial_reasoning":
            durable_weight += reliability * 0.02
        if evidence.current_reliability >= 0.6:
            durable_weight -= min(0.12, evidence.current_reliability * 0.1)
        if (
            evidence.challenge_exposure >= 0.55
            and challenge_index >= 0.65
            and profile.challenge_tolerance < 0.55
        ):
            durable_weight -= 0.06
        if name == "working_memory" and profile.challenge_evidence_strength < 0.52:
            durable_weight -= 0.08
        if evidence.challenge_exposure <= 0.25 and profile.trait_stability >= 0.78:
            durable_weight += 0.04
        consistency = 1.0 - abs(current.value - durable.value)
        if consistency < 0.45:
            durable_weight *= 0.45 if profile.signal == "tentative" else 0.68
        elif consistency < 0.65:
            durable_weight *= 0.82
        if current.confidence < 0.45 and profile.trait_stability >= 0.75:
            durable_weight += 0.04
        if reliability >= 0.72 and consistency >= 0.7:
            durable_weight += 0.03
        durable_weight = min(0.5, max(0.08, durable_weight))
        merged_value = (current.value * (1.0 - durable_weight)) + (
            durable.value * durable_weight
        )
        merged_confidence = min(0.92, current.confidence + (durable.confidence * 0.2))
        return CognitiveTraitScore(
            value=round(merged_value, 2),
            confidence=round(merged_confidence, 2),
            assessed_at=durable.assessed_at,
        )

    def _current_challenge_index(self, observations: list[LearnerObservation]) -> float:
        if not observations:
            return 0.0
        active = [
            observation
            for observation in observations
            if observation.task_type.value in {"practice", "assessment"}
        ] or observations
        completion_gap = 1.0 - (
            sum(1 for observation in active if observation.completed) / len(active)
        )
        hints = sum(observation.hints_used for observation in active) / len(active)
        errors = sum(observation.error_count for observation in active) / len(active)
        low_support_rate = sum(
            1 for observation in active if observation.support_level.value == "low"
        ) / len(active)
        return round(
            min(
                1.0,
                0.12
                + (completion_gap * 0.24)
                + min(hints, 4.0) * 0.08
                + min(errors, 4.0) * 0.08
                + (low_support_rate * 0.12),
            ),
            2,
        )

    def _current_trait_evidence(
        self, observations: list[LearnerObservation]
    ) -> "_TraitEvidence":
        if not observations:
            return _TraitEvidence(current_reliability=0.0, challenge_exposure=0.0)
        active = [
            observation
            for observation in observations
            if observation.task_type.value in {"practice", "assessment"}
        ] or observations
        challenge_exposure = sum(
            1 for observation in active if observation.support_level.value == "low"
        ) / len(active)
        current_reliability = min(
            1.0,
            0.18 + (len(observations) * 0.12) + (min(len(active), 3) * 0.06),
        )
        return _TraitEvidence(
            current_reliability=round(current_reliability, 2),
            challenge_exposure=round(challenge_exposure, 2),
        )


@dataclass(frozen=True, slots=True)
class _TraitEvidence:
    current_reliability: float
    challenge_exposure: float
