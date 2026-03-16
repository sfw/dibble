from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import GenerationModeCalibration, GenerationRequest
from dibble.services.learner_strategy_profiles import LearnerStrategySignalService
from dibble.services.router_calibration_signals import RouterCalibrationSignalService


@dataclass(slots=True)
class GenerationModeCalibrator:
    calibration_signal_service: RouterCalibrationSignalService
    strategy_signal_service: LearnerStrategySignalService
    minimum_confidence_for_bias: float = 0.65
    minimum_positive_outcome_score: float = 0.78
    minimum_improving_outcome_score: float = 0.7
    maximum_negative_outcome_score: float = 0.45
    maximum_declining_outcome_score: float = 0.72
    minimum_matched_runs_for_positive_bias: int = 2

    def calibrate_request(self, *, request: GenerationRequest) -> GenerationRequest:
        calibration = self.calibration_for(request=request)
        if calibration is None:
            return request
        return request.model_copy(update={"mode_calibration": calibration})

    def calibration_for(self, *, request: GenerationRequest) -> GenerationModeCalibration | None:
        signal = self.calibration_signal_service.signal_for(student_id=request.student_id, request=request)
        strategy = self.strategy_signal_service.strategy_for(student_id=request.student_id, request=request)
        support_bias = self._support_bias(signal=signal, strategy=strategy)
        if signal.source == "insufficient" and strategy.source == "insufficient" and support_bias == 0:
            return None

        source = signal.source if signal.source != "insufficient" else strategy.source
        calibration_signal = self._calibration_signal(signal=signal, strategy=strategy, support_bias=support_bias)
        confidence = signal.confidence if signal.source != "insufficient" else strategy.confidence
        average_run_outcome_score = (
            signal.average_run_outcome_score
            if signal.average_run_outcome_score is not None
            else strategy.average_run_outcome_score
        )
        matched_run_count = signal.matched_run_count if signal.source != "insufficient" else strategy.matched_run_count
        progress_signal = signal.progress_signal if signal.source != "insufficient" else strategy.progress_signal
        progress_delta = signal.progress_delta if signal.source != "insufficient" else strategy.progress_delta
        rationale = self._rationale(signal=signal, strategy=strategy, support_bias=support_bias)
        return GenerationModeCalibration(
            signal=calibration_signal,
            source=source,
            confidence=confidence,
            matched_run_count=matched_run_count,
            average_run_outcome_score=average_run_outcome_score,
            progress_signal=progress_signal,
            progress_delta=progress_delta,
            support_bias=support_bias,
            strategy_signal=strategy.signal,
            strategy_recovery_focus=strategy.recovery_focus,
            strategy_trajectory_state=strategy.trajectory_state,
            strategy_recommended_next_action=strategy.recommended_next_action,
            strategy_volatility_index=strategy.volatility_index,
            strategy_relapse_risk=strategy.relapse_risk,
            strategy_source=strategy.source,
            strategy_rationale=strategy.rationale,
            rationale=rationale,
        )

    def _support_bias(self, *, signal, strategy) -> int:
        if signal.confidence < self.minimum_confidence_for_bias:
            return strategy.support_bias
        calibration_bias = self._calibration_support_bias(signal=signal)
        if calibration_bias != 0:
            return calibration_bias
        return strategy.support_bias

    def _calibration_support_bias(self, *, signal) -> int:
        if signal.confidence < self.minimum_confidence_for_bias:
            return 0
        if (
            signal.progress_signal == "improving"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score >= self.minimum_improving_outcome_score
            and signal.matched_run_count >= self.minimum_matched_runs_for_positive_bias
        ):
            return 1
        if (
            signal.progress_signal == "declining"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score <= self.maximum_declining_outcome_score
            and signal.matched_run_count >= 2
        ):
            return -1
        if (
            signal.signal == "positive"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score >= self.minimum_positive_outcome_score
            and signal.matched_run_count >= self.minimum_matched_runs_for_positive_bias
        ):
            return 1
        if (
            signal.signal == "negative"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score <= self.maximum_negative_outcome_score
            and signal.matched_run_count >= 1
        ):
            return -1
        return 0

    def _calibration_signal(self, *, signal, strategy, support_bias: int) -> str:
        if signal.source != "insufficient":
            return signal.signal
        if support_bias > 0:
            return "positive"
        if support_bias < 0:
            return "negative"
        if strategy.signal != "insufficient":
            return "mixed"
        return "insufficient"

    def _rationale(self, *, signal, strategy, support_bias: int) -> str:
        if support_bias > 0 and signal.progress_signal == "improving":
            return (
                "Recent matching runs have been improving across sessions, so the generation mode can allow slightly more independence."
            )
        if support_bias < 0 and signal.progress_signal == "declining":
            return (
                "Recent matching runs have been declining across sessions, so the generation mode should add one step of modeled support."
            )
        if support_bias > 0:
            return (
                "Recent matching runs stayed durably positive, so the generation mode can allow slightly more independence."
            )
        if support_bias < 0:
            return (
                "Recent matching runs trended negative, so the generation mode should add one step of modeled support."
            )
        if strategy.signal == "independence_ready":
            return strategy.rationale or (
                "Long-horizon learner strategy shows the learner is ready for slightly more independent practice."
            )
        if strategy.signal == "support_intensive":
            return strategy.rationale or (
                "Long-horizon learner strategy shows the learner still needs one more step of modeled support."
            )
        if strategy.signal == "stabilizing":
            return strategy.rationale or (
                "Long-horizon learner strategy suggests staying with guided practice while recent gains stabilize."
            )
        if strategy.trajectory_state == "plateaued":
            return strategy.rationale or (
                "Long-horizon learner strategy shows the learner has plateaued, so the next step should vary support instead of repeating the same independence level."
            )
        if strategy.trajectory_state == "volatile":
            return strategy.rationale or (
                "Long-horizon learner strategy shows uneven outcomes, so the next step should stabilize support before pushing ahead."
            )
        if strategy.trajectory_state == "relapsing":
            return strategy.rationale or (
                "Long-horizon learner strategy shows relapse across sessions, so the next step should rebuild prerequisite support."
            )
        return (
            "Recent matching runs were informative but not decisive enough to override the baseline mode heuristics."
        )
