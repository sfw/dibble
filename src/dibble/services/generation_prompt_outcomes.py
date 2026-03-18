from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.telemetry import AuditEvent
from dibble.services.generation_outcome_metrics import (
    score_assessment_event,
    score_observation_event,
)
from dibble.services.generation_run_summaries import GenerationRunSummaryBuilder
from dibble.services.generation_trace_linker import (
    GenerationTraceLinker,
    LinkedTraceEvent,
)
from dibble.services.learning_session_outcomes import LearningSessionOutcomeScorer
from dibble.services.persisted_run_summaries import PersistedRunSummaryResolver


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
    run_summary_score: float | None = None
    run_calibration_signal: str = "insufficient"
    run_calibration_confidence: float = 0.0
    run_direct_source_count: int = 0
    run_event_count: int = 0
    run_summary_source: str = "insufficient"
    run_summary_event_id: str | None = None

    @property
    def composite_score(self) -> float:
        downstream_score = self.run_summary_score
        if downstream_score is None:
            downstream_scores = [
                score
                for score in (
                    self.downstream_observation_score,
                    self.downstream_assessment_score,
                    self.session_outcome_score,
                )
                if score is not None
            ]
            downstream_score = (
                round(sum(downstream_scores) / len(downstream_scores), 2)
                if downstream_scores
                else None
            )
        if downstream_score is None:
            return self.quality_score
        return round((self.quality_score * 0.4) + (downstream_score * 0.6), 2)


@dataclass(slots=True)
class GenerationPromptOutcomeScorer:
    observation_window_minutes: int = 30
    max_trace_events: int = 3
    run_summary_builder: GenerationRunSummaryBuilder = field(
        default_factory=GenerationRunSummaryBuilder
    )
    persisted_run_summary_resolver: PersistedRunSummaryResolver = field(
        default_factory=PersistedRunSummaryResolver
    )

    def score(
        self,
        *,
        generation_event: AuditEvent,
        candidate_generations: list[AuditEvent] | None = None,
        candidate_observations: list[AuditEvent],
        candidate_assessments: list[AuditEvent] | None = None,
        candidate_run_summaries: list[AuditEvent] | None = None,
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
        run_summary = self.run_summary_builder.build(
            linked_observations=linked_observations,
            linked_assessments=linked_assessments,
            session_outcome=session_outcome,
        )
        persisted_run_summary = (
            self.persisted_run_summary_resolver.resolve_for_generation(
                generation_event=generation_event,
                summary_events=candidate_run_summaries or [],
            )
        )
        selected_run_summary = (
            persisted_run_summary.summary
            if persisted_run_summary is not None
            else run_summary
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
            run_summary_score=selected_run_summary.run_outcome_score,
            run_calibration_signal=selected_run_summary.calibration_signal,
            run_calibration_confidence=selected_run_summary.calibration_confidence,
            run_direct_source_count=selected_run_summary.direct_source_count,
            run_event_count=selected_run_summary.event_count,
            run_summary_source=(
                "persisted"
                if persisted_run_summary is not None
                else "derived"
                if run_summary.run_outcome_score is not None
                else "insufficient"
            ),
            run_summary_event_id=persisted_run_summary.event_id
            if persisted_run_summary is not None
            else None,
        )

    def _aggregate_trace_score(
        self,
        *,
        linked_events: list[LinkedTraceEvent],
        event_scorer,
    ) -> float | None:
        return self.run_summary_builder.trace_score(
            linked_events=linked_events, event_scorer=event_scorer
        )
