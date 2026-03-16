from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dibble.models.generation import GenerationRequest
from dibble.models.telemetry import AuditEvent
from dibble.services.protocols import AuditStore


@dataclass(frozen=True, slots=True)
class LearningCalibrationProfileSnapshot:
    average_run_outcome_score: float | None = None
    average_run_confidence: float = 0.0
    matched_run_count: int = 0
    matched_session_count: int = 0
    positive_run_rate: float = 0.0
    negative_run_rate: float = 0.0
    signal: str = "insufficient"


@dataclass(slots=True)
class LearningCalibrationProfileBuilder:
    recency_window_days: int = 14
    max_matched_runs: int = 12
    minimum_confidence_for_stable_signal: float = 0.55
    minimum_session_count_for_stable_signal: int = 2

    def build_from_summary_event(
        self,
        *,
        summary_event: AuditEvent,
        summary_events: list[AuditEvent],
    ) -> LearningCalibrationProfileSnapshot | None:
        matched_events = self._matched_summary_events(summary_event=summary_event, summary_events=summary_events)
        if not matched_events:
            return None
        average_run_outcome_score = round(
            sum(float(event.payload.get("run_summary_score", 0.0)) for event in matched_events) / len(matched_events),
            2,
        )
        average_run_confidence = round(
            sum(float(event.payload.get("run_calibration_confidence", 0.0)) for event in matched_events)
            / len(matched_events),
            2,
        )
        positive_run_rate = round(
            sum(1 for event in matched_events if event.payload.get("run_calibration_signal") == "positive")
            / len(matched_events),
            2,
        )
        negative_run_rate = round(
            sum(1 for event in matched_events if event.payload.get("run_calibration_signal") == "negative")
            / len(matched_events),
            2,
        )
        session_ids = {
            str(event.payload.get("learning_session_id"))
            for event in matched_events
            if event.payload.get("learning_session_id")
        }
        matched_session_count = len(session_ids) if session_ids else min(1, len(matched_events))
        return LearningCalibrationProfileSnapshot(
            average_run_outcome_score=average_run_outcome_score,
            average_run_confidence=average_run_confidence,
            matched_run_count=len(matched_events),
            matched_session_count=matched_session_count,
            positive_run_rate=positive_run_rate,
            negative_run_rate=negative_run_rate,
            signal=self._signal_label(
                average_run_outcome_score=average_run_outcome_score,
                average_run_confidence=average_run_confidence,
                matched_session_count=matched_session_count,
                positive_run_rate=positive_run_rate,
                negative_run_rate=negative_run_rate,
            ),
        )

    def _matched_summary_events(
        self,
        *,
        summary_event: AuditEvent,
        summary_events: list[AuditEvent],
    ) -> list[AuditEvent]:
        recent_cutoff = summary_event.created_at - timedelta(days=max(1, self.recency_window_days))
        scored_matches: list[tuple[int, float, AuditEvent]] = []
        for event in summary_events:
            if event.event_type != "learning.run.summary" or event.student_id != summary_event.student_id:
                continue
            if event.created_at < recent_cutoff or event.created_at > summary_event.created_at:
                continue
            match_tier = self._summary_match_tier(anchor=summary_event.payload, candidate=event.payload)
            match_score = self._summary_match_score(anchor=summary_event.payload, candidate=event.payload)
            if match_tier <= 0 or match_score <= 0.0:
                continue
            scored_matches.append((match_tier, match_score, event))
        if not scored_matches:
            return []
        strongest_tier = max(tier for tier, _, _ in scored_matches)
        latest_by_generation: dict[str, tuple[float, AuditEvent]] = {}
        for tier, match_score, event in scored_matches:
            if tier != strongest_tier:
                continue
            generation_id = str(event.payload.get("generation_id") or event.payload.get("source_generation_event_id"))
            current = latest_by_generation.get(generation_id)
            if current is None or (match_score, event.created_at) > (current[0], current[1].created_at):
                latest_by_generation[generation_id] = (match_score, event)
        matched = list(latest_by_generation.values())
        matched.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return [event for _, event in matched[: self.max_matched_runs]]

    def _summary_match_score(self, *, anchor: dict[str, object], candidate: dict[str, object]) -> float:
        score = 0.0
        score += self._overlap_score(anchor.get("target_kc_ids"), candidate.get("target_kc_ids")) * 3.0
        score += self._overlap_score(anchor.get("target_lo_ids"), candidate.get("target_lo_ids")) * 2.0
        if anchor.get("intent") and candidate.get("intent") == anchor.get("intent"):
            score += 1.0
        if anchor.get("content_type") and candidate.get("content_type") == anchor.get("content_type"):
            score += 0.75
        if not anchor.get("target_kc_ids") and not anchor.get("target_lo_ids") and anchor.get("intent"):
            if candidate.get("intent") == anchor.get("intent"):
                score += 0.25
        return score

    def _summary_match_tier(self, *, anchor: dict[str, object], candidate: dict[str, object]) -> int:
        if self._overlap_score(anchor.get("target_kc_ids"), candidate.get("target_kc_ids")) > 0.0:
            return 3
        if self._overlap_score(anchor.get("target_lo_ids"), candidate.get("target_lo_ids")) > 0.0:
            return 3
        if anchor.get("content_type") and candidate.get("content_type") == anchor.get("content_type"):
            return 2
        if anchor.get("intent") and candidate.get("intent") == anchor.get("intent"):
            return 1
        return 0

    def _signal_label(
        self,
        *,
        average_run_outcome_score: float | None,
        average_run_confidence: float,
        matched_session_count: int,
        positive_run_rate: float,
        negative_run_rate: float,
    ) -> str:
        if average_run_outcome_score is None:
            return "insufficient"
        if matched_session_count < self.minimum_session_count_for_stable_signal:
            return "tentative"
        if average_run_confidence < self.minimum_confidence_for_stable_signal:
            return "tentative"
        if positive_run_rate >= 0.6 and average_run_outcome_score >= 0.7:
            return "positive"
        if negative_run_rate >= 0.5 and average_run_outcome_score <= 0.5:
            return "negative"
        return "mixed"

    def _overlap_score(self, left: object, right: object) -> float:
        left_values = {str(item) for item in left} if isinstance(left, list) else set()
        right_values = {str(item) for item in right} if isinstance(right, list) else set()
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(len(left_values), len(right_values))


@dataclass(slots=True)
class LearningCalibrationProfileRecorder:
    audit_store: AuditStore
    profile_builder: LearningCalibrationProfileBuilder = field(default_factory=LearningCalibrationProfileBuilder)
    max_events: int = 1000

    def record_from_summary_events(self, *, summary_events: list[AuditEvent]) -> list[AuditEvent]:
        if not summary_events:
            return []
        events = self.audit_store.list(limit=self.max_events)
        all_summary_events = [event for event in events if event.event_type == "learning.run.summary"]
        recorded: list[AuditEvent] = []
        for summary_event in summary_events:
            if summary_event.student_id is None or summary_event.event_type != "learning.run.summary":
                continue
            snapshot = self.profile_builder.build_from_summary_event(
                summary_event=summary_event,
                summary_events=all_summary_events,
            )
            if snapshot is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.calibration.profile",
                    status="success",
                    student_id=str(summary_event.student_id),
                    payload={
                        "source_run_summary_event_id": summary_event.event_id,
                        "generation_id": summary_event.payload.get("generation_id"),
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
                        "profile_signal": snapshot.signal,
                    },
                )
            )
        return recorded


@dataclass(slots=True)
class LearningCalibrationProfileResolver:
    recency_window_days: int = 14
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
            if event.event_type != "learning.calibration.profile":
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
        if payload.get("intent") == request.intent.value:
            score += 1.0
        if request.requested_content_type and payload.get("content_type") == request.requested_content_type.value:
            score += 0.75
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
