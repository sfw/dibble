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
        matched = max(candidates, key=lambda event: self._match_score(generation_event, event))
        if self._match_score(generation_event, matched) <= 0.0:
            return None
        return round(self._score_observation(matched), 2)

    def _match_score(self, generation_event: AuditEvent, observation_event: AuditEvent) -> float:
        generation_payload = generation_event.payload
        observation_payload = observation_event.payload
        score = 0.0

        generation_id = generation_payload.get("generation_id")
        if generation_id and observation_payload.get("generation_id") == generation_id:
            score += 5.0

        content_type = generation_payload.get("content_type")
        if content_type and observation_payload.get("observed_content_type") == content_type:
            score += 1.5

        expected_task_type = self._expected_task_type(content_type)
        if expected_task_type and observation_payload.get("task_type") == expected_task_type:
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

        time_delta_seconds = (observation_event.created_at - generation_event.created_at).total_seconds()
        score += max(0.0, 1.0 - (time_delta_seconds / max(60.0, self.observation_window_minutes * 60.0)))
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
        right_values = {str(item) for item in right} if isinstance(right, list) else set()
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(len(left_values), len(right_values))

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
