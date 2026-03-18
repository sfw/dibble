from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
)
from dibble.models.profile import LearnerProfile, SignalLevel
from dibble.plugins.contracts import RouterPlugin
from dibble.services.learner_strategy_profiles import LearnerStrategySignalService
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.services.within_session_adaptation import WithinSessionAdaptationService


@dataclass(slots=True)
class CalibratedRouter:
    base_router: RouterPlugin
    calibration_signal_service: RouterCalibrationSignalService
    strategy_signal_service: LearnerStrategySignalService
    within_session_adaptation_service: WithinSessionAdaptationService
    positive_confidence_threshold: float = 0.7
    negative_confidence_threshold: float = 0.6
    strategy_confidence_threshold: float = 0.68
    session_confidence_threshold: float = 0.55
    minimum_outcome_for_improving_relaxation: float = 0.7
    maximum_outcome_for_declining_support_raise: float = 0.72

    def route(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> AdaptiveRouteDecision:
        decision = self.base_router.route(profile, request)
        calibration = self.calibration_signal_service.signal_for(
            student_id=profile.student_id, request=request
        )
        strategy = self.strategy_signal_service.strategy_for(
            student_id=profile.student_id, request=request
        )
        session = self.within_session_adaptation_service.adaptation_for(
            student_id=profile.student_id, request=request
        )
        calibrated_decision = decision.model_copy(update={"calibration": calibration})
        if self._should_raise_support_from_session(session):
            return self._raise_support_with_reason(
                calibrated_decision,
                reason=self._session_reason(session=session),
            )
        if self._should_relax_support_from_session(profile=profile, session=session):
            return self._relax_support_with_reason(
                calibrated_decision,
                reason=self._session_reason(session=session),
            )
        if self._should_raise_support(calibration):
            return self._raise_support(calibrated_decision)
        if self._should_relax_support(profile=profile, calibration=calibration):
            return self._relax_support(calibrated_decision)
        if self._should_raise_support_from_strategy(strategy):
            return self._raise_support_with_reason(
                calibrated_decision,
                reason=self._strategy_reason(strategy=strategy),
            )
        if self._should_relax_support_from_strategy(profile=profile, strategy=strategy):
            return self._relax_support_with_reason(
                calibrated_decision,
                reason=self._strategy_reason(strategy=strategy),
            )
        if calibration.signal in {"mixed", "tentative"}:
            return calibrated_decision.model_copy(
                update={
                    "reasons": [
                        *calibrated_decision.reasons,
                        self._calibration_reason(
                            signal=calibration.signal,
                            confidence=calibration.confidence,
                            average_run_outcome_score=calibration.average_run_outcome_score,
                            progress_signal=calibration.progress_signal,
                            progress_delta=calibration.progress_delta,
                        ),
                    ]
                }
            )
        return calibrated_decision

    def _raise_support(self, decision: AdaptiveRouteDecision) -> AdaptiveRouteDecision:
        return self._raise_support_with_reason(
            decision,
            reason=self._calibration_reason(
                signal="negative",
                confidence=decision.calibration.confidence
                if decision.calibration is not None
                else 0.0,
                average_run_outcome_score=(
                    decision.calibration.average_run_outcome_score
                    if decision.calibration is not None
                    else None
                ),
                progress_signal=(
                    decision.calibration.progress_signal
                    if decision.calibration is not None
                    else "insufficient"
                ),
                progress_delta=(
                    decision.calibration.progress_delta
                    if decision.calibration is not None
                    else 0.0
                ),
            ),
        )

    def _raise_support_with_reason(
        self, decision: AdaptiveRouteDecision, *, reason: str
    ) -> AdaptiveRouteDecision:
        reasons = [
            *decision.reasons,
            reason,
        ]
        if decision.intervention_type == InterventionType.stretch:
            return decision.model_copy(
                update={
                    "intervention_type": InterventionType.reteach,
                    "delivery_mode": DeliveryMode.generated,
                    "scaffolding_level": "medium",
                    "reasons": reasons
                    + [
                        "Recent run outcomes were weak enough that the router held back stretch and returned to reteaching."
                    ],
                }
            )
        return decision.model_copy(
            update={
                "scaffolding_level": self._increase_scaffolding(
                    decision.scaffolding_level
                ),
                "reasons": reasons
                + [
                    "Recent run outcomes were weak enough that the router increased scaffolding."
                ],
            }
        )

    def _relax_support(self, decision: AdaptiveRouteDecision) -> AdaptiveRouteDecision:
        return self._relax_support_with_reason(
            decision,
            reason=self._calibration_reason(
                signal="positive",
                confidence=decision.calibration.confidence
                if decision.calibration is not None
                else 0.0,
                average_run_outcome_score=(
                    decision.calibration.average_run_outcome_score
                    if decision.calibration is not None
                    else None
                ),
                progress_signal=(
                    decision.calibration.progress_signal
                    if decision.calibration is not None
                    else "insufficient"
                ),
                progress_delta=(
                    decision.calibration.progress_delta
                    if decision.calibration is not None
                    else 0.0
                ),
            ),
        )

    def _relax_support_with_reason(
        self, decision: AdaptiveRouteDecision, *, reason: str
    ) -> AdaptiveRouteDecision:
        if decision.intervention_type not in {
            InterventionType.reteach,
            InterventionType.targeted_practice,
        }:
            return decision
        updated_scaffolding = self._decrease_scaffolding(decision.scaffolding_level)
        if updated_scaffolding == decision.scaffolding_level:
            return decision
        return decision.model_copy(
            update={
                "scaffolding_level": updated_scaffolding,
                "reasons": [
                    *decision.reasons,
                    reason,
                    "Recent run outcomes were strong enough that the router relaxed scaffolding by one level.",
                ],
            }
        )

    def _is_safety_constrained(self, profile: LearnerProfile) -> bool:
        return (
            profile.affective_state.frustration
            in {SignalLevel.medium, SignalLevel.high}
            or profile.cognitive_load.total_load >= 0.8
        )

    def _should_raise_support(self, calibration) -> bool:
        if calibration.confidence < self.negative_confidence_threshold:
            return False
        if calibration.signal == "negative":
            return True
        return calibration.progress_signal == "declining" and (
            calibration.average_run_outcome_score is None
            or calibration.average_run_outcome_score
            <= self.maximum_outcome_for_declining_support_raise
        )

    def _should_relax_support(self, *, profile: LearnerProfile, calibration) -> bool:
        if self._is_safety_constrained(profile):
            return False
        if calibration.confidence < self.positive_confidence_threshold:
            return False
        if calibration.signal == "positive":
            return True
        return (
            calibration.progress_signal == "improving"
            and calibration.average_run_outcome_score is not None
            and calibration.average_run_outcome_score
            >= self.minimum_outcome_for_improving_relaxation
        )

    def _should_raise_support_from_strategy(self, strategy) -> bool:
        return (
            strategy.support_bias < 0
            and strategy.confidence >= self.strategy_confidence_threshold
        )

    def _should_relax_support_from_strategy(
        self, *, profile: LearnerProfile, strategy
    ) -> bool:
        return (
            strategy.support_bias > 0
            and strategy.confidence >= self.strategy_confidence_threshold
            and not self._is_safety_constrained(profile)
        )

    def _should_raise_support_from_session(self, session) -> bool:
        return (
            session.support_bias < 0
            and session.source != "insufficient"
            and session.confidence >= self.session_confidence_threshold
        )

    def _should_relax_support_from_session(
        self, *, profile: LearnerProfile, session
    ) -> bool:
        return (
            session.support_bias > 0
            and session.source != "insufficient"
            and session.confidence >= self.session_confidence_threshold
            and not self._is_safety_constrained(profile)
        )

    def _increase_scaffolding(self, value: str) -> str:
        return {"low": "medium", "medium": "high", "high": "high"}.get(value, "medium")

    def _decrease_scaffolding(self, value: str) -> str:
        return {"high": "medium", "medium": "low", "low": "low"}.get(value, value)

    def _calibration_reason(
        self,
        *,
        signal: str,
        confidence: float,
        average_run_outcome_score: float | None,
        progress_signal: str = "insufficient",
        progress_delta: float = 0.0,
    ) -> str:
        if average_run_outcome_score is None:
            return "Recent run-level calibration was checked, but there was not enough durable evidence to change support."
        trend_fragment = ""
        if progress_signal in {"improving", "declining", "stable"}:
            trend_fragment = f", trend {progress_signal} ({progress_delta:+.2f})"
        return (
            f"Recent run-level calibration on similar targets was {signal} "
            f"(score {average_run_outcome_score:.2f}, confidence {confidence:.2f}{trend_fragment})."
        )

    def _strategy_reason(self, *, strategy) -> str:
        if strategy.rationale is not None:
            return (
                f"Long-horizon learner strategy was {strategy.signal} "
                f"with focus {strategy.recovery_focus}: {strategy.rationale}"
            )
        return (
            f"Long-horizon learner strategy was {strategy.signal} "
            f"with focus {strategy.recovery_focus}."
        )

    def _session_reason(self, *, session) -> str:
        if session.rationale is not None:
            return f"Same-session adaptation was {session.signal}: {session.rationale}"
        return f"Same-session adaptation was {session.signal} on the active learning session."
