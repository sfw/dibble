from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerStrategySummary
from dibble.models.telemetry import AuditEvent
from dibble.services.learning_progress_profiles import LearningProgressProfileResolver
from dibble.services.learning_strategy_resolver import LearningStrategyProfileResolver
from dibble.services.learning_strategy_snapshot import build_strategy_snapshot
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class LearnerStrategySignalService:
    audit_store: AuditStore
    profile_resolver: LearningStrategyProfileResolver = field(
        default_factory=LearningStrategyProfileResolver
    )
    progress_profile_resolver: LearningProgressProfileResolver = field(
        default_factory=LearningProgressProfileResolver
    )
    max_events: int = 500

    def strategy_for(
        self, *, student_id: UUID, request: GenerationRequest
    ) -> LearnerStrategySummary:
        events = self.audit_store.list(limit=self.max_events)
        strategy_events = [
            event
            for event in events
            if event.event_type == "learning.strategy.profile"
            and event.student_id == student_id
        ]
        matched_strategy_profiles = self.profile_resolver.matched_profile_events(
            profile_events=strategy_events,
            request=request,
        )
        if matched_strategy_profiles:
            return self._aggregate_strategy_events(matched_strategy_profiles)

        progress_events = [
            event
            for event in events
            if event.event_type == "learning.progress.profile"
            and event.student_id == student_id
        ]
        matched_progress_profiles = (
            self.progress_profile_resolver.matched_profile_events(
                profile_events=progress_events,
                request=request,
            )
        )
        if matched_progress_profiles:
            return self._aggregate_progress_events(matched_progress_profiles)

        return LearnerStrategySummary()

    def latest_for_student(self, *, student_id: UUID) -> LearnerStrategySummary:
        events = self.audit_store.list(limit=self.max_events)
        strategy_event = next(
            (
                event
                for event in events
                if event.event_type == "learning.strategy.profile"
                and event.student_id == student_id
            ),
            None,
        )
        if strategy_event is not None:
            return self._summary_from_payload(
                payload=strategy_event.payload,
                source="strategy_profile",
                updated_at=strategy_event.created_at,
            )

        progress_event = next(
            (
                event
                for event in events
                if event.event_type == "learning.progress.profile"
                and event.student_id == student_id
            ),
            None,
        )
        if progress_event is None:
            return LearnerStrategySummary()
        snapshot = build_strategy_snapshot(
            average_run_outcome_score=self._maybe_float(
                progress_event.payload.get("average_run_outcome_score")
            ),
            average_run_confidence=float(
                progress_event.payload.get("average_run_confidence", 0.0)
            ),
            matched_run_count=int(progress_event.payload.get("matched_run_count", 0)),
            matched_session_count=int(
                progress_event.payload.get("matched_session_count", 0)
            ),
            positive_run_rate=float(
                progress_event.payload.get("positive_run_rate", 0.0)
            ),
            negative_run_rate=float(
                progress_event.payload.get("negative_run_rate", 0.0)
            ),
            progress_signal=str(
                progress_event.payload.get("progress_signal", "insufficient")
            ),
            progress_delta=float(progress_event.payload.get("progress_delta", 0.0)),
        )
        return LearnerStrategySummary(
            signal=snapshot.signal,
            source="progress_profile",
            support_bias=snapshot.support_bias,
            recovery_focus=snapshot.recovery_focus,
            trajectory_state=snapshot.trajectory_state,
            recommended_next_action=snapshot.recommended_next_action,
            confidence=snapshot.average_run_confidence,
            average_run_outcome_score=snapshot.average_run_outcome_score,
            matched_run_count=snapshot.matched_run_count,
            matched_session_count=snapshot.matched_session_count,
            progress_signal=snapshot.progress_signal,
            progress_delta=snapshot.progress_delta,
            volatility_index=snapshot.volatility_index,
            relapse_risk=snapshot.relapse_risk,
            rationale=snapshot.rationale,
            updated_at=progress_event.created_at,
        )

    def _aggregate_strategy_events(
        self, profile_events: list[AuditEvent]
    ) -> LearnerStrategySummary:
        total_run_count = sum(
            max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        )
        if total_run_count <= 0:
            return LearnerStrategySummary()
        support_bias_score = round(
            sum(
                int(event.payload.get("strategy_support_bias", 0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count
        )
        support_bias = max(-1, min(1, support_bias_score))
        progress_signal = self._dominant_label(
            labels=[
                str(event.payload.get("progress_signal", "insufficient"))
                for event in profile_events
            ]
        )
        strategy_signal = self._dominant_label(
            labels=[
                str(event.payload.get("strategy_signal", "insufficient"))
                for event in profile_events
            ]
        )
        recovery_focus = self._dominant_label(
            labels=[
                str(event.payload.get("strategy_recovery_focus", "monitor"))
                for event in profile_events
            ]
        )
        trajectory_state = self._dominant_label(
            labels=[
                str(event.payload.get("strategy_trajectory_state", "insufficient"))
                for event in profile_events
            ]
        )
        recommended_next_action = self._dominant_label(
            labels=[
                str(event.payload.get("strategy_recommended_next_action", "monitor"))
                for event in profile_events
            ]
        )
        progress_delta = round(
            sum(
                float(event.payload.get("progress_delta", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        average_run_outcome_score = round(
            sum(
                float(event.payload.get("average_run_outcome_score", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        average_confidence = round(
            sum(
                float(event.payload.get("average_run_confidence", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        volatility_index = round(
            sum(
                float(event.payload.get("strategy_volatility_index", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        relapse_risk = round(
            sum(
                float(event.payload.get("strategy_relapse_risk", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        matched_session_count = max(
            int(event.payload.get("matched_session_count", 0))
            for event in profile_events
        )
        rationale = next(
            (
                str(event.payload.get("strategy_rationale"))
                for event in profile_events
                if event.payload.get("strategy_rationale")
            ),
            None,
        )
        return LearnerStrategySummary(
            signal=strategy_signal,
            source="strategy_profile",
            support_bias=support_bias,
            recovery_focus=recovery_focus,
            trajectory_state=trajectory_state,
            recommended_next_action=recommended_next_action,
            confidence=average_confidence,
            average_run_outcome_score=average_run_outcome_score,
            matched_run_count=total_run_count,
            matched_session_count=matched_session_count,
            progress_signal=progress_signal,
            progress_delta=progress_delta,
            volatility_index=volatility_index,
            relapse_risk=relapse_risk,
            rationale=rationale,
            updated_at=profile_events[0].created_at,
        )

    def _aggregate_progress_events(
        self, profile_events: list[AuditEvent]
    ) -> LearnerStrategySummary:
        total_run_count = sum(
            max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        )
        if total_run_count <= 0:
            return LearnerStrategySummary()
        snapshot = build_strategy_snapshot(
            average_run_outcome_score=round(
                sum(
                    float(event.payload.get("average_run_outcome_score", 0.0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count,
                2,
            ),
            average_run_confidence=round(
                sum(
                    float(event.payload.get("average_run_confidence", 0.0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count,
                2,
            ),
            matched_run_count=total_run_count,
            matched_session_count=max(
                int(event.payload.get("matched_session_count", 0))
                for event in profile_events
            ),
            positive_run_rate=round(
                sum(
                    float(event.payload.get("positive_run_rate", 0.0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count,
                2,
            ),
            negative_run_rate=round(
                sum(
                    float(event.payload.get("negative_run_rate", 0.0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count,
                2,
            ),
            progress_signal=self._dominant_label(
                labels=[
                    str(event.payload.get("progress_signal", "insufficient"))
                    for event in profile_events
                ]
            ),
            progress_delta=round(
                sum(
                    float(event.payload.get("progress_delta", 0.0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count,
                2,
            ),
        )
        return LearnerStrategySummary(
            signal=snapshot.signal,
            source="progress_profile",
            support_bias=snapshot.support_bias,
            recovery_focus=snapshot.recovery_focus,
            trajectory_state=snapshot.trajectory_state,
            recommended_next_action=snapshot.recommended_next_action,
            confidence=snapshot.average_run_confidence,
            average_run_outcome_score=snapshot.average_run_outcome_score,
            matched_run_count=snapshot.matched_run_count,
            matched_session_count=snapshot.matched_session_count,
            progress_signal=snapshot.progress_signal,
            progress_delta=snapshot.progress_delta,
            volatility_index=snapshot.volatility_index,
            relapse_risk=snapshot.relapse_risk,
            rationale=snapshot.rationale,
            updated_at=profile_events[0].created_at,
        )

    def _summary_from_payload(
        self,
        *,
        payload: dict[str, object],
        source: str,
        updated_at: datetime,
    ) -> LearnerStrategySummary:
        return LearnerStrategySummary(
            signal=str(payload.get("strategy_signal", "insufficient")),
            source=source,
            support_bias=int(payload.get("strategy_support_bias", 0)),
            recovery_focus=str(payload.get("strategy_recovery_focus", "monitor")),
            trajectory_state=str(
                payload.get("strategy_trajectory_state", "insufficient")
            ),
            recommended_next_action=str(
                payload.get("strategy_recommended_next_action", "monitor")
            ),
            confidence=float(payload.get("average_run_confidence", 0.0)),
            average_run_outcome_score=self._maybe_float(
                payload.get("average_run_outcome_score")
            ),
            matched_run_count=int(payload.get("matched_run_count", 0)),
            matched_session_count=int(payload.get("matched_session_count", 0)),
            progress_signal=str(payload.get("progress_signal", "insufficient")),
            progress_delta=float(payload.get("progress_delta", 0.0)),
            volatility_index=float(payload.get("strategy_volatility_index", 0.0)),
            relapse_risk=float(payload.get("strategy_relapse_risk", 0.0)),
            rationale=str(payload.get("strategy_rationale"))
            if payload.get("strategy_rationale") is not None
            else None,
            updated_at=updated_at,
        )

    def _dominant_label(self, *, labels: list[str]) -> str:
        if not labels:
            return "insufficient"
        ranking: dict[str, int] = {}
        for label in labels:
            ranking[label] = ranking.get(label, 0) + 1
        return sorted(
            ranking.items(), key=lambda item: (item[1], item[0]), reverse=True
        )[0][0]

    def _maybe_float(self, value: object) -> float | None:
        return float(value) if value is not None else None
