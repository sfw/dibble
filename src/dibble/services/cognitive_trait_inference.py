from __future__ import annotations

from dataclasses import dataclass

from dibble.models.observations import LearnerObservation
from dibble.models.profile import CognitiveTraitScore


@dataclass(slots=True)
class CognitiveTraitInferenceService:
    def infer(
        self,
        *,
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

        return {**existing_traits, **updates}

    def _processing_speed(self, observations: list[LearnerObservation]) -> CognitiveTraitScore | None:
        ratios = [
            observation.response_time_ms / max(1, observation.expected_duration_ms or 15000)
            for observation in observations
        ]
        avg_ratio = sum(ratios) / len(ratios)
        completion_rate = sum(1 for observation in observations if observation.completed) / len(observations)
        avg_pause_count = sum(observation.pause_count for observation in observations) / len(observations)
        score = 0.7 - max(avg_ratio - 1.0, 0.0) * 0.35 + (completion_rate * 0.2) - min(avg_pause_count, 4.0) * 0.03
        confidence = min(0.82, 0.35 + (len(observations) * 0.08))
        return CognitiveTraitScore(value=round(min(0.95, max(0.1, score)), 2), confidence=round(confidence, 2))

    def _working_memory(self, observations: list[LearnerObservation]) -> CognitiveTraitScore | None:
        avg_hints = sum(observation.hints_used for observation in observations) / len(observations)
        avg_errors = sum(observation.error_count for observation in observations) / len(observations)
        avg_switches = sum(observation.modality_switches for observation in observations) / len(observations)
        challenge_rate = sum(
            1
            for observation in observations
            if observation.support_level.value == "low" and observation.task_type.value in {"practice", "assessment"}
        ) / len(observations)
        completion_rate = sum(1 for observation in observations if observation.completed) / len(observations)
        score = (
            0.6
            + (completion_rate * 0.15)
            + (challenge_rate * 0.1)
            - min(avg_hints, 4.0) * 0.05
            - min(avg_errors, 4.0) * 0.05
            - min(avg_switches, 4.0) * 0.03
        )
        confidence = min(0.8, 0.3 + (len(observations) * 0.08))
        return CognitiveTraitScore(value=round(min(0.95, max(0.1, score)), 2), confidence=round(confidence, 2))

    def _spatial_reasoning(self, observations: list[LearnerObservation]) -> CognitiveTraitScore | None:
        relevant = [
            observation
            for observation in observations
            if observation.task_type.value in {"worked_example", "explanation", "remediation"}
        ]
        if not relevant:
            return None
        completion_rate = sum(1 for observation in relevant if observation.completed) / len(relevant)
        avg_errors = sum(observation.error_count for observation in relevant) / len(relevant)
        avg_switches = sum(observation.modality_switches for observation in relevant) / len(relevant)
        score = 0.55 + (completion_rate * 0.18) - min(avg_errors, 3.0) * 0.06 - min(avg_switches, 3.0) * 0.04
        confidence = min(0.74, 0.28 + (len(relevant) * 0.1))
        return CognitiveTraitScore(value=round(min(0.95, max(0.1, score)), 2), confidence=round(confidence, 2))

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
            (existing.value * existing.confidence) + (inferred.value * inferred.confidence)
        ) / (existing.confidence + inferred.confidence)
        return CognitiveTraitScore(
            value=round(merged_value, 2),
            confidence=round(total_confidence / 2.0, 2),
            assessed_at=inferred.assessed_at,
        )
