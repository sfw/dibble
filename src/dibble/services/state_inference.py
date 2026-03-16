from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.observations import InferredLearnerState, LearnerObservation
from dibble.models.profile import (
    AffectiveState,
    CognitiveLoadState,
    LearnerStateProfileSummary,
    MetacognitiveState,
    SignalLevel,
)
from dibble.services.learning_state_profiles import LearnerStateSignalService
from dibble.services.state_calibration import summarize_observations


@dataclass(slots=True)
class LearnerStateInferenceService:
    state_profile_signal_service: LearnerStateSignalService | None = None

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
        evidence = _state_evidence(observations)

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

        inferred = InferredLearnerState(
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
        durable_profile = (
            self.state_profile_signal_service.latest_for_student(student_id=student_id)
            if self.state_profile_signal_service is not None
            else LearnerStateProfileSummary()
        )
        if self._should_apply_durable_profile(
            durable_profile=durable_profile,
            observation_count=len(observations),
            performance_estimate=calibrated.performance_estimate,
            evidence=evidence,
            inferred=inferred,
        ):
            return self._blend_with_durable(
                inferred=inferred,
                durable_profile=durable_profile,
                evidence=evidence,
            )
        return inferred

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

    def _should_apply_durable_profile(
        self,
        *,
        durable_profile: LearnerStateProfileSummary,
        observation_count: int,
        performance_estimate: float,
        evidence: "_StateEvidence",
        inferred: InferredLearnerState,
    ) -> bool:
        if durable_profile.source == "insufficient":
            return False
        if durable_profile.confidence < 0.6 or durable_profile.matched_session_count < 2:
            return False
        if observation_count < 2 and durable_profile.confidence < 0.72:
            return False
        performance_gap = (
            abs((durable_profile.average_run_outcome_score or performance_estimate) - performance_estimate)
            if durable_profile.average_run_outcome_score is not None
            else 0.0
        )
        contradiction = _state_profile_contradiction(inferred=inferred, durable_profile=durable_profile)
        if performance_gap > 0.38 and durable_profile.confidence < 0.82:
            return False
        contradiction_limit = 0.38 if durable_profile.signal == "independence_ready" else 0.62
        if contradiction >= contradiction_limit and evidence.current_reliability >= 0.62:
            return False
        if contradiction >= 0.55 and durable_profile.confidence < 0.86:
            return False
        return (
            durable_profile.recovery_stability >= 0.35
            or durable_profile.overload_risk >= 0.55
            or durable_profile.metacognitive_reliability >= 0.5
        )

    def _blend_with_durable(
        self,
        *,
        inferred: InferredLearnerState,
        durable_profile: LearnerStateProfileSummary,
        evidence: "_StateEvidence",
    ) -> InferredLearnerState:
        contradiction = _state_profile_contradiction(inferred=inferred, durable_profile=durable_profile)
        weight = 0.12 + (durable_profile.confidence * 0.16) + (durable_profile.recovery_stability * 0.12)
        weight += durable_profile.metacognitive_reliability * 0.08
        if durable_profile.overload_risk >= 0.7 and inferred.cognitive_load.total_load >= 0.55:
            weight += 0.06
        if (
            evidence.current_reliability >= 0.58
            and contradiction >= 0.28
            and durable_profile.signal == "independence_ready"
        ):
            weight -= min(0.12, evidence.current_reliability * 0.12)
        if evidence.task_diversity >= 0.66:
            weight -= 0.03
        if evidence.support_intensity <= 0.25 and durable_profile.overload_risk >= 0.72:
            weight -= 0.04
        if evidence.support_intensity >= 0.6 and durable_profile.overload_risk >= 0.6:
            weight += 0.03
        if contradiction >= 0.28:
            multiplier = 1.55 if durable_profile.signal == "independence_ready" else 0.8
            floor = 0.26 if durable_profile.signal == "independence_ready" else 0.62
            weight *= max(floor, 1.0 - (contradiction * multiplier))
        metacognitive_weight = min(0.48, weight + (durable_profile.metacognitive_reliability * 0.1))
        if durable_profile.signal == "independence_ready" and contradiction >= 0.28:
            metacognitive_weight *= 0.65
        weight = min(0.42, max(0.1, weight))
        return inferred.model_copy(
            update={
                "affective_state": inferred.affective_state.model_copy(
                    update={
                        "engagement": _blend_signal(inferred.affective_state.engagement, durable_profile.engagement, weight),
                        "frustration": _blend_signal(inferred.affective_state.frustration, durable_profile.frustration, weight),
                        "confidence": round(_blend(inferred.affective_state.confidence, durable_profile.confidence, weight), 2),
                    }
                ),
                "cognitive_load": inferred.cognitive_load.model_copy(
                    update={
                        "total_load": round(_blend(inferred.cognitive_load.total_load, durable_profile.total_load, weight), 2),
                        "capacity_utilization": round(
                            _blend(
                                inferred.cognitive_load.capacity_utilization,
                                max(durable_profile.total_load, durable_profile.overload_risk),
                                min(0.5, weight + 0.06),
                            ),
                            2,
                        ),
                    }
                ),
                "metacognitive_state": inferred.metacognitive_state.model_copy(
                    update={
                        "confidence_calibration": round(
                            _blend(
                                inferred.metacognitive_state.confidence_calibration,
                                durable_profile.confidence_calibration,
                                min(metacognitive_weight, weight + (durable_profile.metacognitive_reliability * 0.08)),
                            ),
                            2,
                        ),
                        "help_seeking": _blend_signal(
                            inferred.metacognitive_state.help_seeking,
                            durable_profile.help_seeking,
                            min(
                                0.58 if durable_profile.signal == "support_needed" and durable_profile.overload_risk >= 0.7 else 0.45,
                                weight
                                + (
                                    0.12
                                    if durable_profile.signal == "support_needed" and durable_profile.overload_risk >= 0.7
                                    else 0.04
                                ),
                            ),
                        ),
                        "self_monitoring": round(
                            _blend(
                                inferred.metacognitive_state.self_monitoring,
                                durable_profile.self_monitoring,
                                metacognitive_weight,
                            ),
                            2,
                        ),
                    }
                ),
            }
        )


def _blend(current: float, durable: float, weight: float) -> float:
    return (current * (1.0 - weight)) + (durable * weight)


def _blend_signal(current: SignalLevel, durable: SignalLevel, weight: float) -> SignalLevel:
    numeric = _blend(_signal_value(current), _signal_value(durable), weight)
    if numeric >= 0.8:
        return SignalLevel.high
    if numeric >= 0.5:
        return SignalLevel.medium
    if numeric >= 0.2:
        return SignalLevel.low
    return SignalLevel.none


@dataclass(frozen=True, slots=True)
class _StateEvidence:
    current_reliability: float
    task_diversity: float
    support_intensity: float


def _state_evidence(observations: list[LearnerObservation]) -> _StateEvidence:
    if not observations:
        return _StateEvidence(current_reliability=0.0, task_diversity=0.0, support_intensity=0.0)
    task_types = {observation.task_type.value for observation in observations}
    support_map = {"low": 0.0, "medium": 0.5, "high": 1.0}
    support_intensity = sum(support_map.get(observation.support_level.value, 0.5) for observation in observations) / len(
        observations
    )
    current_reliability = min(
        1.0,
        0.18 + (len(observations) * 0.12) + (min(len(task_types), 3) * 0.08),
    )
    return _StateEvidence(
        current_reliability=round(current_reliability, 2),
        task_diversity=round(min(1.0, len(task_types) / 3.0), 2),
        support_intensity=round(support_intensity, 2),
    )


def _state_profile_contradiction(
    *,
    inferred: InferredLearnerState,
    durable_profile: LearnerStateProfileSummary,
) -> float:
    overload_gap = abs(inferred.cognitive_load.total_load - durable_profile.total_load)
    confidence_gap = abs(
        inferred.metacognitive_state.confidence_calibration - durable_profile.confidence_calibration
    )
    engagement_gap = abs(
        _signal_value(inferred.affective_state.engagement) - _signal_value(durable_profile.engagement)
    )
    frustration_gap = abs(
        _signal_value(inferred.affective_state.frustration) - _signal_value(durable_profile.frustration)
    )
    help_gap = abs(
        _signal_value(inferred.metacognitive_state.help_seeking) - _signal_value(durable_profile.help_seeking)
    )
    return round(
        min(
            1.0,
            (overload_gap * 0.35)
            + (confidence_gap * 0.2)
            + (engagement_gap * 0.15)
            + (frustration_gap * 0.15)
            + (help_gap * 0.15),
        ),
        2,
    )


def _signal_value(signal: SignalLevel) -> float:
    return {
        SignalLevel.none: 0.0,
        SignalLevel.low: 0.3,
        SignalLevel.medium: 0.6,
        SignalLevel.high: 0.9,
    }[signal]
