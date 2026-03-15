from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from dibble.models.telemetry import AuditEvent


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
    downstream_outcome_score: float | None = None

    @property
    def composite_score(self) -> float:
        if self.downstream_outcome_score is None:
            return self.quality_score
        return round((self.quality_score * 0.45) + (self.downstream_outcome_score * 0.55), 2)


@dataclass(slots=True)
class GenerationPromptOutcomeScorer:
    observation_window_minutes: int = 30

    def score(
        self,
        *,
        generation_event: AuditEvent,
        candidate_observations: list[AuditEvent],
    ) -> GenerationPromptOutcomeSample:
        prompt_template_name = str(generation_event.payload.get("prompt_template_name"))
        variant = str(generation_event.payload.get("prompt_template_variant"))
        downstream = self._match_observation(generation_event=generation_event, observations=candidate_observations)
        return GenerationPromptOutcomeSample(
            variant=variant,
            prompt_template_name=prompt_template_name,
            quality_score=float(generation_event.payload.get("quality_score", 0.0)),
            validation_passed=bool(generation_event.payload.get("validation_passed")),
            grounding_count=int(generation_event.payload.get("grounding_count", 0)),
            downstream_outcome_score=downstream,
        )

    def _match_observation(
        self,
        *,
        generation_event: AuditEvent,
        observations: list[AuditEvent],
    ) -> float | None:
        if generation_event.student_id is None:
            return None
        window = timedelta(minutes=max(1, self.observation_window_minutes))
        candidates = [
            event
            for event in observations
            if event.student_id == generation_event.student_id
            and generation_event.created_at <= event.created_at <= generation_event.created_at + window
        ]
        if not candidates:
            return None
        closest = min(candidates, key=lambda event: event.created_at)
        return round(self._score_observation(closest), 2)

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
