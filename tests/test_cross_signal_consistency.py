"""Tests for the cross-signal consistency service."""

from __future__ import annotations

from dibble.models.profile import (
    LearnerProgressSummary,
    LearnerStateProfileSummary,
    LearnerStrategySummary,
    LearnerTraitProfileSummary,
    StatePredictionReliabilitySummary,
)
from dibble.services.cross_signal_consistency import CrossSignalConsistencyService


def _defaults(
    *,
    progress: LearnerProgressSummary | None = None,
    strategy: LearnerStrategySummary | None = None,
    state_profile: LearnerStateProfileSummary | None = None,
    trait_profile: LearnerTraitProfileSummary | None = None,
    state_prediction: StatePredictionReliabilitySummary | None = None,
) -> dict:
    return dict(
        progress=progress or LearnerProgressSummary(),
        strategy=strategy or LearnerStrategySummary(),
        state_profile=state_profile or LearnerStateProfileSummary(),
        trait_profile=trait_profile or LearnerTraitProfileSummary(),
        state_prediction_reliability=state_prediction
        or StatePredictionReliabilitySummary(),
    )


class TestNoData:
    def test_insufficient_signals_are_coherent(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(**_defaults())
        assert result.coherence_score == 1.0
        assert len(result.divergences) == 0
        assert "consistent" in result.rationale.lower()


class TestProgressVsStrategy:
    def test_improving_progress_with_support_intensive_strategy(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(
                    signal="improving", progress_delta=0.12
                ),
                strategy=LearnerStrategySummary(signal="support_intensive"),
            )
        )
        assert result.high_count == 1
        assert any(
            d.signal_a == "progress" and d.signal_b == "strategy"
            for d in result.divergences
        )

    def test_declining_progress_with_independence_ready_strategy(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(
                    signal="declining", progress_delta=-0.08
                ),
                strategy=LearnerStrategySummary(signal="independence_ready"),
            )
        )
        assert result.high_count == 1
        high_div = [d for d in result.divergences if d.severity == "high"]
        assert "declining" in high_div[0].description

    def test_aligned_progress_and_strategy_no_divergence(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(signal="improving"),
                strategy=LearnerStrategySummary(signal="independence_ready"),
            )
        )
        assert result.high_count == 0


class TestStrategyVsStateProfile:
    def test_accelerating_trajectory_with_support_needed(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                strategy=LearnerStrategySummary(
                    signal="independence_ready",
                    trajectory_state="accelerating",
                ),
                state_profile=LearnerStateProfileSummary(signal="support_needed"),
            )
        )
        assert result.high_count == 1
        assert any(
            d.signal_a == "strategy" and d.signal_b == "state_profile"
            for d in result.divergences
        )

    def test_relapsing_trajectory_with_independence_ready(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                strategy=LearnerStrategySummary(
                    signal="support_intensive",
                    trajectory_state="relapsing",
                ),
                state_profile=LearnerStateProfileSummary(signal="independence_ready"),
            )
        )
        assert result.medium_count == 1


class TestAffectiveCognitiveCoherence:
    def test_high_overload_risk_with_independence_ready(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                state_profile=LearnerStateProfileSummary(
                    signal="independence_ready",
                    overload_risk=0.8,
                )
            )
        )
        assert result.high_count == 1
        assert "overload" in result.divergences[0].description.lower()

    def test_high_frustration_and_engagement(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                state_profile=LearnerStateProfileSummary(
                    signal="monitor",
                    frustration="high",
                    engagement="high",
                )
            )
        )
        assert result.low_count == 1

    def test_moderate_overload_no_divergence(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                state_profile=LearnerStateProfileSummary(
                    signal="independence_ready",
                    overload_risk=0.3,
                )
            )
        )
        assert result.high_count == 0


class TestPredictionReliabilityVsConfidence:
    def test_low_accuracy_high_confidence(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                state_prediction=StatePredictionReliabilitySummary(
                    evaluated_count=5,
                    weighted_accuracy=0.35,
                ),
                state_profile=LearnerStateProfileSummary(
                    signal="monitor",
                    confidence=0.85,
                ),
            )
        )
        assert result.medium_count == 1

    def test_insufficient_predictions_skipped(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                state_prediction=StatePredictionReliabilitySummary(
                    evaluated_count=2,
                    weighted_accuracy=0.2,
                ),
                state_profile=LearnerStateProfileSummary(
                    signal="monitor",
                    confidence=0.9,
                ),
            )
        )
        assert result.medium_count == 0


class TestProgressVsMasteryTrend:
    def test_improving_progress_declining_state(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(signal="improving", progress_delta=0.1),
                state_profile=LearnerStateProfileSummary(
                    signal="support_needed",
                    progress_signal="declining",
                    progress_delta=-0.05,
                ),
            )
        )
        assert result.medium_count >= 1
        assert any(
            "lookback" in d.description.lower()
            for d in result.divergences
            if d.signal_b == "state_profile.progress"
        )

    def test_declining_progress_improving_state(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(
                    signal="declining", progress_delta=-0.1
                ),
                state_profile=LearnerStateProfileSummary(
                    signal="monitor",
                    progress_signal="improving",
                    progress_delta=0.06,
                ),
            )
        )
        assert result.medium_count >= 1


class TestTraitStabilityVsConfidence:
    def test_low_stability_high_challenge_evidence(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                trait_profile=LearnerTraitProfileSummary(
                    signal="stable",
                    trait_stability=0.2,
                    challenge_evidence_strength=0.8,
                )
            )
        )
        assert result.low_count >= 1

    def test_stable_traits_no_divergence(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                trait_profile=LearnerTraitProfileSummary(
                    signal="stable",
                    trait_stability=0.8,
                    challenge_evidence_strength=0.8,
                )
            )
        )
        divergence_from_traits = [
            d for d in result.divergences if "trait" in d.signal_a
        ]
        assert len(divergence_from_traits) == 0


class TestCoherenceScoring:
    def test_coherence_score_decreases_with_severity(self) -> None:
        svc = CrossSignalConsistencyService()
        # Two high-severity divergences
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(
                    signal="improving", progress_delta=0.12
                ),
                strategy=LearnerStrategySummary(
                    signal="support_intensive",
                    trajectory_state="accelerating",
                ),
                state_profile=LearnerStateProfileSummary(
                    signal="support_needed",
                ),
            )
        )
        assert result.high_count >= 2
        assert result.coherence_score <= 0.7

    def test_perfect_coherence_when_aligned(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(signal="improving"),
                strategy=LearnerStrategySummary(
                    signal="independence_ready",
                    trajectory_state="consolidating",
                ),
                state_profile=LearnerStateProfileSummary(
                    signal="independence_ready",
                    progress_signal="improving",
                    overload_risk=0.2,
                ),
            )
        )
        assert result.coherence_score == 1.0

    def test_rationale_mentions_severity_counts(self) -> None:
        svc = CrossSignalConsistencyService()
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(
                    signal="improving", progress_delta=0.12
                ),
                strategy=LearnerStrategySummary(signal="support_intensive"),
            )
        )
        assert "high-severity" in result.rationale

    def test_coherence_score_never_below_zero(self) -> None:
        """Even with many divergences, score clamps at 0."""
        svc = CrossSignalConsistencyService()
        # Trigger as many divergences as possible
        result = svc.evaluate(
            **_defaults(
                progress=LearnerProgressSummary(
                    signal="improving", progress_delta=0.15
                ),
                strategy=LearnerStrategySummary(
                    signal="support_intensive",
                    trajectory_state="accelerating",
                ),
                state_profile=LearnerStateProfileSummary(
                    signal="support_needed",
                    progress_signal="declining",
                    progress_delta=-0.1,
                    overload_risk=0.8,
                    frustration="high",
                    engagement="high",
                    confidence=0.9,
                ),
                state_prediction=StatePredictionReliabilitySummary(
                    evaluated_count=10,
                    weighted_accuracy=0.3,
                ),
                trait_profile=LearnerTraitProfileSummary(
                    signal="stable",
                    trait_stability=0.1,
                    challenge_evidence_strength=0.9,
                ),
            )
        )
        assert result.coherence_score >= 0.0
