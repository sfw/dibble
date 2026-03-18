from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.generation import GenerationModeCalibration, RequestedContentType
from dibble.services.generation_prompt_outcomes import GenerationPromptOutcomeScorer
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class GenerationPromptSelector:
    audit_store: AuditStore
    min_samples_per_variant: int = 2
    max_events: int = 500
    outcome_scorer: GenerationPromptOutcomeScorer = field(
        default_factory=GenerationPromptOutcomeScorer
    )

    def select_variant(
        self,
        *,
        content_type: RequestedContentType,
        fallback_variant: str,
        mode_calibration: GenerationModeCalibration | None = None,
    ) -> str:
        steered_variant = self._steered_variant(
            content_type=content_type,
            fallback_variant=fallback_variant,
            mode_calibration=mode_calibration,
        )
        if steered_variant is not None:
            return steered_variant
        prefix = f"{content_type.value}."
        events = self.audit_store.list(limit=self.max_events)
        all_generation_events = [
            event for event in events if event.event_type == "content.generate"
        ]
        generation_events = [
            event
            for event in all_generation_events
            if event.event_type == "content.generate"
            and event.payload.get("content_type") == content_type.value
            and event.payload.get("prompt_template_name")
            and str(event.payload.get("prompt_template_name")).startswith(prefix)
            and event.payload.get("prompt_template_variant")
        ]
        if not generation_events:
            return fallback_variant
        observation_events = [
            event for event in events if event.event_type == "learner.observe"
        ]
        assessment_events = [
            event for event in events if event.event_type == "assessment.socratic"
        ]
        run_summary_events = [
            event for event in events if event.event_type == "learning.run.summary"
        ]

        grouped: dict[str, list[float]] = {}
        validation_counts: dict[str, int] = {}
        grounded_counts: dict[str, int] = {}
        downstream_counts: dict[str, int] = {}
        assessment_counts: dict[str, int] = {}
        session_outcome_counts: dict[str, int] = {}
        run_summary_counts: dict[str, int] = {}
        persisted_run_summary_counts: dict[str, int] = {}
        positive_run_signal_counts: dict[str, int] = {}
        negative_run_signal_counts: dict[str, int] = {}
        run_signal_confidence_totals: dict[str, float] = {}
        observation_trace_counts: dict[str, int] = {}
        assessment_trace_counts: dict[str, int] = {}
        session_generation_depths: dict[str, int] = {}
        for event in generation_events:
            sample = self.outcome_scorer.score(
                generation_event=event,
                candidate_generations=all_generation_events,
                candidate_observations=observation_events,
                candidate_assessments=assessment_events,
                candidate_run_summaries=run_summary_events,
            )
            grouped.setdefault(sample.variant, []).append(sample.composite_score)
            validation_counts[sample.variant] = validation_counts.get(
                sample.variant, 0
            ) + (1 if sample.validation_passed else 0)
            grounded_counts[sample.variant] = grounded_counts.get(sample.variant, 0) + (
                1 if sample.grounding_count > 0 else 0
            )
            downstream_counts[sample.variant] = downstream_counts.get(
                sample.variant, 0
            ) + (1 if sample.downstream_observation_score is not None else 0)
            assessment_counts[sample.variant] = assessment_counts.get(
                sample.variant, 0
            ) + (1 if sample.downstream_assessment_score is not None else 0)
            session_outcome_counts[sample.variant] = session_outcome_counts.get(
                sample.variant, 0
            ) + (1 if sample.session_outcome_score is not None else 0)
            run_summary_counts[sample.variant] = run_summary_counts.get(
                sample.variant, 0
            ) + (1 if sample.run_summary_score is not None else 0)
            persisted_run_summary_counts[sample.variant] = (
                persisted_run_summary_counts.get(sample.variant, 0)
                + (1 if sample.run_summary_source == "persisted" else 0)
            )
            positive_run_signal_counts[sample.variant] = positive_run_signal_counts.get(
                sample.variant, 0
            ) + (1 if sample.run_calibration_signal == "positive" else 0)
            negative_run_signal_counts[sample.variant] = negative_run_signal_counts.get(
                sample.variant, 0
            ) + (1 if sample.run_calibration_signal == "negative" else 0)
            run_signal_confidence_totals[sample.variant] = (
                run_signal_confidence_totals.get(sample.variant, 0.0)
                + sample.run_calibration_confidence
            )
            observation_trace_counts[sample.variant] = (
                observation_trace_counts.get(sample.variant, 0)
                + sample.observation_match_count
            )
            assessment_trace_counts[sample.variant] = (
                assessment_trace_counts.get(sample.variant, 0)
                + sample.assessment_match_count
            )
            session_generation_depths[sample.variant] = (
                session_generation_depths.get(sample.variant, 0)
                + sample.session_generation_depth
            )

        eligible = {
            variant: scores
            for variant, scores in grouped.items()
            if len(scores) >= self.min_samples_per_variant
        }
        if not eligible:
            return fallback_variant

        def rank(item: tuple[str, list[float]]) -> tuple[float, float, int]:
            variant, scores = item
            event_count = len(scores)
            average_outcome = sum(scores) / event_count
            validation_rate = validation_counts.get(variant, 0) / event_count
            grounding_rate = grounded_counts.get(variant, 0) / event_count
            downstream_rate = downstream_counts.get(variant, 0) / event_count
            assessment_rate = assessment_counts.get(variant, 0) / event_count
            session_outcome_rate = session_outcome_counts.get(variant, 0) / event_count
            run_summary_rate = run_summary_counts.get(variant, 0) / event_count
            persisted_run_summary_rate = (
                persisted_run_summary_counts.get(variant, 0) / event_count
            )
            positive_run_signal_rate = (
                positive_run_signal_counts.get(variant, 0) / event_count
            )
            negative_run_signal_rate = (
                negative_run_signal_counts.get(variant, 0) / event_count
            )
            average_run_signal_confidence = (
                run_signal_confidence_totals.get(variant, 0.0) / event_count
            )
            observation_trace_depth = min(
                1.0, observation_trace_counts.get(variant, 0) / max(1, event_count * 3)
            )
            assessment_trace_depth = min(
                1.0, assessment_trace_counts.get(variant, 0) / max(1, event_count * 3)
            )
            session_generation_depth = min(
                1.0, session_generation_depths.get(variant, 0) / max(1, event_count * 2)
            )
            return (
                average_outcome
                + (validation_rate * 0.08)
                + (grounding_rate * 0.04)
                + (downstream_rate * 0.04)
                + (assessment_rate * 0.08)
                + (session_outcome_rate * 0.06)
                + (run_summary_rate * 0.08)
                + (persisted_run_summary_rate * 0.06)
                + (positive_run_signal_rate * 0.08)
                - (negative_run_signal_rate * 0.08)
                + (average_run_signal_confidence * 0.06)
                + (observation_trace_depth * 0.03)
                + (assessment_trace_depth * 0.05)
                + (session_generation_depth * 0.04),
                average_outcome,
                event_count,
            )

        return max(eligible.items(), key=rank)[0]

    def _steered_variant(
        self,
        *,
        content_type: RequestedContentType,
        fallback_variant: str,
        mode_calibration: GenerationModeCalibration | None,
    ) -> str | None:
        if mode_calibration is None:
            return None
        if content_type not in {
            RequestedContentType.micro_explanation,
            RequestedContentType.worked_example,
            RequestedContentType.practice_problem,
        }:
            return None
        if (
            mode_calibration.state_profile_source != "insufficient"
            and mode_calibration.state_profile_load_reliability >= 0.58
            and mode_calibration.state_profile_overload_risk >= 0.64
        ):
            return "guided_reflection"
        if (
            mode_calibration.trait_profile_source != "insufficient"
            and mode_calibration.trait_profile_trait_stability >= 0.72
            and mode_calibration.trait_profile_challenge_tolerance >= 0.66
            and content_type
            in {
                RequestedContentType.practice_problem,
                RequestedContentType.worked_example,
            }
        ):
            return "baseline"
        if (
            mode_calibration.socratic_profile_source != "insufficient"
            and mode_calibration.socratic_profile_confidence >= 0.56
        ):
            if mode_calibration.socratic_profile_signal in {
                "model_then_release",
                "clarify_then_check",
            }:
                return "guided_reflection"
            if mode_calibration.socratic_profile_signal in {
                "independent_check",
                "vary_representation",
            }:
                return "baseline"
        if (
            mode_calibration.session_source == "insufficient"
            or mode_calibration.session_confidence < 0.55
            or mode_calibration.session_assessment_count <= 0
        ):
            return None
        if mode_calibration.session_arc_action == "reprobe_new_angle":
            return "baseline"
        if mode_calibration.session_arc_action in {
            "model_repair",
            "restate_then_apply",
            "bridge_with_target",
        }:
            return "guided_reflection"
        if mode_calibration.socratic_steering_action in {
            "repair_then_model",
            "clarify_then_check",
            "restate_then_apply",
        }:
            return "guided_reflection"
        if mode_calibration.socratic_steering_action == "verify_transfer":
            return "baseline"
        return (
            fallback_variant
            if mode_calibration.socratic_steering_action == "probe_from_new_angle"
            else None
        )
