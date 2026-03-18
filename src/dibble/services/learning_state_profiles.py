from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerStateProfileSummary, SignalLevel
from dibble.models.telemetry import AuditEvent
from dibble.services.protocols import AuditStore


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


def _build_snapshot(
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
        return _build_snapshot(
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


@dataclass(slots=True)
class LearningStateProfileRecorder:
    audit_store: AuditStore
    profile_builder: LearningStateProfileBuilder = field(
        default_factory=LearningStateProfileBuilder
    )
    max_events: int = 1000

    def record_from_summary_events(
        self, *, summary_events: list[AuditEvent]
    ) -> list[AuditEvent]:
        if not summary_events:
            return []
        events = self.audit_store.list(limit=self.max_events)
        progress_events = [
            event for event in events if event.event_type == "learning.progress.profile"
        ]
        strategy_events = [
            event for event in events if event.event_type == "learning.strategy.profile"
        ]
        recorded: list[AuditEvent] = []
        for summary_event in summary_events:
            if (
                summary_event.student_id is None
                or summary_event.event_type != "learning.run.summary"
            ):
                continue
            progress_event = self._matching_event(
                summary_event=summary_event,
                profile_events=progress_events,
            )
            strategy_event = self._matching_event(
                summary_event=summary_event,
                profile_events=strategy_events,
            )
            snapshot = self.profile_builder.build_from_summary_event(
                summary_event=summary_event,
                progress_event=progress_event,
                strategy_event=strategy_event,
            )
            if snapshot is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.state.profile",
                    status="success",
                    student_id=str(summary_event.student_id),
                    payload={
                        "source_run_summary_event_id": summary_event.event_id,
                        "intent": summary_event.payload.get("intent"),
                        "content_type": summary_event.payload.get("content_type"),
                        "target_kc_ids": summary_event.payload.get("target_kc_ids", []),
                        "target_lo_ids": summary_event.payload.get("target_lo_ids", []),
                        "average_run_outcome_score": snapshot.average_run_outcome_score,
                        "average_run_confidence": snapshot.average_run_confidence,
                        "matched_run_count": snapshot.matched_run_count,
                        "matched_session_count": snapshot.matched_session_count,
                        "progress_signal": snapshot.progress_signal,
                        "progress_delta": snapshot.progress_delta,
                        "strategy_signal": snapshot.strategy_signal,
                        "strategy_trajectory_state": snapshot.strategy_trajectory_state,
                        "state_profile_signal": snapshot.signal,
                        "engagement": snapshot.engagement.value,
                        "frustration": snapshot.frustration.value,
                        "confusion": snapshot.confusion.value,
                        "confidence": snapshot.confidence,
                        "intrinsic_load": snapshot.intrinsic_load,
                        "extraneous_load": snapshot.extraneous_load,
                        "germane_load": snapshot.germane_load,
                        "total_load": snapshot.total_load,
                        "capacity_utilization": snapshot.capacity_utilization,
                        "confidence_calibration": snapshot.confidence_calibration,
                        "help_seeking": snapshot.help_seeking.value,
                        "help_seeking_effectiveness": snapshot.help_seeking_effectiveness,
                        "self_monitoring": snapshot.self_monitoring,
                        "affective_reliability": snapshot.affective_reliability,
                        "load_reliability": snapshot.load_reliability,
                        "recovery_stability": snapshot.recovery_stability,
                        "overload_risk": snapshot.overload_risk,
                        "metacognitive_reliability": snapshot.metacognitive_reliability,
                        "state_profile_rationale": snapshot.rationale,
                    },
                )
            )
        return recorded

    def _matching_event(
        self,
        *,
        summary_event: AuditEvent,
        profile_events: list[AuditEvent],
    ) -> AuditEvent | None:
        matched = [
            event
            for event in profile_events
            if event.student_id == summary_event.student_id
            and event.payload.get("source_run_summary_event_id")
            == summary_event.event_id
        ]
        if not matched:
            return None
        matched.sort(key=lambda event: event.created_at, reverse=True)
        return matched[0]


@dataclass(slots=True)
class LearningStateProfileResolver:
    recency_window_days: int = 30
    max_matched_profiles: int = 2
    minimum_session_count: int = 2

    def matched_profile_events(
        self,
        *,
        profile_events: list[AuditEvent],
        request: GenerationRequest,
    ) -> list[AuditEvent]:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(1, self.recency_window_days)
        )
        scored_matches: list[tuple[int, float, AuditEvent]] = []
        for event in profile_events:
            if event.event_type != "learning.state.profile":
                continue
            if event.created_at < recent_cutoff:
                continue
            if (
                int(event.payload.get("matched_session_count", 0))
                < self.minimum_session_count
            ):
                continue
            match_tier = self._request_match_tier(
                request=request, payload=event.payload
            )
            match_score = self._request_match_score(
                request=request, payload=event.payload
            )
            if match_tier <= 0 or match_score <= 0.0:
                continue
            scored_matches.append((match_tier, match_score, event))
        if not scored_matches:
            return []
        strongest_tier = max(tier for tier, _, _ in scored_matches)
        latest_by_context: dict[tuple[object, ...], tuple[float, AuditEvent]] = {}
        for tier, match_score, event in scored_matches:
            if tier != strongest_tier:
                continue
            context_key = (
                event.payload.get("intent"),
                event.payload.get("content_type"),
                tuple(
                    str(item)
                    for item in event.payload.get("target_kc_ids", [])
                    if item is not None
                ),
                tuple(
                    str(item)
                    for item in event.payload.get("target_lo_ids", [])
                    if item is not None
                ),
            )
            current = latest_by_context.get(context_key)
            if current is None or (match_score, event.created_at) > (
                current[0],
                current[1].created_at,
            ):
                latest_by_context[context_key] = (match_score, event)
        matched = list(latest_by_context.values())
        matched.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return [event for _, event in matched[: self.max_matched_profiles]]

    def _request_match_score(
        self, *, request: GenerationRequest, payload: dict[str, object]
    ) -> float:
        score = 0.0
        score += (
            self._overlap_score(request.target_kc_ids, payload.get("target_kc_ids"))
            * 3.0
        )
        score += (
            self._overlap_score(request.target_lo_ids, payload.get("target_lo_ids"))
            * 2.0
        )
        if (
            request.requested_content_type
            and payload.get("content_type") == request.requested_content_type.value
        ):
            score += 0.75
        if payload.get("intent") == request.intent.value:
            score += 1.0
        if (
            not request.target_kc_ids
            and not request.target_lo_ids
            and payload.get("intent") == request.intent.value
        ):
            score += 0.25
        return score

    def _request_match_tier(
        self, *, request: GenerationRequest, payload: dict[str, object]
    ) -> int:
        if (
            self._overlap_score(request.target_kc_ids, payload.get("target_kc_ids"))
            > 0.0
        ):
            return 3
        if (
            self._overlap_score(request.target_lo_ids, payload.get("target_lo_ids"))
            > 0.0
        ):
            return 3
        if (
            request.requested_content_type
            and payload.get("content_type") == request.requested_content_type.value
        ):
            return 2
        if payload.get("intent") == request.intent.value:
            return 1
        return 0

    def _overlap_score(self, left: list[str], right: object) -> float:
        left_values = {str(item) for item in left}
        right_values = (
            {str(item) for item in right} if isinstance(right, list) else set()
        )
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(
            len(left_values), len(right_values)
        )


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
