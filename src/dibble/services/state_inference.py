from __future__ import annotations

from uuid import UUID

from dibble.models.observations import InferredLearnerState, LearnerObservation
from dibble.models.profile import AffectiveState, CognitiveLoadState, MetacognitiveState, SignalLevel
from dibble.services.state_calibration import summarize_observations


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

        calibrated = summarize_observations(observations)

        frustration = self._frustration_level(
            calibrated.normalized_error_pressure,
            calibrated.normalized_hint_pressure,
            calibrated.normalized_pause_pressure,
        )
        confusion = self._confusion_level(
            calibrated.normalized_error_pressure,
            calibrated.normalized_hint_pressure,
            calibrated.normalized_response_time,
        )
        engagement = self._engagement_level(
            calibrated.completion_rate,
            calibrated.normalized_pause_pressure,
            calibrated.normalized_switch_pressure,
            calibrated.normalized_response_time,
        )
        confidence_calibration = max(0.0, 1.0 - abs(calibrated.avg_confidence - calibrated.performance_estimate))
        help_seeking_effectiveness = max(
            0.0,
            min(
                1.0,
                0.3
                + (calibrated.completion_rate * 0.35)
                + min(calibrated.normalized_hint_pressure, 1.5) * 0.08
                - (calibrated.normalized_error_pressure * 0.06),
            ),
        )
        self_monitoring = max(
            0.0,
            min(
                1.0,
                0.25
                + (confidence_calibration * 0.4)
                + (calibrated.completion_rate * 0.2)
                - (calibrated.normalized_pause_pressure * 0.06),
            ),
        )
        help_seeking = self._help_seeking_level(
            calibrated.normalized_hint_pressure,
            calibrated.normalized_error_pressure,
            calibrated.avg_confidence,
        )

        intrinsic_load = min(
            1.0,
            0.2
            + (calibrated.normalized_error_pressure * 0.18)
            + min(calibrated.normalized_response_time * 0.2, 0.25),
        )
        extraneous_load = min(
            1.0,
            0.15
            + (calibrated.normalized_pause_pressure * 0.1)
            + (calibrated.normalized_switch_pressure * 0.08)
            + (calibrated.normalized_hint_pressure * 0.06),
        )
        germane_load = min(1.0, 0.25 + (calibrated.completion_rate * 0.35) + (calibrated.avg_confidence * 0.15))
        total_load = min(
            1.0,
            (intrinsic_load * 0.45)
            + (extraneous_load * 0.35)
            + (germane_load * 0.20)
            + (0.1 if frustration == SignalLevel.high else 0.05 if frustration == SignalLevel.medium else 0.0),
        )
        capacity_utilization = min(1.0, total_load + (0.1 if frustration in {SignalLevel.medium, SignalLevel.high} else 0.0))

        return InferredLearnerState(
            student_id=student_id,
            affective_state=AffectiveState(
                engagement=engagement,
                frustration=frustration,
                confusion=confusion,
                confidence=round(calibrated.avg_confidence, 2),
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
        if score >= 1.35:
            return SignalLevel.high
        if score >= 0.8:
            return SignalLevel.medium
        if score >= 0.3:
            return SignalLevel.low
        return SignalLevel.none

    def _confusion_level(self, avg_errors: float, avg_hints: float, avg_response_time: float) -> SignalLevel:
        score = (avg_errors * 0.45) + (avg_hints * 0.35) + min(avg_response_time * 0.25, 0.4)
        if score >= 1.3:
            return SignalLevel.high
        if score >= 0.7:
            return SignalLevel.medium
        if score >= 0.25:
            return SignalLevel.low
        return SignalLevel.none

    def _engagement_level(
        self,
        completion_rate: float,
        avg_pauses: float,
        avg_switches: float,
        avg_response_time: float,
    ) -> SignalLevel:
        score = (completion_rate * 0.6) - (avg_pauses * 0.16) - (avg_switches * 0.1) - min(avg_response_time * 0.15, 0.2)
        if score >= 0.55:
            return SignalLevel.high
        if score >= 0.2:
            return SignalLevel.medium
        if score >= 0.0:
            return SignalLevel.low
        return SignalLevel.none

    def _help_seeking_level(self, avg_hints: float, avg_errors: float, avg_confidence: float) -> SignalLevel:
        score = (avg_hints * 0.45) + (avg_errors * 0.15) + ((1.0 - avg_confidence) * 0.4)
        if score >= 1.25:
            return SignalLevel.high
        if score >= 0.7:
            return SignalLevel.medium
        if score >= 0.25:
            return SignalLevel.low
        return SignalLevel.none
