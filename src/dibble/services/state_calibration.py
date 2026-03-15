from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from dibble.models.observations import LearnerObservation, ObservationSupportLevel, ObservationTaskType


@dataclass(frozen=True, slots=True)
class CalibratedObservationSummary:
    normalized_response_time: float
    normalized_error_pressure: float
    normalized_hint_pressure: float
    normalized_pause_pressure: float
    normalized_switch_pressure: float
    completion_rate: float
    avg_confidence: float
    performance_estimate: float


def summarize_observations(observations: list[LearnerObservation]) -> CalibratedObservationSummary:
    normalized_response_times = [_normalized_response_time(item) for item in observations]
    normalized_error_pressures = [_normalized_error_pressure(item) for item in observations]
    normalized_hint_pressures = [_normalized_hint_pressure(item) for item in observations]
    normalized_pause_pressures = [_normalized_pause_pressure(item) for item in observations]
    normalized_switch_pressures = [_normalized_switch_pressure(item) for item in observations]
    completion_rate = mean(1.0 if item.completed else 0.0 for item in observations)
    avg_confidence = mean(item.confidence for item in observations)
    avg_error_pressure = mean(normalized_error_pressures)
    avg_hint_pressure = mean(normalized_hint_pressures)
    performance_estimate = max(
        0.0,
        min(1.0, completion_rate - (avg_error_pressure * 0.22) - (avg_hint_pressure * 0.08)),
    )

    return CalibratedObservationSummary(
        normalized_response_time=mean(normalized_response_times),
        normalized_error_pressure=avg_error_pressure,
        normalized_hint_pressure=avg_hint_pressure,
        normalized_pause_pressure=mean(normalized_pause_pressures),
        normalized_switch_pressure=mean(normalized_switch_pressures),
        completion_rate=completion_rate,
        avg_confidence=avg_confidence,
        performance_estimate=performance_estimate,
    )


def _normalized_response_time(observation: LearnerObservation) -> float:
    baseline = float(observation.expected_duration_ms or _baseline_duration_ms(observation.task_type))
    support_factor = {
        ObservationSupportLevel.low: 0.95,
        ObservationSupportLevel.medium: 1.0,
        ObservationSupportLevel.high: 1.2,
    }[observation.support_level]
    return min(observation.response_time_ms / max(1.0, baseline * support_factor), 2.0)


def _normalized_error_pressure(observation: LearnerObservation) -> float:
    tolerance = {
        ObservationTaskType.generic: 2.5,
        ObservationTaskType.explanation: 2.2,
        ObservationTaskType.practice: 2.0,
        ObservationTaskType.worked_example: 3.0,
        ObservationTaskType.assessment: 1.5,
        ObservationTaskType.remediation: 2.6,
    }[observation.task_type]
    support_factor = {
        ObservationSupportLevel.low: 1.0,
        ObservationSupportLevel.medium: 1.15,
        ObservationSupportLevel.high: 1.35,
    }[observation.support_level]
    return min(observation.error_count / (tolerance * support_factor), 2.0)


def _normalized_hint_pressure(observation: LearnerObservation) -> float:
    expected_hints = {
        ObservationTaskType.generic: 1.0,
        ObservationTaskType.explanation: 0.8,
        ObservationTaskType.practice: 1.0,
        ObservationTaskType.worked_example: 1.6,
        ObservationTaskType.assessment: 0.2,
        ObservationTaskType.remediation: 1.5,
    }[observation.task_type]
    support_factor = {
        ObservationSupportLevel.low: 0.75,
        ObservationSupportLevel.medium: 1.0,
        ObservationSupportLevel.high: 1.35,
    }[observation.support_level]
    return min(observation.hints_used / max(0.2, expected_hints * support_factor), 2.0)


def _normalized_pause_pressure(observation: LearnerObservation) -> float:
    pause_tolerance = {
        ObservationTaskType.generic: 2.0,
        ObservationTaskType.explanation: 1.5,
        ObservationTaskType.practice: 2.0,
        ObservationTaskType.worked_example: 2.5,
        ObservationTaskType.assessment: 1.8,
        ObservationTaskType.remediation: 2.3,
    }[observation.task_type]
    return min(observation.pause_count / pause_tolerance, 2.0)


def _normalized_switch_pressure(observation: LearnerObservation) -> float:
    switch_tolerance = {
        ObservationTaskType.generic: 1.5,
        ObservationTaskType.explanation: 1.0,
        ObservationTaskType.practice: 1.3,
        ObservationTaskType.worked_example: 1.8,
        ObservationTaskType.assessment: 0.8,
        ObservationTaskType.remediation: 1.6,
    }[observation.task_type]
    return min(observation.modality_switches / switch_tolerance, 2.0)


def _baseline_duration_ms(task_type: ObservationTaskType) -> int:
    return {
        ObservationTaskType.generic: 15000,
        ObservationTaskType.explanation: 12000,
        ObservationTaskType.practice: 14000,
        ObservationTaskType.worked_example: 10000,
        ObservationTaskType.assessment: 18000,
        ObservationTaskType.remediation: 16000,
    }[task_type]
