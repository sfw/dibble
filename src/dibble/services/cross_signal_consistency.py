"""Cross-signal consistency service.

Detects when different evidence sources disagree about a learner's state
and surfaces those divergences so the system and teachers know when the
adaptive model is internally coherent versus contradictory.
"""

from __future__ import annotations

from dataclasses import dataclass

from dibble.models.profile import (
    LearnerProgressSummary,
    LearnerStateProfileSummary,
    LearnerStrategySummary,
    LearnerTraitProfileSummary,
    StatePredictionReliabilitySummary,
)


@dataclass(frozen=True, slots=True)
class SignalDivergence:
    """A single detected inconsistency between two evidence sources."""

    signal_a: str
    signal_b: str
    severity: str  # "high", "medium", "low"
    description: str


@dataclass(frozen=True, slots=True)
class CrossSignalConsistencyResult:
    """Aggregated consistency analysis across all signal pairs."""

    divergences: tuple[SignalDivergence, ...]
    coherence_score: float  # 0.0 = fully contradictory, 1.0 = fully coherent
    high_count: int
    medium_count: int
    low_count: int
    rationale: str


# ---------------------------------------------------------------------------
# Penalty weights per severity for coherence score computation
# ---------------------------------------------------------------------------

_SEVERITY_PENALTY = {"high": 0.20, "medium": 0.10, "low": 0.05}


def _has_data(summary_signal: str, min_sessions: int = 0, sessions: int = 0) -> bool:
    """Return True when a signal has enough evidence to participate."""
    return summary_signal != "insufficient" and sessions >= min_sessions


# ---------------------------------------------------------------------------
# Individual divergence checks
# ---------------------------------------------------------------------------


def _check_progress_vs_strategy(
    progress: LearnerProgressSummary,
    strategy: LearnerStrategySummary,
) -> list[SignalDivergence]:
    """Progress signal and strategy signal should broadly agree."""
    divergences: list[SignalDivergence] = []
    if not _has_data(progress.signal) or not _has_data(strategy.signal):
        return divergences

    # Improving progress but support-intensive strategy
    if progress.signal == "improving" and strategy.signal == "support_intensive":
        divergences.append(
            SignalDivergence(
                signal_a="progress",
                signal_b="strategy",
                severity="high",
                description=(
                    "Progress signal says improving "
                    f"(delta {progress.progress_delta:+.2f}) "
                    "but strategy signal says support-intensive. "
                    "The learner may be improving only with heavy support."
                ),
            )
        )

    # Declining progress but independence-ready strategy
    if progress.signal == "declining" and strategy.signal == "independence_ready":
        divergences.append(
            SignalDivergence(
                signal_a="progress",
                signal_b="strategy",
                severity="high",
                description=(
                    "Progress signal says declining "
                    f"(delta {progress.progress_delta:+.2f}) "
                    "but strategy signal says independence-ready. "
                    "Recent outcomes may be masking a downward trend."
                ),
            )
        )

    return divergences


def _check_strategy_vs_state_profile(
    strategy: LearnerStrategySummary,
    state_profile: LearnerStateProfileSummary,
) -> list[SignalDivergence]:
    """Strategy trajectory and state profile should be directionally aligned."""
    divergences: list[SignalDivergence] = []
    if not _has_data(strategy.signal) or not _has_data(state_profile.signal):
        return divergences

    # Strategy says accelerating but state profile says support_needed
    if (
        strategy.trajectory_state == "accelerating"
        and state_profile.signal == "support_needed"
    ):
        divergences.append(
            SignalDivergence(
                signal_a="strategy",
                signal_b="state_profile",
                severity="high",
                description=(
                    "Strategy trajectory is accelerating but the composite "
                    "state profile signals support needed. "
                    "The learner may be overperforming in narrow tasks "
                    "while broader state indicators remain fragile."
                ),
            )
        )

    # Strategy says relapsing but state profile says independence_ready
    if (
        strategy.trajectory_state == "relapsing"
        and state_profile.signal == "independence_ready"
    ):
        divergences.append(
            SignalDivergence(
                signal_a="strategy",
                signal_b="state_profile",
                severity="medium",
                description=(
                    "Strategy trajectory is relapsing but the composite "
                    "state profile signals independence ready. "
                    "The relapse may be localised to a specific KC "
                    "while overall state looks stable."
                ),
            )
        )

    return divergences


def _check_affective_cognitive_coherence(
    state_profile: LearnerStateProfileSummary,
) -> list[SignalDivergence]:
    """Certain affective/cognitive combinations are internally contradictory."""
    divergences: list[SignalDivergence] = []
    if not _has_data(state_profile.signal):
        return divergences

    # High overload risk paired with independence-ready
    if state_profile.overload_risk >= 0.7 and state_profile.signal == "independence_ready":
        divergences.append(
            SignalDivergence(
                signal_a="state_profile.overload_risk",
                signal_b="state_profile.signal",
                severity="high",
                description=(
                    f"Overload risk is high ({state_profile.overload_risk:.0%}) "
                    "but the state profile signals independence ready. "
                    "Reducing scaffolds under high cognitive load is risky."
                ),
            )
        )

    # High frustration + high engagement (unusual but not always wrong)
    if state_profile.frustration == "high" and state_profile.engagement == "high":
        divergences.append(
            SignalDivergence(
                signal_a="state_profile.frustration",
                signal_b="state_profile.engagement",
                severity="low",
                description=(
                    "Both frustration and engagement are high. "
                    "This may indicate productive struggle, but could also "
                    "signal the learner is pushing through unsustainably."
                ),
            )
        )

    return divergences


def _check_prediction_reliability_vs_confidence(
    state_prediction: StatePredictionReliabilitySummary,
    state_profile: LearnerStateProfileSummary,
) -> list[SignalDivergence]:
    """When predictions are unreliable, high-confidence decisions are suspect."""
    divergences: list[SignalDivergence] = []
    if state_prediction.evaluated_count < 3:
        return divergences

    if (
        state_prediction.weighted_accuracy < 0.5
        and state_profile.confidence >= 0.7
    ):
        divergences.append(
            SignalDivergence(
                signal_a="state_prediction_reliability",
                signal_b="state_profile.confidence",
                severity="medium",
                description=(
                    f"State prediction accuracy is low "
                    f"({state_prediction.weighted_accuracy:.0%} weighted) "
                    f"but the state profile confidence is "
                    f"{state_profile.confidence:.0%}. "
                    "Decisions based on these state classifications "
                    "may not be well-founded."
                ),
            )
        )

    return divergences


def _check_progress_vs_mastery_trend(
    progress: LearnerProgressSummary,
    state_profile: LearnerStateProfileSummary,
) -> list[SignalDivergence]:
    """Progress delta and mastery-derived trajectory should agree."""
    divergences: list[SignalDivergence] = []
    if not _has_data(progress.signal) or not _has_data(state_profile.signal):
        return divergences

    # Progress improving but state profile progress declining
    if (
        progress.signal == "improving"
        and state_profile.progress_signal == "declining"
    ):
        divergences.append(
            SignalDivergence(
                signal_a="progress",
                signal_b="state_profile.progress",
                severity="medium",
                description=(
                    "The durable progress profile says improving "
                    f"(delta {progress.progress_delta:+.2f}) "
                    "but the state profile's progress signal says declining "
                    f"(delta {state_profile.progress_delta:+.2f}). "
                    "These use different lookback windows and may be "
                    "reflecting short-term vs long-term trends."
                ),
            )
        )

    # Reverse case
    if (
        progress.signal == "declining"
        and state_profile.progress_signal == "improving"
    ):
        divergences.append(
            SignalDivergence(
                signal_a="progress",
                signal_b="state_profile.progress",
                severity="medium",
                description=(
                    "The durable progress profile says declining "
                    f"(delta {progress.progress_delta:+.2f}) "
                    "but the state profile's progress signal says improving "
                    f"(delta {state_profile.progress_delta:+.2f}). "
                    "Recent session data may not yet be reflected "
                    "in the durable profile."
                ),
            )
        )

    return divergences


def _check_trait_stability_vs_confidence(
    trait_profile: LearnerTraitProfileSummary,
) -> list[SignalDivergence]:
    """Low trait stability with high confidence in trait-derived decisions."""
    divergences: list[SignalDivergence] = []
    if not _has_data(trait_profile.signal):
        return divergences

    if trait_profile.trait_stability < 0.3 and trait_profile.challenge_evidence_strength >= 0.7:
        divergences.append(
            SignalDivergence(
                signal_a="trait_profile.trait_stability",
                signal_b="trait_profile.challenge_evidence_strength",
                severity="low",
                description=(
                    f"Trait stability is low ({trait_profile.trait_stability:.0%}) "
                    f"but challenge evidence strength is high "
                    f"({trait_profile.challenge_evidence_strength:.0%}). "
                    "Trait-based challenge decisions may be premature."
                ),
            )
        )

    return divergences


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CrossSignalConsistencyService:
    """Detects logical inconsistencies across the learner signal landscape."""

    def evaluate(
        self,
        *,
        progress: LearnerProgressSummary,
        strategy: LearnerStrategySummary,
        state_profile: LearnerStateProfileSummary,
        trait_profile: LearnerTraitProfileSummary,
        state_prediction_reliability: StatePredictionReliabilitySummary,
    ) -> CrossSignalConsistencyResult:
        divergences: list[SignalDivergence] = []

        divergences.extend(_check_progress_vs_strategy(progress, strategy))
        divergences.extend(
            _check_strategy_vs_state_profile(strategy, state_profile)
        )
        divergences.extend(_check_affective_cognitive_coherence(state_profile))
        divergences.extend(
            _check_prediction_reliability_vs_confidence(
                state_prediction_reliability, state_profile
            )
        )
        divergences.extend(
            _check_progress_vs_mastery_trend(progress, state_profile)
        )
        divergences.extend(_check_trait_stability_vs_confidence(trait_profile))

        high = sum(1 for d in divergences if d.severity == "high")
        medium = sum(1 for d in divergences if d.severity == "medium")
        low = sum(1 for d in divergences if d.severity == "low")

        total_penalty = sum(
            _SEVERITY_PENALTY.get(d.severity, 0.0) for d in divergences
        )
        coherence_score = round(max(0.0, 1.0 - total_penalty), 3)

        if not divergences:
            rationale = "All evidence sources are directionally consistent."
        else:
            parts = []
            if high:
                parts.append(f"{high} high-severity")
            if medium:
                parts.append(f"{medium} medium-severity")
            if low:
                parts.append(f"{low} low-severity")
            rationale = (
                f"Detected {', '.join(parts)} signal divergence"
                f"{'s' if len(divergences) > 1 else ''} "
                f"(coherence {coherence_score:.0%})."
            )

        return CrossSignalConsistencyResult(
            divergences=tuple(divergences),
            coherence_score=coherence_score,
            high_count=high,
            medium_count=medium,
            low_count=low,
            rationale=rationale,
        )
