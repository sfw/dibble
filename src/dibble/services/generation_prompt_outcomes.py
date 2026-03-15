from __future__ import annotations

from dataclasses import dataclass

from dibble.models.telemetry import AuditEvent
from dibble.services.generation_trace_linker import GenerationTraceLinker, LinkedTraceEvent


def _signal_score(value: object, *, positive: bool) -> float:
    mapping = {
        "none": 0.0,
        "low": 0.33,
        "medium": 0.66,
        "high": 1.0,
    }
    score = mapping.get(str(value), 0.5)
    return score if positive else (1.0 - score)


@dataclass(frozen=True, slots=True)
class GenerationPromptOutcomeSample:
    variant: str
    prompt_template_name: str
    quality_score: float
    validation_passed: bool
    grounding_count: int
    downstream_observation_score: float | None = None
    downstream_assessment_score: float | None = None
    observation_match_count: int = 0
    assessment_match_count: int = 0

    @property
    def composite_score(self) -> float:
        downstream_scores = [
            score
            for score in (self.downstream_observation_score, self.downstream_assessment_score)
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
            event_scorer=self._score_observation,
        )
        assessment_score = self._aggregate_trace_score(
            linked_events=linked_assessments,
            event_scorer=self._score_assessment,
        )
        return GenerationPromptOutcomeSample(
            variant=variant,
            prompt_template_name=prompt_template_name,
            quality_score=float(generation_event.payload.get("quality_score", 0.0)),
            validation_passed=bool(generation_event.payload.get("validation_passed")),
            grounding_count=int(generation_event.payload.get("grounding_count", 0)),
            downstream_observation_score=observation_score,
            downstream_assessment_score=assessment_score,
            observation_match_count=len(linked_observations),
            assessment_match_count=len(linked_assessments),
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

    def _score_observation(self, observation_event: AuditEvent) -> float:
        payload = observation_event.payload
        engagement_score = _signal_score(payload.get("engagement"), positive=True)
        frustration_score = _signal_score(payload.get("frustration"), positive=False)
        load_score = 1.0 - min(max(float(payload.get("total_load", 0.5)), 0.0), 1.0)
        confidence_score = min(max(float(payload.get("confidence_calibration", 0.5)), 0.0), 1.0)
        help_seeking_score = _signal_score(payload.get("help_seeking"), positive=False)
        return (
            (engagement_score * 0.22)
            + (frustration_score * 0.22)
            + (load_score * 0.18)
            + (confidence_score * 0.22)
            + (help_seeking_score * 0.16)
        )

    def _score_assessment(self, assessment_event: AuditEvent) -> float:
        payload = assessment_event.payload
        evidence_score = min(max(float(payload.get("evidence_score", 0.0)), 0.0), 1.0)
        profile_update_score = 1.0 if bool(payload.get("profile_update_applied")) else 0.0
        strength_score = {
            "insufficient": 0.2,
            "emerging": 0.6,
            "demonstrated": 1.0,
        }.get(str(payload.get("evidence_strength")), 0.5)
        return (evidence_score * 0.55) + (strength_score * 0.3) + (profile_update_score * 0.15)
