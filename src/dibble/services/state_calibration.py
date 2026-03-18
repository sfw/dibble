from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from dibble.models.observations import (
    CurrentEvidenceSignal,
    LearnerObservation,
    ObservationSupportLevel,
    ObservationTaskType,
)


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


def summarize_observations(
    observations: list[LearnerObservation],
) -> CalibratedObservationSummary:
    normalized_response_times = [
        _normalized_response_time(item) for item in observations
    ]
    normalized_error_pressures = [
        _normalized_error_pressure(item) for item in observations
    ]
    normalized_hint_pressures = [
        _normalized_hint_pressure(item) for item in observations
    ]
    normalized_pause_pressures = [
        _normalized_pause_pressure(item) for item in observations
    ]
    normalized_switch_pressures = [
        _normalized_switch_pressure(item) for item in observations
    ]
    completion_rate = mean(1.0 if item.completed else 0.0 for item in observations)
    avg_confidence = mean(item.confidence for item in observations)
    avg_error_pressure = mean(normalized_error_pressures)
    avg_hint_pressure = mean(normalized_hint_pressures)
    performance_estimate = max(
        0.0,
        min(
            1.0,
            completion_rate - (avg_error_pressure * 0.22) - (avg_hint_pressure * 0.08),
        ),
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


def discriminate_current_evidence(
    observations: list[LearnerObservation],
    *,
    calibrated_summary: CalibratedObservationSummary | None = None,
) -> CurrentEvidenceSignal:
    if not observations:
        return CurrentEvidenceSignal()

    summary = calibrated_summary or summarize_observations(observations)
    challenge_exposure = _challenge_exposure(observations)
    support_intensity = _support_intensity(observations)
    high_support_success_rate = _high_support_success_rate(observations)
    low_support_completion_rate = _low_support_completion_rate(observations)
    incomplete_rate = 1.0 - summary.completion_rate
    low_confidence = max(0.0, 1.0 - summary.avg_confidence)
    response_overrun = max(0.0, summary.normalized_response_time - 1.0)

    productive_struggle_score = _clamp01(
        0.12
        + (challenge_exposure * 0.34)
        + (low_support_completion_rate * 0.18)
        + (0.16 if 0.2 <= summary.normalized_error_pressure <= 0.9 else 0.0)
        + (0.12 if 0.15 <= summary.normalized_hint_pressure <= 0.85 else 0.0)
        + (0.08 if 0.4 <= summary.avg_confidence <= 0.78 else 0.0)
        - min(0.16, response_overrun * 0.18)
        - min(0.12, summary.normalized_pause_pressure * 0.1)
        - min(0.1, summary.normalized_switch_pressure * 0.08)
        - min(0.12, high_support_success_rate * 0.18)
    )
    overload_score = _clamp01(
        (summary.normalized_error_pressure * 0.28)
        + (summary.normalized_hint_pressure * 0.16)
        + min(0.18, response_overrun * 0.22)
        + min(0.16, summary.normalized_pause_pressure * 0.12)
        + (incomplete_rate * 0.16)
        + (low_confidence * 0.16)
        + (
            0.1
            if challenge_exposure >= 0.34 and summary.normalized_error_pressure >= 0.7
            else 0.0
        )
    )
    disengagement_score = _clamp01(
        (incomplete_rate * 0.28)
        + min(0.18, summary.normalized_pause_pressure * 0.16)
        + min(0.16, summary.normalized_switch_pressure * 0.14)
        + min(0.14, response_overrun * 0.18)
        + (low_confidence * 0.12)
        + (
            0.08
            if summary.normalized_hint_pressure <= 0.25 and incomplete_rate >= 0.34
            else 0.0
        )
        + (
            0.08
            if summary.normalized_error_pressure <= 0.45
            and summary.normalized_switch_pressure >= 0.75
            else 0.0
        )
    )
    support_dependence_score = _clamp01(
        (support_intensity * 0.3)
        + (high_support_success_rate * 0.26)
        + min(0.14, summary.normalized_hint_pressure * 0.12)
        + (summary.completion_rate * 0.1)
        + max(0.0, 0.42 - challenge_exposure) * 0.3
        + (
            0.1
            if support_intensity >= 0.75 and summary.completion_rate >= 0.66
            else 0.0
        )
        - (
            0.08
            if summary.normalized_error_pressure >= 0.95 and incomplete_rate >= 0.34
            else 0.0
        )
    )
    scores = {
        "productive_struggle": round(productive_struggle_score, 2),
        "overload": round(overload_score, 2),
        "disengagement": round(disengagement_score, 2),
        "support_dependence": round(support_dependence_score, 2),
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    signal, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    confidence = round(
        min(0.92, (top_score * 0.72) + (max(0.0, top_score - second_score) * 0.28)), 2
    )

    if signal == "productive_struggle":
        if (
            top_score < 0.52
            or challenge_exposure < 0.3
            or overload_score >= (productive_struggle_score - 0.02)
            or disengagement_score >= 0.5
        ):
            signal = "steady"
    elif signal == "overload":
        if top_score < 0.56 or productive_struggle_score >= (overload_score - 0.02):
            signal = "steady"
    elif signal == "disengagement":
        if top_score < 0.54 or productive_struggle_score >= disengagement_score:
            signal = "steady"
    elif signal == "support_dependence":
        if top_score < 0.54 or support_intensity < 0.5:
            signal = "steady"

    return CurrentEvidenceSignal(
        signal=signal,
        confidence=confidence
        if signal != "steady"
        else round(max(top_score - 0.12, 0.0), 2),
        challenge_exposure=round(challenge_exposure, 2),
        productive_struggle_score=round(productive_struggle_score, 2),
        overload_score=round(overload_score, 2),
        disengagement_score=round(disengagement_score, 2),
        support_dependence_score=round(support_dependence_score, 2),
        rationale=_current_evidence_rationale(
            signal=signal,
            challenge_exposure=challenge_exposure,
            high_support_success_rate=high_support_success_rate,
            summary=summary,
        ),
    )


def _normalized_response_time(observation: LearnerObservation) -> float:
    baseline = float(
        observation.expected_duration_ms or _baseline_duration_ms(observation.task_type)
    )
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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _challenge_exposure(observations: list[LearnerObservation]) -> float:
    if not observations:
        return 0.0
    challenge_events = sum(
        1
        for observation in observations
        if observation.support_level == ObservationSupportLevel.low
        and observation.task_type
        in {ObservationTaskType.practice, ObservationTaskType.assessment}
    )
    return challenge_events / len(observations)


def _support_intensity(observations: list[LearnerObservation]) -> float:
    if not observations:
        return 0.0
    support_map = {
        ObservationSupportLevel.low: 0.0,
        ObservationSupportLevel.medium: 0.5,
        ObservationSupportLevel.high: 1.0,
    }
    return sum(
        support_map[observation.support_level] for observation in observations
    ) / len(observations)


def _high_support_success_rate(observations: list[LearnerObservation]) -> float:
    if not observations:
        return 0.0
    successes = sum(
        1
        for observation in observations
        if observation.support_level == ObservationSupportLevel.high
        and observation.completed
        and observation.error_count <= 1
    )
    return successes / len(observations)


def _low_support_completion_rate(observations: list[LearnerObservation]) -> float:
    low_support = [
        observation
        for observation in observations
        if observation.support_level == ObservationSupportLevel.low
    ]
    if not low_support:
        return 0.0
    return sum(
        1.0 if observation.completed else 0.0 for observation in low_support
    ) / len(low_support)


def _current_evidence_rationale(
    *,
    signal: str,
    challenge_exposure: float,
    high_support_success_rate: float,
    summary: CalibratedObservationSummary,
) -> str | None:
    if signal == "productive_struggle":
        return "Recent observations show low-support challenge with recoverable friction, so the learner looks productively stretched rather than overloaded."
    if signal == "overload":
        return "Recent observations combine high pressure, slower-than-expected work, and low completion, so the learner looks overloaded right now."
    if signal == "disengagement":
        return "Recent observations show low completion with pause or switching friction that does not look like healthy challenge, so engagement likely needs recovery."
    if signal == "support_dependence":
        return "Recent observations stay successful mainly when support is heavy, so the learner appears reliant on scaffolds rather than ready for a larger release."
    if challenge_exposure >= 0.3 and summary.completion_rate >= 0.6:
        return "Recent observations show some challenge exposure, but the signal is not yet strong enough to classify confidently."
    if high_support_success_rate >= 0.5:
        return "Recent observations are informative but still mostly support-heavy, so the signal stays mixed for now."
    return None
