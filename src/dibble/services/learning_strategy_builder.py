from __future__ import annotations

from dataclasses import dataclass

from dibble.models.telemetry import AuditEvent
from dibble.services.learning_strategy_snapshot import (
    LearningStrategyProfileSnapshot,
    build_strategy_snapshot,
)


@dataclass(slots=True)
class LearningStrategyProfileBuilder:
    def build_from_summary_event(
        self,
        *,
        summary_event: AuditEvent,
        progress_event: AuditEvent | None = None,
    ) -> LearningStrategyProfileSnapshot | None:
        if summary_event.event_type != "learning.run.summary":
            return None
        average_run_outcome_score = self._float_value(
            progress_event.payload.get("average_run_outcome_score")
            if progress_event is not None
            else summary_event.payload.get("run_summary_score")
        )
        average_run_confidence = self._float_value(
            progress_event.payload.get("average_run_confidence")
            if progress_event is not None
            else summary_event.payload.get("run_calibration_confidence"),
            default=0.0,
        )
        matched_run_count = self._int_value(
            progress_event.payload.get("matched_run_count")
            if progress_event is not None
            else 1,
            default=1,
        )
        matched_session_count = self._int_value(
            progress_event.payload.get("matched_session_count")
            if progress_event is not None
            else (1 if summary_event.payload.get("learning_session_id") else 0),
        )
        positive_run_rate = self._float_value(
            progress_event.payload.get("positive_run_rate")
            if progress_event is not None
            else (
                1.0
                if summary_event.payload.get("run_calibration_signal") == "positive"
                else 0.0
            ),
            default=0.0,
        )
        negative_run_rate = self._float_value(
            progress_event.payload.get("negative_run_rate")
            if progress_event is not None
            else (
                1.0
                if summary_event.payload.get("run_calibration_signal") == "negative"
                else 0.0
            ),
            default=0.0,
        )
        progress_signal = (
            str(progress_event.payload.get("progress_signal", "tentative"))
            if progress_event is not None
            else "tentative"
        )
        progress_delta = self._float_value(
            progress_event.payload.get("progress_delta")
            if progress_event is not None
            else 0.0,
            default=0.0,
        )
        return build_strategy_snapshot(
            average_run_outcome_score=average_run_outcome_score,
            average_run_confidence=average_run_confidence,
            matched_run_count=matched_run_count,
            matched_session_count=matched_session_count,
            positive_run_rate=positive_run_rate,
            negative_run_rate=negative_run_rate,
            progress_signal=progress_signal,
            progress_delta=progress_delta,
        )

    def _float_value(self, value: object, default: float | None = None) -> float | None:
        if value is None:
            return default
        return float(value)

    def _int_value(self, value: object, default: int = 0) -> int:
        if value is None:
            return default
        return int(value)
