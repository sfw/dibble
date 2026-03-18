from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from dibble.models.telemetry import AuditEvent


@dataclass(frozen=True, slots=True)
class LinkedTraceEvent:
    event: AuditEvent
    match_score: float
    link_tier: int = 0


@dataclass(slots=True)
class GenerationTraceLinker:
    event_window_minutes: int = 30
    minimum_match_score: float = 2.0
    max_events_per_trace: int = 3

    def linked_observations(
        self,
        *,
        generation_event: AuditEvent,
        observations: list[AuditEvent],
    ) -> list[LinkedTraceEvent]:
        return self._linked_events(
            generation_event=generation_event,
            events=observations,
            match_scorer=self._observation_match_score,
            tier_scorer=self._observation_link_tier,
        )

    def linked_assessments(
        self,
        *,
        generation_event: AuditEvent,
        assessments: list[AuditEvent],
    ) -> list[LinkedTraceEvent]:
        return self._linked_events(
            generation_event=generation_event,
            events=assessments,
            match_scorer=self._assessment_match_score,
            tier_scorer=self._assessment_link_tier,
        )

    def _linked_events(
        self,
        *,
        generation_event: AuditEvent,
        events: list[AuditEvent],
        match_scorer,
        tier_scorer,
    ) -> list[LinkedTraceEvent]:
        if generation_event.student_id is None:
            return []
        window = timedelta(minutes=max(1, self.event_window_minutes))
        linked: list[LinkedTraceEvent] = []
        for event in events:
            if event.student_id != generation_event.student_id:
                continue
            if not (
                generation_event.created_at
                <= event.created_at
                <= generation_event.created_at + window
            ):
                continue
            match_score = float(match_scorer(generation_event, event))
            if match_score <= 0.0:
                continue
            linked.append(
                LinkedTraceEvent(
                    event=event,
                    match_score=match_score,
                    link_tier=int(tier_scorer(generation_event, event)),
                )
            )
        if not linked:
            return []
        strongest_tier = max(item.link_tier for item in linked)
        if strongest_tier > 0:
            strongest_matches = [
                item
                for item in linked
                if item.link_tier == strongest_tier
                and item.match_score >= self.minimum_match_score
            ]
            if strongest_matches:
                linked = strongest_matches
        linked.sort(
            key=lambda item: (item.match_score, item.event.created_at), reverse=True
        )
        return linked[: self.max_events_per_trace]

    def _observation_link_tier(
        self, generation_event: AuditEvent, observation_event: AuditEvent
    ) -> int:
        generation_payload = generation_event.payload
        observation_payload = observation_event.payload

        generation_id = generation_payload.get("generation_id")
        if generation_id and observation_payload.get("generation_id") == generation_id:
            return 3

        learning_session_id = generation_payload.get("learning_session_id")
        if (
            learning_session_id
            and observation_payload.get("learning_session_id") == learning_session_id
        ):
            return 2

        content_type = generation_payload.get("content_type")
        expected_task_type = self._expected_task_type(content_type)
        if (
            (
                content_type
                and observation_payload.get("observed_content_type") == content_type
            )
            or (
                expected_task_type
                and observation_payload.get("task_type") == expected_task_type
            )
            or self._overlap_score(
                generation_payload.get("target_kc_ids"),
                observation_payload.get("target_kc_ids"),
            )
            > 0.0
            or self._overlap_score(
                generation_payload.get("target_lo_ids"),
                observation_payload.get("target_lo_ids"),
            )
            > 0.0
        ):
            return 1
        return 0

    def _assessment_link_tier(
        self, generation_event: AuditEvent, assessment_event: AuditEvent
    ) -> int:
        generation_payload = generation_event.payload
        assessment_payload = assessment_event.payload

        generation_id = generation_payload.get("generation_id")
        if generation_id and assessment_payload.get("generation_id") == generation_id:
            return 3

        learning_session_id = generation_payload.get("learning_session_id")
        if (
            learning_session_id
            and assessment_payload.get("learning_session_id") == learning_session_id
        ):
            return 2

        if (
            self._overlap_score(
                generation_payload.get("target_kc_ids"),
                assessment_payload.get("target_kc_ids"),
            )
            > 0.0
            or self._overlap_score(
                generation_payload.get("target_lo_ids"),
                assessment_payload.get("target_lo_ids"),
            )
            > 0.0
        ):
            return 1
        return 0

    def _observation_match_score(
        self, generation_event: AuditEvent, observation_event: AuditEvent
    ) -> float:
        generation_payload = generation_event.payload
        observation_payload = observation_event.payload
        score = 0.0

        generation_id = generation_payload.get("generation_id")
        if generation_id and observation_payload.get("generation_id") == generation_id:
            score += 5.0

        learning_session_id = generation_payload.get("learning_session_id")
        if (
            learning_session_id
            and observation_payload.get("learning_session_id") == learning_session_id
        ):
            score += 3.0

        content_type = generation_payload.get("content_type")
        if (
            content_type
            and observation_payload.get("observed_content_type") == content_type
        ):
            score += 1.5

        expected_task_type = self._expected_task_type(content_type)
        if (
            expected_task_type
            and observation_payload.get("task_type") == expected_task_type
        ):
            score += 1.0

        kc_overlap = self._overlap_score(
            generation_payload.get("target_kc_ids"),
            observation_payload.get("target_kc_ids"),
        )
        lo_overlap = self._overlap_score(
            generation_payload.get("target_lo_ids"),
            observation_payload.get("target_lo_ids"),
        )
        score += kc_overlap * 1.2
        score += lo_overlap * 0.8

        time_delta_seconds = (
            observation_event.created_at - generation_event.created_at
        ).total_seconds()
        score += max(
            0.0,
            1.0 - (time_delta_seconds / max(60.0, self.event_window_minutes * 60.0)),
        )
        return score

    def _assessment_match_score(
        self, generation_event: AuditEvent, assessment_event: AuditEvent
    ) -> float:
        generation_payload = generation_event.payload
        assessment_payload = assessment_event.payload
        score = 0.0

        generation_id = generation_payload.get("generation_id")
        if generation_id and assessment_payload.get("generation_id") == generation_id:
            score += 4.0

        learning_session_id = generation_payload.get("learning_session_id")
        if (
            learning_session_id
            and assessment_payload.get("learning_session_id") == learning_session_id
        ):
            score += 3.0

        kc_overlap = self._overlap_score(
            generation_payload.get("target_kc_ids"),
            assessment_payload.get("target_kc_ids"),
        )
        lo_overlap = self._overlap_score(
            generation_payload.get("target_lo_ids"),
            assessment_payload.get("target_lo_ids"),
        )
        score += kc_overlap * 1.4
        score += lo_overlap * 1.0

        time_delta_seconds = (
            assessment_event.created_at - generation_event.created_at
        ).total_seconds()
        score += max(
            0.0,
            1.0 - (time_delta_seconds / max(60.0, self.event_window_minutes * 60.0)),
        )
        return score

    def _expected_task_type(self, content_type: object) -> str | None:
        mapping = {
            "micro_explanation": "explanation",
            "worked_example": "worked_example",
            "practice_problem": "practice",
            "remedial_micro_module": "remediation",
            "assessment_probe": "assessment",
        }
        return mapping.get(str(content_type)) if content_type is not None else None

    def _overlap_score(self, left: object, right: object) -> float:
        left_values = {str(item) for item in left} if isinstance(left, list) else set()
        right_values = (
            {str(item) for item in right} if isinstance(right, list) else set()
        )
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(
            len(left_values), len(right_values)
        )
