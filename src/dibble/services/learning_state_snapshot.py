from __future__ import annotations

from dataclasses import dataclass

from dibble.models.profile import SignalLevel


@dataclass(frozen=True, slots=True)
class LearningStateProfileSnapshot:
    signal: str = "insufficient"
    average_run_outcome_score: float | None = None
    average_run_confidence: float = 0.0
    matched_run_count: int = 0
    matched_session_count: int = 0
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0
    strategy_signal: str = "insufficient"
    strategy_trajectory_state: str = "insufficient"
    engagement: SignalLevel = SignalLevel.medium
    frustration: SignalLevel = SignalLevel.none
    confusion: SignalLevel = SignalLevel.low
    confidence: float = 0.5
    intrinsic_load: float = 0.3
    extraneous_load: float = 0.2
    germane_load: float = 0.4
    total_load: float = 0.4
    capacity_utilization: float = 0.4
    confidence_calibration: float = 0.5
    help_seeking: SignalLevel = SignalLevel.low
    help_seeking_effectiveness: float = 0.5
    self_monitoring: float = 0.5
    affective_reliability: float = 0.0
    load_reliability: float = 0.0
    recovery_stability: float = 0.0
    overload_risk: float = 0.0
    metacognitive_reliability: float = 0.0
    rationale: str | None = None


def _clamp(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def _signal_from_score(score: float) -> SignalLevel:
    if score >= 0.8:
        return SignalLevel.high
    if score >= 0.5:
        return SignalLevel.medium
    if score >= 0.2:
        return SignalLevel.low
    return SignalLevel.none


def _profile_signal(
    *,
    average_run_confidence: float,
    matched_session_count: int,
    progress_signal: str,
    strategy_signal: str,
    trajectory_state: str,
) -> str:
    if matched_session_count < 2 or average_run_confidence < 0.55:
        return "tentative"
    if strategy_signal == "support_intensive" or trajectory_state in {
        "relapsing",
        "plateaued",
    }:
        return "support_needed"
    if progress_signal == "declining":
        return "support_needed"
    if strategy_signal == "independence_ready" and trajectory_state in {
        "accelerating",
        "consolidating",
    }:
        return "independence_ready"
    if progress_signal == "improving":
        return "recovering"
    return "monitor"


def _rationale(
    *,
    signal: str,
    average_run_outcome_score: float | None,
    progress_signal: str,
    progress_delta: float,
    trajectory_state: str,
) -> str | None:
    if average_run_outcome_score is None:
        return None
    if signal == "support_needed":
        return (
            f"Cross-session outcomes remain fragile (score {average_run_outcome_score:.2f}, "
            f"trend {progress_signal} {progress_delta:+.2f}, trajectory {trajectory_state}), "
            "so live learner state should stay support-seeking."
        )
    if signal == "independence_ready":
        return (
            f"Cross-session outcomes remain strong (score {average_run_outcome_score:.2f}, "
            f"trend {progress_signal} {progress_delta:+.2f}, trajectory {trajectory_state}), "
            "so live learner state can lean toward more confident independence."
        )
    if signal == "recovering":
        return (
            f"Cross-session outcomes are improving (score {average_run_outcome_score:.2f}, "
            f"delta {progress_delta:+.2f}), so live learner state should reflect a steadier recovery."
        )
    if signal == "tentative":
        return (
            f"Only light cross-session evidence is available (score {average_run_outcome_score:.2f}), "
            "so the durable learner-state profile remains tentative."
        )
    return (
        f"Cross-session outcomes are currently being monitored "
        f"(score {average_run_outcome_score:.2f}, trend {progress_signal})."
    )


def build_state_snapshot(
    *,
    average_run_outcome_score: float | None,
    average_run_confidence: float,
    matched_run_count: int,
    matched_session_count: int,
    progress_signal: str,
    progress_delta: float,
    strategy_signal: str,
    trajectory_state: str,
) -> LearningStateProfileSnapshot:
    if average_run_outcome_score is None:
        return LearningStateProfileSnapshot()

    performance = average_run_outcome_score
    improvement = max(0.0, progress_delta)
    decline = max(0.0, -progress_delta)
    relapse_penalty = 0.18 if trajectory_state == "relapsing" else 0.0
    plateau_penalty = 0.09 if trajectory_state == "plateaued" else 0.0
    volatility_penalty = 0.1 if trajectory_state == "volatile" else 0.0
    acceleration_bonus = 0.08 if trajectory_state == "accelerating" else 0.0
    support_penalty = 0.1 if strategy_signal == "support_intensive" else 0.0
    independence_bonus = 0.08 if strategy_signal == "independence_ready" else 0.0

    signal = _profile_signal(
        average_run_confidence=average_run_confidence,
        matched_session_count=matched_session_count,
        progress_signal=progress_signal,
        strategy_signal=strategy_signal,
        trajectory_state=trajectory_state,
    )

    engagement_score = _clamp(
        0.32
        + (performance * 0.42)
        + (improvement * 0.3)
        + independence_bonus
        - (decline * 0.22)
        - relapse_penalty
        - support_penalty
    )
    frustration_score = _clamp(
        0.08
        + ((1.0 - performance) * 0.42)
        + (decline * 0.34)
        + relapse_penalty
        + plateau_penalty
        + support_penalty
        - (improvement * 0.18)
        - acceleration_bonus
    )
    confusion_score = _clamp(
        0.12
        + ((1.0 - performance) * 0.28)
        + (decline * 0.28)
        + volatility_penalty
        + plateau_penalty
        - (improvement * 0.12)
    )
    confidence = _clamp(
        0.3
        + (performance * 0.44)
        + (improvement * 0.12)
        + independence_bonus
        - (decline * 0.16)
        - relapse_penalty
    )

    intrinsic_load = _clamp(
        0.24
        + ((1.0 - performance) * 0.18)
        + (support_penalty * 0.8)
        + plateau_penalty
        - (independence_bonus * 0.5)
    )
    extraneous_load = _clamp(
        0.16
        + (decline * 0.16)
        + (volatility_penalty * 0.9)
        + support_penalty
        - (improvement * 0.06)
        - (independence_bonus * 0.35)
    )
    germane_load = _clamp(
        0.28
        + (performance * 0.18)
        + (improvement * 0.18)
        + (independence_bonus * 0.35)
        - (decline * 0.08)
        - (relapse_penalty * 0.3)
    )
    total_load = _clamp(
        0.36
        + ((1.0 - performance) * 0.22)
        + (decline * 0.2)
        + (support_penalty * 0.8)
        + relapse_penalty
        + (volatility_penalty * 0.7)
        - (improvement * 0.08)
        - acceleration_bonus
    )
    capacity_utilization = _clamp(
        total_load
        + (
            0.1
            if frustration_score >= 0.8
            else 0.05
            if frustration_score >= 0.5
            else 0.0
        )
        + (0.06 if confusion_score >= 0.5 else 0.0)
    )

    confidence_calibration = _clamp(
        0.32
        + (performance * 0.42)
        + (improvement * 0.12)
        + (independence_bonus * 0.4)
        - (decline * 0.18)
        - relapse_penalty
    )
    help_seeking_score = _clamp(
        0.08
        + ((1.0 - performance) * 0.32)
        + (decline * 0.18)
        + (support_penalty * 1.1)
        + plateau_penalty
        - (improvement * 0.08)
        - independence_bonus
    )
    help_seeking_effectiveness = _clamp(
        0.34
        + (performance * 0.28)
        + (improvement * 0.12)
        + (independence_bonus * 0.2)
        - (decline * 0.14)
        - (volatility_penalty * 0.6)
    )
    self_monitoring = _clamp(
        0.3
        + (confidence_calibration * 0.34)
        + (performance * 0.16)
        + (improvement * 0.12)
        - (decline * 0.12)
        - (relapse_penalty * 0.4)
    )
    affective_reliability = _clamp(
        0.2
        + (average_run_confidence * 0.24)
        + (
            0.06
            if matched_session_count >= 4
            else 0.03
            if matched_session_count >= 2
            else 0.0
        )
        + (improvement * 0.08)
        - (decline * 0.12)
        - (volatility_penalty * 0.5)
        - (plateau_penalty * 0.3)
    )
    recovery_stability = _clamp(
        0.2
        + (performance * 0.24)
        + (average_run_confidence * 0.24)
        + (improvement * 0.18)
        + (
            0.08
            if matched_session_count >= 4
            else 0.04
            if matched_session_count >= 2
            else 0.0
        )
        - (decline * 0.16)
        - (relapse_penalty * 0.9)
        - (volatility_penalty * 0.7)
        - (plateau_penalty * 0.4)
    )
    overload_risk = _clamp(
        0.12
        + (total_load * 0.34)
        + (frustration_score * 0.2)
        + (confusion_score * 0.16)
        + (decline * 0.16)
        + (support_penalty * 0.6)
        + (relapse_penalty * 0.75)
        - (improvement * 0.08)
        - (independence_bonus * 0.4)
    )
    load_reliability = _clamp(
        0.22
        + (average_run_confidence * 0.22)
        + (
            0.06
            if matched_session_count >= 4
            else 0.03
            if matched_session_count >= 2
            else 0.0
        )
        + (recovery_stability * 0.12)
        + (overload_risk * 0.08)
        - (volatility_penalty * 0.42)
        - abs(total_load - capacity_utilization) * 0.12
    )
    metacognitive_reliability = _clamp(
        0.18
        + (confidence_calibration * 0.26)
        + (help_seeking_effectiveness * 0.22)
        + (self_monitoring * 0.24)
        + (average_run_confidence * 0.12)
        + (improvement * 0.08)
        - (decline * 0.08)
        - (volatility_penalty * 0.45)
    )

    return LearningStateProfileSnapshot(
        signal=signal,
        average_run_outcome_score=average_run_outcome_score,
        average_run_confidence=average_run_confidence,
        matched_run_count=matched_run_count,
        matched_session_count=matched_session_count,
        progress_signal=progress_signal,
        progress_delta=progress_delta,
        strategy_signal=strategy_signal,
        strategy_trajectory_state=trajectory_state,
        engagement=_signal_from_score(engagement_score),
        frustration=_signal_from_score(frustration_score),
        confusion=_signal_from_score(confusion_score),
        confidence=round(confidence, 2),
        intrinsic_load=round(intrinsic_load, 2),
        extraneous_load=round(extraneous_load, 2),
        germane_load=round(germane_load, 2),
        total_load=round(total_load, 2),
        capacity_utilization=round(capacity_utilization, 2),
        confidence_calibration=round(confidence_calibration, 2),
        help_seeking=_signal_from_score(help_seeking_score),
        help_seeking_effectiveness=round(help_seeking_effectiveness, 2),
        self_monitoring=round(self_monitoring, 2),
        affective_reliability=round(affective_reliability, 2),
        load_reliability=round(load_reliability, 2),
        recovery_stability=round(recovery_stability, 2),
        overload_risk=round(overload_risk, 2),
        metacognitive_reliability=round(metacognitive_reliability, 2),
        rationale=_rationale(
            signal=signal,
            average_run_outcome_score=average_run_outcome_score,
            progress_signal=progress_signal,
            progress_delta=progress_delta,
            trajectory_state=trajectory_state,
        ),
    )
