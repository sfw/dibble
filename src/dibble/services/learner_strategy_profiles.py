from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerStrategySummary
from dibble.models.telemetry import AuditEvent
from dibble.services.learning_progress_profiles import LearningProgressProfileResolver
from dibble.services.protocols import AuditStore


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
    if progress_signal == "improving" and positive_run_rate >= 0.5 and average_run_outcome_score >= 0.7:
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
    if support_bias < 0 and (progress_signal == "declining" or negative_run_rate >= 0.5):
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
    if progress_signal == "improving" and average_run_outcome_score >= 0.78 and support_bias >= 0:
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


def _build_snapshot(
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
            progress_event.payload.get("matched_run_count") if progress_event is not None else 1,
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
            else (1.0 if summary_event.payload.get("run_calibration_signal") == "positive" else 0.0),
            default=0.0,
        )
        negative_run_rate = self._float_value(
            progress_event.payload.get("negative_run_rate")
            if progress_event is not None
            else (1.0 if summary_event.payload.get("run_calibration_signal") == "negative" else 0.0),
            default=0.0,
        )
        progress_signal = (
            str(progress_event.payload.get("progress_signal", "tentative"))
            if progress_event is not None
            else "tentative"
        )
        progress_delta = self._float_value(
            progress_event.payload.get("progress_delta") if progress_event is not None else 0.0,
            default=0.0,
        )
        return _build_snapshot(
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


@dataclass(slots=True)
class LearningStrategyProfileRecorder:
    audit_store: AuditStore
    profile_builder: LearningStrategyProfileBuilder = field(default_factory=LearningStrategyProfileBuilder)
    max_events: int = 1000

    def record_from_summary_events(self, *, summary_events: list[AuditEvent]) -> list[AuditEvent]:
        if not summary_events:
            return []
        events = self.audit_store.list(limit=self.max_events)
        progress_events = [event for event in events if event.event_type == "learning.progress.profile"]
        recorded: list[AuditEvent] = []
        for summary_event in summary_events:
            if summary_event.student_id is None or summary_event.event_type != "learning.run.summary":
                continue
            progress_event = self._matching_progress_event(summary_event=summary_event, progress_events=progress_events)
            snapshot = self.profile_builder.build_from_summary_event(
                summary_event=summary_event,
                progress_event=progress_event,
            )
            if snapshot is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.strategy.profile",
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
                        "positive_run_rate": snapshot.positive_run_rate,
                        "negative_run_rate": snapshot.negative_run_rate,
                        "progress_signal": snapshot.progress_signal,
                        "progress_delta": snapshot.progress_delta,
                        "strategy_signal": snapshot.signal,
                        "strategy_support_bias": snapshot.support_bias,
                        "strategy_recovery_focus": snapshot.recovery_focus,
                        "strategy_trajectory_state": snapshot.trajectory_state,
                        "strategy_recommended_next_action": snapshot.recommended_next_action,
                        "strategy_volatility_index": snapshot.volatility_index,
                        "strategy_relapse_risk": snapshot.relapse_risk,
                        "strategy_rationale": snapshot.rationale,
                    },
                )
            )
        return recorded

    def _matching_progress_event(
        self,
        *,
        summary_event: AuditEvent,
        progress_events: list[AuditEvent],
    ) -> AuditEvent | None:
        matched = [
            event
            for event in progress_events
            if event.student_id == summary_event.student_id
            and event.payload.get("source_run_summary_event_id") == summary_event.event_id
        ]
        if not matched:
            return None
        matched.sort(key=lambda event: event.created_at, reverse=True)
        return matched[0]


@dataclass(slots=True)
class LearningStrategyProfileResolver:
    recency_window_days: int = 30
    max_matched_profiles: int = 2
    minimum_session_count: int = 2

    def matched_profile_events(
        self,
        *,
        profile_events: list[AuditEvent],
        request: GenerationRequest,
    ) -> list[AuditEvent]:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, self.recency_window_days))
        scored_matches: list[tuple[int, float, AuditEvent]] = []
        for event in profile_events:
            if event.event_type != "learning.strategy.profile":
                continue
            if event.created_at < recent_cutoff:
                continue
            if int(event.payload.get("matched_session_count", 0)) < self.minimum_session_count:
                continue
            match_tier = self._request_match_tier(request=request, payload=event.payload)
            match_score = self._request_match_score(request=request, payload=event.payload)
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
                tuple(str(item) for item in event.payload.get("target_kc_ids", []) if item is not None),
                tuple(str(item) for item in event.payload.get("target_lo_ids", []) if item is not None),
            )
            current = latest_by_context.get(context_key)
            if current is None or (match_score, event.created_at) > (current[0], current[1].created_at):
                latest_by_context[context_key] = (match_score, event)
        matched = list(latest_by_context.values())
        matched.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return [event for _, event in matched[: self.max_matched_profiles]]

    def _request_match_score(self, *, request: GenerationRequest, payload: dict[str, object]) -> float:
        score = 0.0
        score += self._overlap_score(request.target_kc_ids, payload.get("target_kc_ids")) * 3.0
        score += self._overlap_score(request.target_lo_ids, payload.get("target_lo_ids")) * 2.0
        if request.requested_content_type and payload.get("content_type") == request.requested_content_type.value:
            score += 0.75
        if payload.get("intent") == request.intent.value:
            score += 1.0
        if not request.target_kc_ids and not request.target_lo_ids and payload.get("intent") == request.intent.value:
            score += 0.25
        return score

    def _request_match_tier(self, *, request: GenerationRequest, payload: dict[str, object]) -> int:
        if self._overlap_score(request.target_kc_ids, payload.get("target_kc_ids")) > 0.0:
            return 3
        if self._overlap_score(request.target_lo_ids, payload.get("target_lo_ids")) > 0.0:
            return 3
        if request.requested_content_type and payload.get("content_type") == request.requested_content_type.value:
            return 2
        if payload.get("intent") == request.intent.value:
            return 1
        return 0

    def _overlap_score(self, left: list[str], right: object) -> float:
        left_values = {str(item) for item in left}
        right_values = {str(item) for item in right} if isinstance(right, list) else set()
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(len(left_values), len(right_values))


@dataclass(slots=True)
class LearnerStrategySignalService:
    audit_store: AuditStore
    profile_resolver: LearningStrategyProfileResolver = field(default_factory=LearningStrategyProfileResolver)
    progress_profile_resolver: LearningProgressProfileResolver = field(default_factory=LearningProgressProfileResolver)
    max_events: int = 500

    def strategy_for(self, *, student_id: UUID, request: GenerationRequest) -> LearnerStrategySummary:
        events = self.audit_store.list(limit=self.max_events)
        strategy_events = [
            event for event in events if event.event_type == "learning.strategy.profile" and event.student_id == student_id
        ]
        matched_strategy_profiles = self.profile_resolver.matched_profile_events(
            profile_events=strategy_events,
            request=request,
        )
        if matched_strategy_profiles:
            return self._aggregate_strategy_events(matched_strategy_profiles)

        progress_events = [
            event for event in events if event.event_type == "learning.progress.profile" and event.student_id == student_id
        ]
        matched_progress_profiles = self.progress_profile_resolver.matched_profile_events(
            profile_events=progress_events,
            request=request,
        )
        if matched_progress_profiles:
            return self._aggregate_progress_events(matched_progress_profiles)

        return LearnerStrategySummary()

    def latest_for_student(self, *, student_id: UUID) -> LearnerStrategySummary:
        events = self.audit_store.list(limit=self.max_events)
        strategy_event = next(
            (event for event in events if event.event_type == "learning.strategy.profile" and event.student_id == student_id),
            None,
        )
        if strategy_event is not None:
            return self._summary_from_payload(
                payload=strategy_event.payload,
                source="strategy_profile",
                updated_at=strategy_event.created_at,
            )

        progress_event = next(
            (event for event in events if event.event_type == "learning.progress.profile" and event.student_id == student_id),
            None,
        )
        if progress_event is None:
            return LearnerStrategySummary()
        snapshot = _build_snapshot(
            average_run_outcome_score=self._maybe_float(progress_event.payload.get("average_run_outcome_score")),
            average_run_confidence=float(progress_event.payload.get("average_run_confidence", 0.0)),
            matched_run_count=int(progress_event.payload.get("matched_run_count", 0)),
            matched_session_count=int(progress_event.payload.get("matched_session_count", 0)),
            positive_run_rate=float(progress_event.payload.get("positive_run_rate", 0.0)),
            negative_run_rate=float(progress_event.payload.get("negative_run_rate", 0.0)),
            progress_signal=str(progress_event.payload.get("progress_signal", "insufficient")),
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

    def _aggregate_strategy_events(self, profile_events: list[AuditEvent]) -> LearnerStrategySummary:
        total_run_count = sum(max(1, int(event.payload.get("matched_run_count", 0))) for event in profile_events)
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
            labels=[str(event.payload.get("progress_signal", "insufficient")) for event in profile_events]
        )
        strategy_signal = self._dominant_label(
            labels=[str(event.payload.get("strategy_signal", "insufficient")) for event in profile_events]
        )
        recovery_focus = self._dominant_label(
            labels=[str(event.payload.get("strategy_recovery_focus", "monitor")) for event in profile_events]
        )
        trajectory_state = self._dominant_label(
            labels=[str(event.payload.get("strategy_trajectory_state", "insufficient")) for event in profile_events]
        )
        recommended_next_action = self._dominant_label(
            labels=[str(event.payload.get("strategy_recommended_next_action", "monitor")) for event in profile_events]
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
        matched_session_count = max(int(event.payload.get("matched_session_count", 0)) for event in profile_events)
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

    def _aggregate_progress_events(self, profile_events: list[AuditEvent]) -> LearnerStrategySummary:
        total_run_count = sum(max(1, int(event.payload.get("matched_run_count", 0))) for event in profile_events)
        if total_run_count <= 0:
            return LearnerStrategySummary()
        snapshot = _build_snapshot(
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
            matched_session_count=max(int(event.payload.get("matched_session_count", 0)) for event in profile_events),
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
                labels=[str(event.payload.get("progress_signal", "insufficient")) for event in profile_events]
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
            trajectory_state=str(payload.get("strategy_trajectory_state", "insufficient")),
            recommended_next_action=str(payload.get("strategy_recommended_next_action", "monitor")),
            confidence=float(payload.get("average_run_confidence", 0.0)),
            average_run_outcome_score=self._maybe_float(payload.get("average_run_outcome_score")),
            matched_run_count=int(payload.get("matched_run_count", 0)),
            matched_session_count=int(payload.get("matched_session_count", 0)),
            progress_signal=str(payload.get("progress_signal", "insufficient")),
            progress_delta=float(payload.get("progress_delta", 0.0)),
            volatility_index=float(payload.get("strategy_volatility_index", 0.0)),
            relapse_risk=float(payload.get("strategy_relapse_risk", 0.0)),
            rationale=str(payload.get("strategy_rationale")) if payload.get("strategy_rationale") is not None else None,
            updated_at=updated_at,
        )

    def _dominant_label(self, *, labels: list[str]) -> str:
        if not labels:
            return "insufficient"
        ranking: dict[str, int] = {}
        for label in labels:
            ranking[label] = ranking.get(label, 0) + 1
        return sorted(ranking.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]

    def _maybe_float(self, value: object) -> float | None:
        return float(value) if value is not None else None
