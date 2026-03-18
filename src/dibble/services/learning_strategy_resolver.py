from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dibble.models.generation import GenerationRequest
from dibble.models.telemetry import AuditEvent


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
        recent_cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(1, self.recency_window_days)
        )
        scored_matches: list[tuple[int, float, AuditEvent]] = []
        for event in profile_events:
            if event.event_type != "learning.strategy.profile":
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
