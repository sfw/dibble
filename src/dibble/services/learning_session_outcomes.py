from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from dibble.models.telemetry import AuditEvent
from dibble.services.generation_outcome_metrics import (
    score_assessment_event,
    score_observation_event,
)


@dataclass(frozen=True, slots=True)
class LearningSessionOutcome:
    session_outcome_score: float | None = None
    subsequent_generation_count: int = 0
    outcome_event_count: int = 0
    outcome_event_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class LearningSessionOutcomeScorer:
    session_window_minutes: int = 90
    max_events_per_type: int = 4

    def score(
        self,
        *,
        generation_event: AuditEvent,
        candidate_generations: list[AuditEvent],
        candidate_observations: list[AuditEvent],
        candidate_assessments: list[AuditEvent],
    ) -> LearningSessionOutcome:
        learning_session_id = generation_event.payload.get("learning_session_id")
        if generation_event.student_id is None or learning_session_id is None:
            return LearningSessionOutcome()

        window = timedelta(minutes=max(1, self.session_window_minutes))
        subsequent_generations = sorted(
            [
                event
                for event in candidate_generations
                if event.event_id != generation_event.event_id
                and event.student_id == generation_event.student_id
                and event.payload.get("learning_session_id") == learning_session_id
                and generation_event.created_at
                < event.created_at
                <= generation_event.created_at + window
            ],
            key=lambda event: event.created_at,
        )
        if not subsequent_generations:
            return LearningSessionOutcome()

        trace_start = subsequent_generations[0].created_at
        trace_end = generation_event.created_at + window
        observations = self._later_session_events(
            events=candidate_observations,
            generation_event=generation_event,
            learning_session_id=str(learning_session_id),
            trace_start=trace_start,
            trace_end=trace_end,
        )
        assessments = self._later_session_events(
            events=candidate_assessments,
            generation_event=generation_event,
            learning_session_id=str(learning_session_id),
            trace_start=trace_start,
            trace_end=trace_end,
        )
        downstream_scores = []
        if observations:
            downstream_scores.append(
                sum(score_observation_event(event) for event in observations)
                / len(observations)
            )
        if assessments:
            downstream_scores.append(
                sum(score_assessment_event(event) for event in assessments)
                / len(assessments)
            )
        if not downstream_scores:
            return LearningSessionOutcome(
                subsequent_generation_count=len(subsequent_generations)
            )
        outcome_event_ids = tuple(
            dict.fromkeys([event.event_id for event in observations + assessments])
        )
        return LearningSessionOutcome(
            session_outcome_score=round(
                sum(downstream_scores) / len(downstream_scores), 2
            ),
            subsequent_generation_count=len(subsequent_generations),
            outcome_event_count=len(observations) + len(assessments),
            outcome_event_ids=outcome_event_ids,
        )

    def _later_session_events(
        self,
        *,
        events: list[AuditEvent],
        generation_event: AuditEvent,
        learning_session_id: str,
        trace_start,
        trace_end,
    ) -> list[AuditEvent]:
        matched = [
            event
            for event in events
            if event.student_id == generation_event.student_id
            and event.payload.get("learning_session_id") == learning_session_id
            and trace_start <= event.created_at <= trace_end
        ]
        matched.sort(key=lambda event: event.created_at)
        return matched[: self.max_events_per_type]
