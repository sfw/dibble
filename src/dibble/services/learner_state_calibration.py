from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.generation import ContentIntent
from dibble.models.observations import InferredLearnerState, LearnerObservationCreate, ObservationTaskType
from dibble.models.profile import LearnerStateProfileSummary, MetacognitiveState, SignalLevel
from dibble.services.learning_state_profiles import LearnerStateSignalService
from dibble.services.router_calibration_signals import RouterCalibrationSignalService


@dataclass(frozen=True, slots=True)
class LearnerStateCalibrationResult:
    state: InferredLearnerState
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = 0.0
    average_run_outcome_score: float | None = None
    matched_run_count: int = 0
    matched_session_count: int = 0
    progress_signal: str = "insufficient"
    strategy_signal: str = "insufficient"
    recovery_stability: float = 0.0
    overload_risk: float = 0.0
    metacognitive_reliability: float = 0.0
    rationale: str | None = None
    applied: bool = False


@dataclass(slots=True)
class LearnerStateCalibrator:
    calibration_signal_service: RouterCalibrationSignalService
    state_signal_service: LearnerStateSignalService | None = None
    positive_confidence_threshold: float = 0.7
    negative_confidence_threshold: float = 0.6
    state_profile_confidence_threshold: float = 0.58

    def calibrate(
        self,
        *,
        student_id: UUID,
        observation: LearnerObservationCreate,
        inferred_state: InferredLearnerState,
    ) -> LearnerStateCalibrationResult:
        request = self._request_from_observation(student_id=student_id, observation=observation)
        state_profile = (
            self.state_signal_service.state_for(student_id=student_id, request=request)
            if self.state_signal_service is not None
            else LearnerStateProfileSummary()
        )
        if self._should_apply_state_profile(
            profile=state_profile,
            observation=observation,
            inferred_state=inferred_state,
        ):
            return LearnerStateCalibrationResult(
                state=self._blend_with_state_profile(
                    inferred_state,
                    state_profile,
                    observation=observation,
                ),
                signal=state_profile.signal,
                source=state_profile.source,
                confidence=state_profile.confidence,
                average_run_outcome_score=state_profile.average_run_outcome_score,
                matched_run_count=state_profile.matched_run_count,
                matched_session_count=state_profile.matched_session_count,
                progress_signal=state_profile.progress_signal,
                strategy_signal=state_profile.strategy_signal,
                recovery_stability=state_profile.recovery_stability,
                overload_risk=state_profile.overload_risk,
                metacognitive_reliability=state_profile.metacognitive_reliability,
                rationale=state_profile.rationale,
                applied=True,
            )

        signal = self.calibration_signal_service.signal_for(student_id=student_id, request=request)
        if signal.signal == "positive" and signal.confidence >= self.positive_confidence_threshold:
            return LearnerStateCalibrationResult(
                state=inferred_state.model_copy(
                    update={
                        "metacognitive_state": self._adjust_metacognitive_state(
                            inferred_state.metacognitive_state,
                            confidence_delta=min(0.12, 0.05 + (signal.confidence * 0.08)),
                            self_monitoring_delta=min(0.1, 0.04 + (signal.confidence * 0.07)),
                            help_seeking_shift=-1,
                            effectiveness_delta=min(0.08, 0.03 + (signal.confidence * 0.05)),
                        )
                    }
                ),
                signal=signal.signal,
                source=signal.source,
                confidence=signal.confidence,
                average_run_outcome_score=signal.average_run_outcome_score,
                matched_run_count=signal.matched_run_count,
                progress_signal=signal.progress_signal,
                overload_risk=self._observation_strain(observation=observation, state=inferred_state),
                applied=True,
            )
        if signal.signal == "negative" and signal.confidence >= self.negative_confidence_threshold:
            return LearnerStateCalibrationResult(
                state=inferred_state.model_copy(
                    update={
                        "metacognitive_state": self._adjust_metacognitive_state(
                            inferred_state.metacognitive_state,
                            confidence_delta=-min(0.12, 0.05 + (signal.confidence * 0.08)),
                            self_monitoring_delta=-min(0.08, 0.03 + (signal.confidence * 0.06)),
                            help_seeking_shift=1,
                            effectiveness_delta=-min(0.06, 0.02 + (signal.confidence * 0.04)),
                        )
                    }
                ),
                signal=signal.signal,
                source=signal.source,
                confidence=signal.confidence,
                average_run_outcome_score=signal.average_run_outcome_score,
                matched_run_count=signal.matched_run_count,
                progress_signal=signal.progress_signal,
                overload_risk=self._observation_strain(observation=observation, state=inferred_state),
                applied=True,
            )
        return LearnerStateCalibrationResult(
            state=inferred_state,
            signal=signal.signal,
            source=signal.source,
            confidence=signal.confidence,
            average_run_outcome_score=signal.average_run_outcome_score,
            matched_run_count=signal.matched_run_count,
            progress_signal=signal.progress_signal,
            overload_risk=self._observation_strain(observation=observation, state=inferred_state),
            applied=False,
        )

    def _request_from_observation(
        self,
        *,
        student_id: UUID,
        observation: LearnerObservationCreate,
    ):
        from dibble.models.generation import GenerationRequest

        return GenerationRequest(
            student_id=student_id,
            learning_session_id=observation.learning_session_id,
            target_kc_ids=observation.target_kc_ids,
            target_lo_ids=observation.target_lo_ids,
            intent=self._intent_for(observation.task_type),
        )

    def _intent_for(self, task_type: ObservationTaskType) -> ContentIntent:
        mapping = {
            ObservationTaskType.generic: ContentIntent.explanation,
            ObservationTaskType.explanation: ContentIntent.explanation,
            ObservationTaskType.worked_example: ContentIntent.explanation,
            ObservationTaskType.practice: ContentIntent.practice,
            ObservationTaskType.remediation: ContentIntent.remediation,
            ObservationTaskType.assessment: ContentIntent.assessment,
        }
        return mapping[task_type]

    def _adjust_metacognitive_state(
        self,
        state: MetacognitiveState,
        *,
        confidence_delta: float,
        self_monitoring_delta: float,
        help_seeking_shift: int,
        effectiveness_delta: float,
    ) -> MetacognitiveState:
        return state.model_copy(
            update={
                "confidence_calibration": round(
                    min(1.0, max(0.0, state.confidence_calibration + confidence_delta)),
                    2,
                ),
                "self_monitoring": round(
                    min(1.0, max(0.0, state.self_monitoring + self_monitoring_delta)),
                    2,
                ),
                "help_seeking_effectiveness": round(
                    min(1.0, max(0.0, state.help_seeking_effectiveness + effectiveness_delta)),
                    2,
                ),
                "help_seeking": self._shift_signal_level(state.help_seeking, help_seeking_shift),
            }
        )

    def _shift_signal_level(self, level: SignalLevel, shift: int) -> SignalLevel:
        ordered = [SignalLevel.none, SignalLevel.low, SignalLevel.medium, SignalLevel.high]
        current_index = ordered.index(level)
        target_index = min(max(0, current_index + shift), len(ordered) - 1)
        return ordered[target_index]

    def _should_apply_state_profile(
        self,
        *,
        profile: LearnerStateProfileSummary,
        observation: LearnerObservationCreate,
        inferred_state: InferredLearnerState,
    ) -> bool:
        if profile.source == "insufficient":
            return False
        if profile.signal not in {"support_needed", "independence_ready", "recovering"}:
            return False
        if profile.matched_session_count < 2:
            return False
        if profile.confidence < self.state_profile_confidence_threshold:
            return False
        observation_strain = self._observation_strain(observation=observation, state=inferred_state)
        if profile.signal == "independence_ready":
            return (
                profile.recovery_stability >= 0.58
                and profile.metacognitive_reliability >= 0.52
                and profile.overload_risk <= 0.68
                and observation_strain < 0.72
            )
        if profile.signal == "support_needed":
            return profile.overload_risk >= 0.44 or observation_strain >= 0.36
        return profile.recovery_stability >= 0.5

    def _blend_with_state_profile(
        self,
        state: InferredLearnerState,
        profile: LearnerStateProfileSummary,
        *,
        observation: LearnerObservationCreate,
    ) -> InferredLearnerState:
        weight = self._state_profile_weight(
            profile=profile,
            observation=observation,
            state=state,
        )
        return state.model_copy(
            update={
                "affective_state": state.affective_state.model_copy(
                    update={
                        "engagement": self._blend_signal_level(
                            state.affective_state.engagement,
                            profile.engagement,
                            weight=weight,
                        ),
                        "frustration": self._blend_signal_level(
                            state.affective_state.frustration,
                            profile.frustration,
                            weight=weight,
                        ),
                        "confidence": round(
                            self._blend_numeric(
                                state.affective_state.confidence,
                                target=self._profile_confidence_target(profile),
                                weight=weight,
                            ),
                            2,
                        ),
                    }
                ),
                "cognitive_load": state.cognitive_load.model_copy(
                    update={
                        "intrinsic_load": round(
                            self._blend_numeric(state.cognitive_load.intrinsic_load, target=self._profile_intrinsic_load(profile), weight=weight),
                            2,
                        ),
                        "extraneous_load": round(
                            self._blend_numeric(state.cognitive_load.extraneous_load, target=self._profile_extraneous_load(profile), weight=weight),
                            2,
                        ),
                        "germane_load": round(
                            self._blend_numeric(state.cognitive_load.germane_load, target=self._profile_germane_load(profile), weight=weight),
                            2,
                        ),
                        "total_load": round(
                            self._blend_numeric(state.cognitive_load.total_load, target=profile.total_load, weight=weight),
                            2,
                        ),
                        "capacity_utilization": round(
                            self._blend_numeric(
                                state.cognitive_load.capacity_utilization,
                                target=min(1.0, profile.total_load + (0.1 if profile.frustration in {SignalLevel.medium, SignalLevel.high} else 0.0)),
                                weight=weight,
                            ),
                            2,
                        ),
                    }
                ),
                "metacognitive_state": state.metacognitive_state.model_copy(
                    update={
                        "confidence_calibration": round(
                            self._blend_numeric(
                                state.metacognitive_state.confidence_calibration,
                                target=profile.confidence_calibration,
                                weight=weight,
                            ),
                            2,
                        ),
                        "help_seeking": self._blend_signal_level(
                            state.metacognitive_state.help_seeking,
                            profile.help_seeking,
                            weight=weight,
                        ),
                        "help_seeking_effectiveness": round(
                            self._blend_numeric(
                                state.metacognitive_state.help_seeking_effectiveness,
                                target=self._profile_help_seeking_effectiveness(profile),
                                weight=weight,
                            ),
                            2,
                        ),
                        "self_monitoring": round(
                            self._blend_numeric(
                                state.metacognitive_state.self_monitoring,
                                target=profile.self_monitoring,
                                weight=weight,
                            ),
                            2,
                        ),
                    }
                ),
            }
        )

    def _state_profile_weight(
        self,
        *,
        profile: LearnerStateProfileSummary,
        observation: LearnerObservationCreate,
        state: InferredLearnerState,
    ) -> float:
        observation_strain = self._observation_strain(observation=observation, state=state)
        weight = 0.12 + (profile.confidence * 0.18)
        if profile.matched_session_count >= 4:
            weight += 0.05
        if profile.signal == "support_needed":
            weight += (profile.overload_risk * 0.14) + (observation_strain * 0.12)
        elif profile.signal == "independence_ready":
            weight += (profile.recovery_stability * 0.12) + (profile.metacognitive_reliability * 0.08)
            weight -= observation_strain * 0.18
        else:
            weight += (profile.recovery_stability * 0.1) - abs(observation_strain - 0.45) * 0.08
        return min(0.48, max(0.16, weight))

    def _observation_strain(
        self,
        *,
        observation: LearnerObservationCreate,
        state: InferredLearnerState,
    ) -> float:
        ratio = (
            observation.response_time_ms / max(1, observation.expected_duration_ms)
            if observation.expected_duration_ms is not None
            else 1.0
        )
        strain = 0.12
        strain += min(0.24, observation.error_count * 0.07)
        strain += min(0.18, observation.hints_used * 0.05)
        strain += 0.1 if not observation.completed else 0.0
        strain += (
            0.08
            if observation.support_level.value == "low"
            else 0.04
            if observation.support_level.value == "medium"
            else 0.0
        )
        strain += min(0.12, max(0.0, ratio - 1.0) * 0.12)
        strain += max(0.0, state.cognitive_load.total_load - 0.55) * 0.22
        strain += 0.12 if state.affective_state.frustration in {SignalLevel.medium, SignalLevel.high} else 0.0
        return min(1.0, round(strain, 2))

    def _blend_numeric(self, current: float, *, target: float, weight: float) -> float:
        return min(1.0, max(0.0, (current * (1.0 - weight)) + (target * weight)))

    def _blend_signal_level(self, current: SignalLevel, target: SignalLevel, *, weight: float) -> SignalLevel:
        ordered = [SignalLevel.none, SignalLevel.low, SignalLevel.medium, SignalLevel.high]
        current_index = ordered.index(current)
        target_index = ordered.index(target)
        if current_index == target_index:
            return current
        if weight < 0.22 and abs(target_index - current_index) <= 1:
            return current
        step = 1 if target_index > current_index else -1
        return ordered[min(max(0, current_index + step), len(ordered) - 1)]

    def _profile_confidence_target(self, profile: LearnerStateProfileSummary) -> float:
        if profile.signal == "support_needed":
            return max(0.25, profile.confidence_calibration - 0.05)
        if profile.signal == "independence_ready":
            return min(1.0, profile.confidence_calibration + 0.05)
        return profile.confidence_calibration

    def _profile_intrinsic_load(self, profile: LearnerStateProfileSummary) -> float:
        if profile.signal == "support_needed":
            return min(1.0, profile.total_load)
        if profile.signal == "independence_ready":
            return max(0.0, profile.total_load - 0.12)
        return max(0.0, profile.total_load - 0.08)

    def _profile_extraneous_load(self, profile: LearnerStateProfileSummary) -> float:
        if profile.signal == "support_needed":
            return min(1.0, profile.total_load - 0.12)
        if profile.signal == "independence_ready":
            return max(0.0, profile.total_load - 0.24)
        return max(0.0, profile.total_load - 0.18)

    def _profile_germane_load(self, profile: LearnerStateProfileSummary) -> float:
        if profile.signal == "support_needed":
            return max(0.2, 0.75 - profile.total_load)
        return min(1.0, 0.25 + profile.confidence_calibration * 0.35)

    def _profile_help_seeking_effectiveness(self, profile: LearnerStateProfileSummary) -> float:
        if profile.signal == "support_needed":
            return max(0.25, profile.confidence_calibration - 0.05)
        if profile.signal == "independence_ready":
            return min(1.0, profile.confidence_calibration + 0.02)
        return min(1.0, profile.confidence_calibration)
