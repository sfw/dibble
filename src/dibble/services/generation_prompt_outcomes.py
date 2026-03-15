from __future__ import annotations

from dataclasses import dataclass

from dibble.models.telemetry import AuditEvent
from dibble.services.generation_outcome_metrics import score_assessment_event, score_observation_event
from dibble.services.generation_trace_linker import GenerationTraceLinker, LinkedTraceEvent
from dibble.services.learning_session_outcomes import LearningSessionOutcomeScorer


@dataclass(frozen=True, slots=True)
class GenerationPromptOutcomeSample:
    variant: str
    prompt_template_name: str
    quality_score: float
    validation_passed: bool
    grounding_count: int
    downstream_observation_score: float | None = None
    downstream_assessment_score: float | None = None
    session_outcome_score: float | None = None
    observation_match_count: int = 0
    assessment_match_count: int = 0
    session_generation_depth: int = 0
    session_outcome_event_count: int = 0

    @property
    def composite_score(self) -> float:
        downstream_scores = [
            score
            for score in (
                self.downstream_observation_score,
                self.downstream_assessment_score,
                self.session_outcome_score,
            )
            if score is not None
        ]
        if not downstream_scores:
            return self.quality_score
        downstream_average = sum(downstream_scores) / len(downstream_scores)
        return round((self.quality_score * 0.4) + (downstream_average * 0.6), 2)


@dataclass(slots=True)
class GenerationPromptOutcomeScorer:
    observation_window_minutes: int = 30
    max_trace_events: int = 3

    def score(
        self,
        *,
        generation_event: AuditEvent,
        candidate_generations: list[AuditEvent] | None = None,
        candidate_observations: list[AuditEvent],
        candidate_assessments: list[AuditEvent] | None = None,
    ) -> GenerationPromptOutcomeSample:
        prompt_template_name = str(generation_event.payload.get("prompt_template_name"))
        variant = str(generation_event.payload.get("prompt_template_variant"))
        linker = GenerationTraceLinker(
            event_window_minutes=self.observation_window_minutes,
            max_events_per_trace=self.max_trace_events,
        )
        linked_observations = linker.linked_observations(
            generation_event=generation_event,
            observations=candidate_observations,
        )
        linked_assessments = linker.linked_assessments(
            generation_event=generation_event,
            assessments=candidate_assessments or [],
        )
        observation_score = self._aggregate_trace_score(
            linked_events=linked_observations,
            event_scorer=score_observation_event,
        )
        assessment_score = self._aggregate_trace_score(
            linked_events=linked_assessments,
            event_scorer=score_assessment_event,
        )
        session_outcome = LearningSessionOutcomeScorer(
            session_window_minutes=max(60, self.observation_window_minutes * 3),
            max_events_per_type=self.max_trace_events,
        ).score(
            generation_event=generation_event,
            candidate_generations=candidate_generations or [],
            candidate_observations=candidate_observations,
            candidate_assessments=candidate_assessments or [],
        )
        return GenerationPromptOutcomeSample(
            variant=variant,
            prompt_template_name=prompt_template_name,
            quality_score=float(generation_event.payload.get("quality_score", 0.0)),
            validation_passed=bool(generation_event.payload.get("validation_passed")),
            grounding_count=int(generation_event.payload.get("grounding_count", 0)),
            downstream_observation_score=observation_score,
            downstream_assessment_score=assessment_score,
            session_outcome_score=session_outcome.session_outcome_score,
            observation_match_count=len(linked_observations),
            assessment_match_count=len(linked_assessments),
            session_generation_depth=session_outcome.subsequent_generation_count,
            session_outcome_event_count=session_outcome.outcome_event_count,
        )

    def _aggregate_trace_score(
        self,
        *,
        linked_events: list[LinkedTraceEvent],
        event_scorer,
    ) -> float | None:
        if not linked_events:
            return None
        weighted_total = 0.0
        total_weight = 0.0
        for linked_event in linked_events:
            weighted_total += event_scorer(linked_event.event) * linked_event.match_score
            total_weight += linked_event.match_score
        if total_weight <= 0.0:
            return None
        return round(weighted_total / total_weight, 2)
