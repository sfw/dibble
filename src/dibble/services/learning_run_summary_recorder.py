from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.telemetry import AuditEvent
from dibble.services.generation_prompt_outcomes import GenerationPromptOutcomeScorer
from dibble.services.generation_trace_linker import GenerationTraceLinker
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class LearningRunSummaryRecorder:
    audit_store: AuditStore
    outcome_scorer: GenerationPromptOutcomeScorer = field(
        default_factory=GenerationPromptOutcomeScorer
    )
    linker: GenerationTraceLinker = field(default_factory=GenerationTraceLinker)
    max_events: int = 500
    max_summaries_per_trigger: int = 3

    def record_from_trigger_event(
        self, *, trigger_event: AuditEvent
    ) -> list[AuditEvent]:
        if trigger_event.student_id is None or trigger_event.event_type not in {
            "learner.observe",
            "assessment.socratic",
        }:
            return []
        events = self.audit_store.list(limit=self.max_events)
        generation_events = [
            event
            for event in events
            if event.event_type == "content.generate"
            and event.student_id == trigger_event.student_id
        ]
        observation_events = [
            event
            for event in events
            if event.event_type == "learner.observe"
            and event.student_id == trigger_event.student_id
        ]
        assessment_events = [
            event
            for event in events
            if event.event_type == "assessment.socratic"
            and event.student_id == trigger_event.student_id
        ]
        matched_generations = self._matched_generations(
            trigger_event=trigger_event,
            generation_events=generation_events,
        )
        recorded: list[AuditEvent] = []
        for generation_event in matched_generations[: self.max_summaries_per_trigger]:
            sample = self.outcome_scorer.score(
                generation_event=generation_event,
                candidate_generations=generation_events,
                candidate_observations=observation_events,
                candidate_assessments=assessment_events,
            )
            if sample.run_summary_score is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.run.summary",
                    status="success",
                    student_id=str(trigger_event.student_id),
                    payload={
                        "trigger_event_id": trigger_event.event_id,
                        "trigger_event_type": trigger_event.event_type,
                        "source_generation_event_id": generation_event.event_id,
                        "generation_id": generation_event.payload.get("generation_id"),
                        "intent": generation_event.payload.get("intent"),
                        "learning_session_id": generation_event.payload.get(
                            "learning_session_id"
                        ),
                        "content_type": generation_event.payload.get("content_type"),
                        "prompt_template_name": sample.prompt_template_name,
                        "prompt_template_variant": sample.variant,
                        "target_kc_ids": generation_event.payload.get(
                            "target_kc_ids", []
                        ),
                        "target_lo_ids": generation_event.payload.get(
                            "target_lo_ids", []
                        ),
                        "run_summary_score": sample.run_summary_score,
                        "run_calibration_signal": sample.run_calibration_signal,
                        "run_calibration_confidence": sample.run_calibration_confidence,
                        "run_direct_source_count": sample.run_direct_source_count,
                        "run_event_count": sample.run_event_count,
                        "downstream_observation_score": sample.downstream_observation_score,
                        "downstream_assessment_score": sample.downstream_assessment_score,
                        "session_outcome_score": sample.session_outcome_score,
                        "observation_match_count": sample.observation_match_count,
                        "assessment_match_count": sample.assessment_match_count,
                        "session_generation_depth": sample.session_generation_depth,
                        "session_outcome_event_count": sample.session_outcome_event_count,
                    },
                )
            )
        return recorded

    def _matched_generations(
        self,
        *,
        trigger_event: AuditEvent,
        generation_events: list[AuditEvent],
    ) -> list[AuditEvent]:
        scored_matches: list[tuple[float, AuditEvent]] = []
        for generation_event in generation_events:
            if trigger_event.event_type == "learner.observe":
                linked = self.linker.linked_observations(
                    generation_event=generation_event,
                    observations=[trigger_event],
                )
            else:
                linked = self.linker.linked_assessments(
                    generation_event=generation_event,
                    assessments=[trigger_event],
                )
            if not linked:
                continue
            scored_matches.append((linked[0].match_score, generation_event))
        scored_matches.sort(
            key=lambda item: (item[0], item[1].created_at), reverse=True
        )
        return [generation_event for _, generation_event in scored_matches]
