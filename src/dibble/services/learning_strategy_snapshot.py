from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LearningStrategyProfileSnapshot:
    average_run_outcome_score: float | None = None
    average_run_confidence: float = 0.0
    matched_run_count: int = 0
    matched_session_count: int = 0
    positive_run_rate: float = 0.0
    negative_run_rate: float = 0.0
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0
    support_bias: int = 0
    recovery_focus: str = "monitor"
    trajectory_state: str = "insufficient"
    recommended_next_action: str = "monitor"
    volatility_index: float = 0.0
    relapse_risk: float = 0.0
    signal: str = "insufficient"
    rationale: str | None = None


def _strategy_signal(
    *,
    support_bias: int,
    progress_signal: str,
    matched_session_count: int,
) -> str:
    if matched_session_count <= 0:
        return "insufficient"
    if support_bias < 0:
        return "support_intensive"
    if support_bias > 0:
        return "independence_ready"
    if progress_signal == "improving":
        return "stabilizing"
    return "monitor"


def _support_bias(
    *,
    average_run_outcome_score: float | None,
    average_run_confidence: float,
    matched_session_count: int,
    positive_run_rate: float,
    negative_run_rate: float,
    progress_signal: str,
) -> int:
    if average_run_outcome_score is None:
        return 0
    if matched_session_count < 2 or average_run_confidence < 0.6:
        return 0
    if progress_signal == "declining" and average_run_outcome_score <= 0.72:
        return -1
    if negative_run_rate >= 0.4 and average_run_outcome_score <= 0.58:
        return -1
    if (
        progress_signal == "improving"
        and positive_run_rate >= 0.5
        and average_run_outcome_score >= 0.7
    ):
        return 1
    if positive_run_rate >= 0.7 and average_run_outcome_score >= 0.78:
        return 1
    return 0


def _recovery_focus(
    *,
    support_bias: int,
    progress_signal: str,
    negative_run_rate: float,
) -> str:
    if support_bias < 0 and (
        progress_signal == "declining" or negative_run_rate >= 0.5
    ):
        return "prerequisite_rebuild"
    if support_bias < 0:
        return "targeted_repair"
    if support_bias > 0:
        return "independent_practice"
    if progress_signal == "improving":
        return "guided_practice"
    return "monitor"


def _volatility_index(
    *,
    positive_run_rate: float,
    negative_run_rate: float,
    matched_session_count: int,
) -> float:
    if matched_session_count < 3:
        return 0.0
    return round(min(1.0, 2.0 * min(positive_run_rate, negative_run_rate)), 2)


def _relapse_risk(
    *,
    average_run_outcome_score: float | None,
    average_run_confidence: float,
    matched_session_count: int,
    negative_run_rate: float,
    progress_signal: str,
    progress_delta: float,
) -> float:
    if average_run_outcome_score is None or matched_session_count < 2:
        return 0.0
    score = 0.0
    if progress_signal == "declining":
        score += 0.4
    if negative_run_rate >= 0.4:
        score += 0.3
    elif negative_run_rate >= 0.25:
        score += 0.15
    if average_run_outcome_score <= 0.65:
        score += 0.2
    elif average_run_outcome_score <= 0.75:
        score += 0.1
    if progress_delta <= -0.12:
        score += 0.1
    confidence_factor = 0.7 + min(0.3, max(0.0, average_run_confidence - 0.5))
    return round(min(1.0, score * confidence_factor), 2)


def _trajectory_state(
    *,
    average_run_outcome_score: float | None,
    average_run_confidence: float,
    matched_session_count: int,
    progress_signal: str,
    progress_delta: float,
    support_bias: int,
    volatility_index: float,
    relapse_risk: float,
) -> str:
    if average_run_outcome_score is None or matched_session_count < 2:
        return "insufficient"
    if relapse_risk >= 0.55 and average_run_outcome_score <= 0.78:
        return "relapsing"
    if volatility_index >= 0.35 and matched_session_count >= 3:
        return "volatile"
    if (
        progress_signal == "stable"
        and matched_session_count >= 3
        and average_run_confidence >= 0.65
        and abs(progress_delta) < 0.05
        and 0.58 <= average_run_outcome_score <= 0.76
    ):
        return "plateaued"
    if (
        progress_signal == "improving"
        and average_run_outcome_score >= 0.78
        and support_bias >= 0
    ):
        return "accelerating"
    if progress_signal == "improving":
        return "consolidating"
    return "monitor"


def _recommended_next_action(
    *,
    trajectory_state: str,
    support_bias: int,
) -> str:
    if trajectory_state == "relapsing":
        return "rebuild_prerequisite"
    if trajectory_state == "volatile":
        return "stabilize_support"
    if trajectory_state == "plateaued":
        return "introduce_varied_support"
    if trajectory_state == "accelerating":
        return "check_transfer_readiness"
    if trajectory_state == "consolidating":
        return "guided_practice"
    if support_bias < 0:
        return "stabilize_support"
    if support_bias > 0:
        return "fade_support"
    return "monitor"


def _rationale(
    *,
    signal: str,
    trajectory_state: str,
    recommended_next_action: str,
    average_run_outcome_score: float | None,
    average_run_confidence: float,
    progress_signal: str,
    progress_delta: float,
    volatility_index: float,
    relapse_risk: float,
) -> str | None:
    if average_run_outcome_score is None:
        return None
    if trajectory_state == "relapsing":
        return (
            f"Recent matching runs show relapse risk {relapse_risk:.2f} "
            f"(score {average_run_outcome_score:.2f}, trend {progress_signal} {progress_delta:+.2f}), "
            f"so the next step should {recommended_next_action.replace('_', ' ')}."
        )
    if trajectory_state == "plateaued":
        return (
            f"Recent matching runs have plateaued around score {average_run_outcome_score:.2f} "
            f"with little movement across sessions, so the next step should {recommended_next_action.replace('_', ' ')}."
        )
    if trajectory_state == "volatile":
        return (
            f"Recent matching runs are volatile (index {volatility_index:.2f}) despite average score "
            f"{average_run_outcome_score:.2f}, so the next step should {recommended_next_action.replace('_', ' ')}."
        )
    if trajectory_state == "accelerating":
        return (
            f"Recent matching runs are accelerating across sessions "
            f"(score {average_run_outcome_score:.2f}, trend {progress_delta:+.2f}), "
            f"so the next step should {recommended_next_action.replace('_', ' ')}."
        )
    if trajectory_state == "consolidating":
        return (
            f"Recent matching runs are consolidating ({progress_delta:+.2f}) with enough confidence "
            f"to keep {recommended_next_action.replace('_', ' ')}."
        )
    if signal == "support_intensive":
        return (
            f"Recent matching runs stayed weak enough across sessions "
            f"(score {average_run_outcome_score:.2f}, confidence {average_run_confidence:.2f}) "
            f"that the learner should rebuild support before more independence."
        )
    if signal == "independence_ready":
        return (
            f"Recent matching runs stayed strong across sessions "
            f"(score {average_run_outcome_score:.2f}, confidence {average_run_confidence:.2f}) "
            f"so support can fade toward more independent practice."
        )
    if signal == "stabilizing":
        return (
            f"Recent matching runs are improving ({progress_delta:+.2f}) with enough confidence "
            f"to keep guided practice while support gradually fades."
        )
    return (
        f"Recent matching runs are being monitored "
        f"(score {average_run_outcome_score:.2f}, confidence {average_run_confidence:.2f}, trend {progress_signal})."
    )


def build_strategy_snapshot(
    *,
    average_run_outcome_score: float | None,
    average_run_confidence: float,
    matched_run_count: int,
    matched_session_count: int,
    positive_run_rate: float,
    negative_run_rate: float,
    progress_signal: str,
    progress_delta: float,
) -> LearningStrategyProfileSnapshot:
    support_bias = _support_bias(
        average_run_outcome_score=average_run_outcome_score,
        average_run_confidence=average_run_confidence,
        matched_session_count=matched_session_count,
        positive_run_rate=positive_run_rate,
        negative_run_rate=negative_run_rate,
        progress_signal=progress_signal,
    )
    signal = _strategy_signal(
        support_bias=support_bias,
        progress_signal=progress_signal,
        matched_session_count=matched_session_count,
    )
    recovery_focus = _recovery_focus(
        support_bias=support_bias,
        progress_signal=progress_signal,
        negative_run_rate=negative_run_rate,
    )
    volatility_index = _volatility_index(
        positive_run_rate=positive_run_rate,
        negative_run_rate=negative_run_rate,
        matched_session_count=matched_session_count,
    )
    relapse_risk = _relapse_risk(
        average_run_outcome_score=average_run_outcome_score,
        average_run_confidence=average_run_confidence,
        matched_session_count=matched_session_count,
        negative_run_rate=negative_run_rate,
        progress_signal=progress_signal,
        progress_delta=progress_delta,
    )
    trajectory_state = _trajectory_state(
        average_run_outcome_score=average_run_outcome_score,
        average_run_confidence=average_run_confidence,
        matched_session_count=matched_session_count,
        progress_signal=progress_signal,
        progress_delta=progress_delta,
        support_bias=support_bias,
        volatility_index=volatility_index,
        relapse_risk=relapse_risk,
    )
    recommended_next_action = _recommended_next_action(
        trajectory_state=trajectory_state,
        support_bias=support_bias,
    )
    return LearningStrategyProfileSnapshot(
        average_run_outcome_score=average_run_outcome_score,
        average_run_confidence=average_run_confidence,
        matched_run_count=matched_run_count,
        matched_session_count=matched_session_count,
        positive_run_rate=positive_run_rate,
        negative_run_rate=negative_run_rate,
        progress_signal=progress_signal,
        progress_delta=progress_delta,
        support_bias=support_bias,
        recovery_focus=recovery_focus,
        trajectory_state=trajectory_state,
        recommended_next_action=recommended_next_action,
        volatility_index=volatility_index,
        relapse_risk=relapse_risk,
        signal=signal,
        rationale=_rationale(
            signal=signal,
            trajectory_state=trajectory_state,
            recommended_next_action=recommended_next_action,
            average_run_outcome_score=average_run_outcome_score,
            average_run_confidence=average_run_confidence,
            progress_signal=progress_signal,
            progress_delta=progress_delta,
            volatility_index=volatility_index,
            relapse_risk=relapse_risk,
        ),
    )
