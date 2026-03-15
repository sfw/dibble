from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.generation import ContentIntent
from dibble.models.observations import InferredLearnerState, LearnerObservationCreate, ObservationTaskType
from dibble.models.profile import MetacognitiveState, SignalLevel
from dibble.services.router_calibration_signals import RouterCalibrationSignalService


@dataclass(frozen=True, slots=True)
class LearnerStateCalibrationResult:
    state: InferredLearnerState
    signal: str = "insufficient"
    confidence: float = 0.0
    average_run_outcome_score: float | None = None
    matched_run_count: int = 0
    applied: bool = False


@dataclass(slots=True)
class LearnerStateCalibrator:
    calibration_signal_service: RouterCalibrationSignalService
    positive_confidence_threshold: float = 0.7
    negative_confidence_threshold: float = 0.6

    def calibrate(
        self,
        *,
        student_id: UUID,
        observation: LearnerObservationCreate,
        inferred_state: InferredLearnerState,
    ) -> LearnerStateCalibrationResult:
        signal = self.calibration_signal_service.signal_for(
            student_id=student_id,
            request=self._request_from_observation(student_id=student_id, observation=observation),
        )
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
                confidence=signal.confidence,
                average_run_outcome_score=signal.average_run_outcome_score,
                matched_run_count=signal.matched_run_count,
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
                confidence=signal.confidence,
                average_run_outcome_score=signal.average_run_outcome_score,
                matched_run_count=signal.matched_run_count,
                applied=True,
            )
        return LearnerStateCalibrationResult(
            state=inferred_state,
            signal=signal.signal,
            confidence=signal.confidence,
            average_run_outcome_score=signal.average_run_outcome_score,
            matched_run_count=signal.matched_run_count,
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
