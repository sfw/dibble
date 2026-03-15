from __future__ import annotations

from statistics import mean
from uuid import UUID

from dibble.models.observations import InferredLearnerState, LearnerObservation
from dibble.models.profile import AffectiveState, CognitiveLoadState, MetacognitiveState, SignalLevel


class LearnerStateInferenceService:
    def infer(self, *, student_id: UUID, observations: list[LearnerObservation]) -> InferredLearnerState:
        if not observations:
            return InferredLearnerState(
                student_id=student_id,
                affective_state=AffectiveState(),
                cognitive_load=CognitiveLoadState(),
                metacognitive_state=MetacognitiveState(),
                observation_count=0,
                last_observation_at=None,
            )

        avg_response_time = mean(item.response_time_ms for item in observations)
        avg_hints = mean(item.hints_used for item in observations)
        avg_errors = mean(item.error_count for item in observations)
        avg_pauses = mean(item.pause_count for item in observations)
        avg_switches = mean(item.modality_switches for item in observations)
        completion_rate = mean(1.0 if item.completed else 0.0 for item in observations)
        avg_confidence = mean(item.confidence for item in observations)
        performance_estimate = max(0.0, min(completion_rate - (avg_errors * 0.12), 1.0))

        frustration = self._frustration_level(avg_errors, avg_hints, avg_pauses)
        confusion = self._confusion_level(avg_errors, avg_hints, avg_response_time)
        engagement = self._engagement_level(completion_rate, avg_pauses, avg_switches, avg_response_time)
        confidence_calibration = max(0.0, 1.0 - abs(avg_confidence - performance_estimate))
        help_seeking_effectiveness = max(
            0.0,
            min(1.0, 0.3 + (completion_rate * 0.35) + min(avg_hints, 3) * 0.08 - (avg_errors * 0.04)),
        )
        self_monitoring = max(
            0.0,
            min(1.0, 0.25 + (confidence_calibration * 0.4) + (completion_rate * 0.2) - (avg_pauses * 0.04)),
        )
        help_seeking = self._help_seeking_level(avg_hints, avg_errors, avg_confidence)

        intrinsic_load = min(1.0, 0.2 + (avg_errors * 0.12) + min(avg_response_time / 40000, 0.25))
        extraneous_load = min(1.0, 0.15 + (avg_pauses * 0.08) + (avg_switches * 0.07) + (avg_hints * 0.05))
        germane_load = min(1.0, 0.25 + (completion_rate * 0.35) + (avg_confidence * 0.15))
        total_load = min(1.0, (intrinsic_load * 0.45) + (extraneous_load * 0.35) + (germane_load * 0.20))
        capacity_utilization = min(1.0, total_load + (0.1 if frustration in {SignalLevel.medium, SignalLevel.high} else 0.0))

        return InferredLearnerState(
            student_id=student_id,
            affective_state=AffectiveState(
                engagement=engagement,
                frustration=frustration,
                confusion=confusion,
                confidence=round(avg_confidence, 2),
            ),
            cognitive_load=CognitiveLoadState(
                intrinsic_load=round(intrinsic_load, 2),
                extraneous_load=round(extraneous_load, 2),
                germane_load=round(germane_load, 2),
                total_load=round(total_load, 2),
                capacity_utilization=round(capacity_utilization, 2),
            ),
            metacognitive_state=MetacognitiveState(
                confidence_calibration=round(confidence_calibration, 2),
                help_seeking=help_seeking,
                help_seeking_effectiveness=round(help_seeking_effectiveness, 2),
                self_monitoring=round(self_monitoring, 2),
            ),
            observation_count=len(observations),
            last_observation_at=max(item.created_at for item in observations),
        )

    def _frustration_level(self, avg_errors: float, avg_hints: float, avg_pauses: float) -> SignalLevel:
        score = (avg_errors * 0.5) + (avg_hints * 0.3) + (avg_pauses * 0.2)
        if score >= 1.8:
            return SignalLevel.high
        if score >= 1.0:
            return SignalLevel.medium
        if score >= 0.4:
            return SignalLevel.low
        return SignalLevel.none

    def _confusion_level(self, avg_errors: float, avg_hints: float, avg_response_time: float) -> SignalLevel:
        score = (avg_errors * 0.45) + (avg_hints * 0.35) + min(avg_response_time / 30000, 0.4)
        if score >= 1.6:
            return SignalLevel.high
        if score >= 0.9:
            return SignalLevel.medium
        if score >= 0.35:
            return SignalLevel.low
        return SignalLevel.none

    def _engagement_level(
        self,
        completion_rate: float,
        avg_pauses: float,
        avg_switches: float,
        avg_response_time: float,
    ) -> SignalLevel:
        score = (completion_rate * 0.6) - (avg_pauses * 0.12) - (avg_switches * 0.08) - min(avg_response_time / 60000, 0.2)
        if score >= 0.55:
            return SignalLevel.high
        if score >= 0.2:
            return SignalLevel.medium
        if score >= 0.0:
            return SignalLevel.low
        return SignalLevel.none

    def _help_seeking_level(self, avg_hints: float, avg_errors: float, avg_confidence: float) -> SignalLevel:
        score = (avg_hints * 0.45) + (avg_errors * 0.15) + ((1.0 - avg_confidence) * 0.4)
        if score >= 1.7:
            return SignalLevel.high
        if score >= 0.9:
            return SignalLevel.medium
        if score >= 0.25:
            return SignalLevel.low
        return SignalLevel.none
