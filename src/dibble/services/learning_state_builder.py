from __future__ import annotations

from dataclasses import dataclass

from dibble.models.telemetry import AuditEvent
from dibble.services.learning_state_snapshot import (
    LearningStateProfileSnapshot,
    build_state_snapshot,
)


@dataclass(slots=True)
class LearningStateProfileBuilder:
    def build_from_summary_event(
        self,
        *,
        summary_event: AuditEvent,
        progress_event: AuditEvent | None = None,
        strategy_event: AuditEvent | None = None,
    ) -> LearningStateProfileSnapshot | None:
        if summary_event.event_type != "learning.run.summary":
            return None
        average_run_outcome_score = self._float_value(
            strategy_event.payload.get("average_run_outcome_score")
            if strategy_event is not None
            else (
                progress_event.payload.get("average_run_outcome_score")
                if progress_event is not None
                else summary_event.payload.get("run_summary_score")
            )
        )
        average_run_confidence = self._float_value(
            strategy_event.payload.get("average_run_confidence")
            if strategy_event is not None
            else (
                progress_event.payload.get("average_run_confidence")
                if progress_event is not None
                else summary_event.payload.get("run_calibration_confidence")
            ),
            default=0.0,
        )
        matched_run_count = self._int_value(
            strategy_event.payload.get("matched_run_count")
            if strategy_event is not None
            else (
                progress_event.payload.get("matched_run_count")
                if progress_event is not None
                else 1
            ),
            default=1,
        )
        matched_session_count = self._int_value(
            strategy_event.payload.get("matched_session_count")
            if strategy_event is not None
            else (
                progress_event.payload.get("matched_session_count")
                if progress_event is not None
                else (1 if summary_event.payload.get("learning_session_id") else 0)
            ),
            default=0,
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
        strategy_signal = (
            str(strategy_event.payload.get("strategy_signal", "insufficient"))
            if strategy_event is not None
            else "insufficient"
        )
        trajectory_state = (
            str(strategy_event.payload.get("strategy_trajectory_state", "insufficient"))
            if strategy_event is not None
            else "insufficient"
        )
        return build_state_snapshot(
            average_run_outcome_score=average_run_outcome_score,
            average_run_confidence=average_run_confidence,
            matched_run_count=matched_run_count,
            matched_session_count=matched_session_count,
            progress_signal=progress_signal,
            progress_delta=progress_delta,
            strategy_signal=strategy_signal,
            trajectory_state=trajectory_state,
        )

    def _float_value(self, value: object, default: float | None = None) -> float | None:
        if value is None:
            return default
        return float(value)

    def _int_value(self, value: object, default: int = 0) -> int:
        if value is None:
            return default
        return int(value)
