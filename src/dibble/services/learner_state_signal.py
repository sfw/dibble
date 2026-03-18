from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerStateProfileSummary, SignalLevel
from dibble.models.telemetry import AuditEvent
from dibble.services.learning_state_resolver import LearningStateProfileResolver
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class LearnerStateSignalService:
    audit_store: AuditStore
    profile_resolver: LearningStateProfileResolver = field(
        default_factory=LearningStateProfileResolver
    )
    max_events: int = 500

    def state_for(
        self, *, student_id: UUID, request: GenerationRequest
    ) -> LearnerStateProfileSummary:
        events = self.audit_store.list(limit=self.max_events)
        state_events = [
            event
            for event in events
            if event.event_type == "learning.state.profile"
            and event.student_id == student_id
        ]
        matched_profiles = self.profile_resolver.matched_profile_events(
            profile_events=state_events, request=request
        )
        if not matched_profiles:
            return LearnerStateProfileSummary()
        return self._aggregate_state_events(matched_profiles)

    def latest_for_student(self, *, student_id: UUID) -> LearnerStateProfileSummary:
        events = self.audit_store.list(limit=self.max_events)
        state_event = next(
            (
                event
                for event in events
                if event.event_type == "learning.state.profile"
                and event.student_id == student_id
            ),
            None,
        )
        if state_event is None:
            return LearnerStateProfileSummary()
        return self._summary_from_payload(
            payload=state_event.payload,
            source="state_profile",
            updated_at=state_event.created_at,
        )

    def _aggregate_state_events(
        self, profile_events: list[AuditEvent]
    ) -> LearnerStateProfileSummary:
        total_run_count = sum(
            max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        )
        if total_run_count <= 0:
            return LearnerStateProfileSummary()
        return LearnerStateProfileSummary(
            signal=self._dominant_label(
                labels=[
                    str(event.payload.get("state_profile_signal", "insufficient"))
                    for event in profile_events
                ]
            ),
            source="state_profile",
            confidence=round(
                sum(
                    float(event.payload.get("average_run_confidence", 0.0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count,
                2,
            ),
            average_run_outcome_score=round(
                sum(
                    float(event.payload.get("average_run_outcome_score", 0.0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count,
                2,
            ),
            matched_run_count=total_run_count,
            matched_session_count=round(
                sum(
                    int(event.payload.get("matched_session_count", 0))
                    * max(1, int(event.payload.get("matched_run_count", 0)))
                    for event in profile_events
                )
                / total_run_count
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
            strategy_signal=self._dominant_label(
                labels=[
                    str(event.payload.get("strategy_signal", "insufficient"))
                    for event in profile_events
                ]
            ),
            strategy_trajectory_state=self._dominant_label(
                labels=[
                    str(event.payload.get("strategy_trajectory_state", "insufficient"))
                    for event in profile_events
                ]
            ),
            engagement=self._average_signal_level(profile_events, "engagement"),
            frustration=self._average_signal_level(profile_events, "frustration"),
            total_load=round(self._weighted_average(profile_events, "total_load"), 2),
            confidence_calibration=round(
                self._weighted_average(profile_events, "confidence_calibration"), 2
            ),
            help_seeking=self._average_signal_level(profile_events, "help_seeking"),
            self_monitoring=round(
                self._weighted_average(profile_events, "self_monitoring"), 2
            ),
            affective_reliability=round(
                self._weighted_average(profile_events, "affective_reliability"), 2
            ),
            load_reliability=round(
                self._weighted_average(profile_events, "load_reliability"), 2
            ),
            recovery_stability=round(
                self._weighted_average(profile_events, "recovery_stability"), 2
            ),
            overload_risk=round(
                self._weighted_average(profile_events, "overload_risk"), 2
            ),
            metacognitive_reliability=round(
                self._weighted_average(profile_events, "metacognitive_reliability"),
                2,
            ),
            rationale=next(
                (
                    str(event.payload.get("state_profile_rationale"))
                    for event in profile_events
                    if event.payload.get("state_profile_rationale")
                ),
                None,
            ),
            updated_at=max(event.created_at for event in profile_events),
        )

    def _summary_from_payload(
        self,
        *,
        payload: dict[str, object],
        source: str,
        updated_at: datetime,
    ) -> LearnerStateProfileSummary:
        return LearnerStateProfileSummary(
            signal=str(payload.get("state_profile_signal", "insufficient")),
            source=source,
            confidence=float(payload.get("average_run_confidence", 0.0)),
            average_run_outcome_score=self._maybe_float(
                payload.get("average_run_outcome_score")
            ),
            matched_run_count=int(payload.get("matched_run_count", 0)),
            matched_session_count=int(payload.get("matched_session_count", 0)),
            progress_signal=str(payload.get("progress_signal", "insufficient")),
            progress_delta=float(payload.get("progress_delta", 0.0)),
            strategy_signal=str(payload.get("strategy_signal", "insufficient")),
            strategy_trajectory_state=str(
                payload.get("strategy_trajectory_state", "insufficient")
            ),
            engagement=self._signal_level(payload.get("engagement")),
            frustration=self._signal_level(payload.get("frustration")),
            total_load=float(payload.get("total_load", 0.4)),
            confidence_calibration=float(payload.get("confidence_calibration", 0.5)),
            help_seeking=self._signal_level(payload.get("help_seeking")),
            self_monitoring=float(payload.get("self_monitoring", 0.5)),
            affective_reliability=float(payload.get("affective_reliability", 0.0)),
            load_reliability=float(payload.get("load_reliability", 0.0)),
            recovery_stability=float(payload.get("recovery_stability", 0.0)),
            overload_risk=float(payload.get("overload_risk", 0.0)),
            metacognitive_reliability=float(
                payload.get("metacognitive_reliability", 0.0)
            ),
            rationale=str(payload.get("state_profile_rationale"))
            if payload.get("state_profile_rationale") is not None
            else None,
            updated_at=updated_at,
        )

    def _weighted_average(self, profile_events: list[AuditEvent], key: str) -> float:
        total_run_count = sum(
            max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        )
        return sum(
            float(event.payload.get(key, 0.0))
            * max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        ) / max(1, total_run_count)

    def _average_signal_level(
        self, profile_events: list[AuditEvent], key: str
    ) -> SignalLevel:
        total_run_count = sum(
            max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        )
        average = sum(
            self._signal_score(event.payload.get(key))
            * max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        ) / max(1, total_run_count)
        return self._signal_level_from_score(average)

    def _signal_level(self, value: object) -> SignalLevel:
        return {
            "none": SignalLevel.none,
            "low": SignalLevel.low,
            "medium": SignalLevel.medium,
            "high": SignalLevel.high,
        }.get(str(value), SignalLevel.low)

    def _signal_score(self, value: object) -> int:
        return {
            "none": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
        }.get(str(value), 1)

    def _signal_level_from_score(self, value: float) -> SignalLevel:
        if value >= 2.5:
            return SignalLevel.high
        if value >= 1.5:
            return SignalLevel.medium
        if value >= 0.5:
            return SignalLevel.low
        return SignalLevel.none

    def _dominant_label(self, *, labels: list[str]) -> str:
        counts: dict[str, int] = {}
        for label in labels:
            counts[label] = counts.get(label, 0) + 1
        if not counts:
            return "insufficient"
        return max(counts.items(), key=lambda item: (item[1], item[0]))[0]

    def _maybe_float(self, value: object) -> float | None:
        return float(value) if value is not None else None
