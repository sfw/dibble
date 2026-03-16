from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import GenerationModeCalibration, GenerationRequest
from dibble.services.router_calibration_signals import RouterCalibrationSignalService


@dataclass(slots=True)
class GenerationModeCalibrator:
    calibration_signal_service: RouterCalibrationSignalService
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
        if signal.source == "insufficient":
            return None

        support_bias = self._support_bias(signal=signal)
        rationale = self._rationale(signal=signal, support_bias=support_bias)
        return GenerationModeCalibration(
            signal=signal.signal,
            source=signal.source,
            confidence=signal.confidence,
            matched_run_count=signal.matched_run_count,
            average_run_outcome_score=signal.average_run_outcome_score,
            progress_signal=signal.progress_signal,
            progress_delta=signal.progress_delta,
            support_bias=support_bias,
            rationale=rationale,
        )

    def _support_bias(self, *, signal) -> int:
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

    def _rationale(self, *, signal, support_bias: int) -> str:
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
        return (
            "Recent matching runs were informative but not decisive enough to override the baseline mode heuristics."
        )
