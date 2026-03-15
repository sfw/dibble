from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dibble.models.telemetry import AuditEvent
from dibble.services.generation_outcome_metrics import score_assessment_event, score_observation_event
from dibble.services.generation_trace_linker import LinkedTraceEvent
from dibble.services.learning_session_outcomes import LearningSessionOutcome


@dataclass(frozen=True, slots=True)
class GenerationRunSummary:
    run_outcome_score: float | None = None
    calibration_signal: str = "insufficient"
    calibration_confidence: float = 0.0
    direct_source_count: int = 0
    event_count: int = 0


@dataclass(slots=True)
class GenerationRunSummaryBuilder:
    def build(
        self,
        *,
        linked_observations: list[LinkedTraceEvent],
        linked_assessments: list[LinkedTraceEvent],
        session_outcome: LearningSessionOutcome,
    ) -> GenerationRunSummary:
        observation_score = self.trace_score(
            linked_events=linked_observations,
            event_scorer=score_observation_event,
        )
        assessment_score = self.trace_score(
            linked_events=linked_assessments,
            event_scorer=score_assessment_event,
        )
        weighted_sources: list[tuple[float, float]] = []
        confidence_inputs: list[float] = []
        if observation_score is not None:
            weighted_sources.append((observation_score, 0.3))
            confidence_inputs.append(self._linked_trace_confidence(linked_observations))
        if assessment_score is not None:
            weighted_sources.append((assessment_score, 0.35))
            confidence_inputs.append(self._linked_trace_confidence(linked_assessments))
        if session_outcome.session_outcome_score is not None:
            weighted_sources.append((session_outcome.session_outcome_score, 0.35))
            confidence_inputs.append(self._session_outcome_confidence(session_outcome))

        event_ids = {linked_event.event.event_id for linked_event in linked_observations}
        event_ids.update(linked_event.event.event_id for linked_event in linked_assessments)
        event_ids.update(session_outcome.outcome_event_ids)
        event_count = len(event_ids)
        direct_source_count = sum(1 for score in (observation_score, assessment_score) if score is not None)
        if not weighted_sources:
            return GenerationRunSummary(event_count=event_count)

        weighted_total = sum(score * weight for score, weight in weighted_sources)
        total_weight = sum(weight for _, weight in weighted_sources)
        run_outcome_score = round(weighted_total / total_weight, 2) if total_weight > 0.0 else None
        calibration_confidence = (
            round(sum(confidence_inputs) / len(confidence_inputs), 2) if confidence_inputs else 0.0
        )
        return GenerationRunSummary(
            run_outcome_score=run_outcome_score,
            calibration_signal=self._calibration_signal(
                run_outcome_score=run_outcome_score,
                calibration_confidence=calibration_confidence,
            ),
            calibration_confidence=calibration_confidence,
            direct_source_count=direct_source_count,
            event_count=event_count,
        )

    def trace_score(
        self,
        *,
        linked_events: list[LinkedTraceEvent],
        event_scorer: Callable[[AuditEvent], float],
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

    def _linked_trace_confidence(self, linked_events: list[LinkedTraceEvent]) -> float:
        if not linked_events:
            return 0.0
        per_event_confidences = []
        for linked_event in linked_events:
            tier_confidence = {
                0: 0.3,
                1: 0.55,
                2: 0.8,
                3: 1.0,
            }.get(linked_event.link_tier, 0.4)
            match_confidence = min(1.0, linked_event.match_score / 5.0)
            per_event_confidences.append((tier_confidence * 0.65) + (match_confidence * 0.35))
        trace_depth_bonus = min(1.0, len(linked_events) / 2.0)
        average_event_confidence = sum(per_event_confidences) / len(per_event_confidences)
        return round((average_event_confidence * 0.75) + (trace_depth_bonus * 0.25), 2)

    def _session_outcome_confidence(self, session_outcome: LearningSessionOutcome) -> float:
        if session_outcome.session_outcome_score is None:
            return 0.0
        generation_depth = min(1.0, session_outcome.subsequent_generation_count / 2.0)
        outcome_depth = min(1.0, session_outcome.outcome_event_count / 3.0)
        return round(0.45 + (generation_depth * 0.25) + (outcome_depth * 0.3), 2)

    def _calibration_signal(
        self,
        *,
        run_outcome_score: float | None,
        calibration_confidence: float,
    ) -> str:
        if run_outcome_score is None:
            return "insufficient"
        if calibration_confidence < 0.35:
            return "tentative"
        if run_outcome_score >= 0.75:
            return "positive"
        if run_outcome_score <= 0.45:
            return "negative"
        return "mixed"
