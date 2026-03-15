from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import AdaptiveRouteDecision, DeliveryMode, GenerationRequest, InterventionType
from dibble.models.profile import LearnerProfile, SignalLevel
from dibble.plugins.contracts import RouterPlugin
from dibble.services.router_calibration_signals import RouterCalibrationSignalService


@dataclass(slots=True)
class CalibratedRouter:
    base_router: RouterPlugin
    calibration_signal_service: RouterCalibrationSignalService
    positive_confidence_threshold: float = 0.7
    negative_confidence_threshold: float = 0.6

    def route(self, profile: LearnerProfile, request: GenerationRequest) -> AdaptiveRouteDecision:
        decision = self.base_router.route(profile, request)
        calibration = self.calibration_signal_service.signal_for(student_id=profile.student_id, request=request)
        calibrated_decision = decision.model_copy(update={"calibration": calibration})
        if calibration.signal == "negative" and calibration.confidence >= self.negative_confidence_threshold:
            return self._raise_support(calibrated_decision)
        if (
            calibration.signal == "positive"
            and calibration.confidence >= self.positive_confidence_threshold
            and not self._is_safety_constrained(profile)
        ):
            return self._relax_support(calibrated_decision)
        if calibration.signal in {"mixed", "tentative"}:
            return calibrated_decision.model_copy(
                update={
                    "reasons": [
                        *calibrated_decision.reasons,
                        self._calibration_reason(
                            signal=calibration.signal,
                            confidence=calibration.confidence,
                            average_run_outcome_score=calibration.average_run_outcome_score,
                        ),
                    ]
                }
            )
        return calibrated_decision

    def _raise_support(self, decision: AdaptiveRouteDecision) -> AdaptiveRouteDecision:
        reasons = [
            *decision.reasons,
            self._calibration_reason(
                signal="negative",
                confidence=decision.calibration.confidence if decision.calibration is not None else 0.0,
                average_run_outcome_score=(
                    decision.calibration.average_run_outcome_score if decision.calibration is not None else None
                ),
            ),
        ]
        if decision.intervention_type == InterventionType.stretch:
            return decision.model_copy(
                update={
                    "intervention_type": InterventionType.reteach,
                    "delivery_mode": DeliveryMode.generated,
                    "scaffolding_level": "medium",
                    "reasons": reasons
                    + ["Recent run outcomes were weak enough that the router held back stretch and returned to reteaching."],
                }
            )
        return decision.model_copy(
            update={
                "scaffolding_level": self._increase_scaffolding(decision.scaffolding_level),
                "reasons": reasons + ["Recent run outcomes were weak enough that the router increased scaffolding."],
            }
        )

    def _relax_support(self, decision: AdaptiveRouteDecision) -> AdaptiveRouteDecision:
        if decision.intervention_type not in {InterventionType.reteach, InterventionType.targeted_practice}:
            return decision
        updated_scaffolding = self._decrease_scaffolding(decision.scaffolding_level)
        if updated_scaffolding == decision.scaffolding_level:
            return decision
        return decision.model_copy(
            update={
                "scaffolding_level": updated_scaffolding,
                "reasons": [
                    *decision.reasons,
                    self._calibration_reason(
                        signal="positive",
                        confidence=decision.calibration.confidence if decision.calibration is not None else 0.0,
                        average_run_outcome_score=(
                            decision.calibration.average_run_outcome_score if decision.calibration is not None else None
                        ),
                    ),
                    "Recent run outcomes were strong enough that the router relaxed scaffolding by one level.",
                ],
            }
        )

    def _is_safety_constrained(self, profile: LearnerProfile) -> bool:
        return (
            profile.affective_state.frustration in {SignalLevel.medium, SignalLevel.high}
            or profile.cognitive_load.total_load >= 0.8
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
    ) -> str:
        if average_run_outcome_score is None:
            return "Recent run-level calibration was checked, but there was not enough durable evidence to change support."
        return (
            f"Recent run-level calibration on similar targets was {signal} "
            f"(score {average_run_outcome_score:.2f}, confidence {confidence:.2f})."
        )
