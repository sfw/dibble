from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.models.assessment import (
    SocraticAssessmentRequest,
    SocraticAssessmentResponse,
    SocraticAssessmentSession,
    SocraticEvidenceStrength,
)
from dibble.models.profile import LearnerProfile, SignalLevel
from dibble.services.knowledge_state_migration import KnowledgeStateMigrator


def _clamp(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _blend(prior: float, observed: float, weight: float) -> float:
    return (prior * (1.0 - weight)) + (observed * weight)


def _signal_to_score(level: SignalLevel) -> float:
    mapping = {
        SignalLevel.none: 0.0,
        SignalLevel.low: 0.33,
        SignalLevel.medium: 0.66,
        SignalLevel.high: 1.0,
    }
    return mapping[level]


def _score_to_signal(score: float) -> SignalLevel:
    if score >= 0.83:
        return SignalLevel.high
    if score >= 0.5:
        return SignalLevel.medium
    if score >= 0.16:
        return SignalLevel.low
    return SignalLevel.none


@dataclass(frozen=True, slots=True)
class SocraticProfileUpdateResult:
    profile: LearnerProfile
    applied: bool
    kc_mastery_updates: dict[str, float]
    lo_mastery_updates: dict[str, float]
    propagated_kc_mastery_updates: dict[str, float] | None = None
    propagated_lo_mastery_updates: dict[str, float] | None = None
    confidence_calibration: float | None = None
    self_monitoring: float | None = None
    help_seeking: SignalLevel | None = None


@dataclass(slots=True)
class SocraticProfileUpdater:
    knowledge_state_migrator: KnowledgeStateMigrator | None = None

    def apply(
        self,
        profile: LearnerProfile,
        request: SocraticAssessmentRequest,
        response: SocraticAssessmentResponse,
        session: SocraticAssessmentSession | None,
    ) -> SocraticProfileUpdateResult:
        if not request.learner_response:
            return SocraticProfileUpdateResult(
                profile=profile,
                applied=False,
                kc_mastery_updates={},
                lo_mastery_updates={},
            )

        target_kc_ids = session.target_kc_ids if session is not None and session.target_kc_ids else request.target_kc_ids
        target_lo_ids = session.target_lo_ids if session is not None and session.target_lo_ids else request.target_lo_ids
        if not target_kc_ids and not target_lo_ids:
            return SocraticProfileUpdateResult(
                profile=profile,
                applied=False,
                kc_mastery_updates={},
                lo_mastery_updates={},
            )

        evidence_weight = self._evidence_weight(response.evaluation.evidence_strength, response.evaluation.evidence_score)
        new_kc_mastery = dict(profile.knowledge_state.kc_mastery)
        new_lo_mastery = dict(profile.knowledge_state.lo_mastery)

        kc_updates = self._apply_mastery_updates(
            current_values=new_kc_mastery,
            target_ids=target_kc_ids,
            inferred_mastery=response.evaluation.inferred_mastery,
            evidence_weight=evidence_weight,
            evidence_strength=response.evaluation.evidence_strength,
        )
        lo_updates = self._apply_mastery_updates(
            current_values=new_lo_mastery,
            target_ids=target_lo_ids,
            inferred_mastery=response.evaluation.inferred_mastery,
            evidence_weight=evidence_weight,
            evidence_strength=response.evaluation.evidence_strength,
        )
        migration_result = (
            self.knowledge_state_migrator.migrate(
                kc_mastery=new_kc_mastery,
                lo_mastery=new_lo_mastery,
                direct_kc_updates=kc_updates,
                direct_lo_updates=lo_updates,
                evidence_strength=response.evaluation.evidence_strength,
            )
            if self.knowledge_state_migrator is not None
            else None
        )

        metacognitive_weight = min(0.65, evidence_weight + 0.1)
        confidence_alignment = response.evaluation.evidence_dimensions.confidence_alignment
        self_monitoring_signal = _clamp(
            (response.evaluation.evidence_dimensions.reasoning_signal * 0.6)
            + (response.evaluation.evidence_dimensions.progression_signal * 0.4)
        )
        target_help_score = self._target_help_score(response)
        updated_help_seeking = _score_to_signal(
            _blend(
                _signal_to_score(profile.metacognitive_state.help_seeking),
                target_help_score,
                metacognitive_weight,
            )
        )
        updated_profile = profile.model_copy(
            update={
                "knowledge_state": profile.knowledge_state.model_copy(
                    update={
                        "kc_mastery": new_kc_mastery,
                        "lo_mastery": new_lo_mastery,
                        "last_updated": datetime.now(timezone.utc),
                    }
                ),
                "metacognitive_state": profile.metacognitive_state.model_copy(
                    update={
                        "confidence_calibration": round(
                            _blend(
                                profile.metacognitive_state.confidence_calibration,
                                confidence_alignment,
                                metacognitive_weight,
                            ),
                            2,
                        ),
                        "self_monitoring": round(
                            _blend(
                                profile.metacognitive_state.self_monitoring,
                                self_monitoring_signal,
                                metacognitive_weight,
                            ),
                            2,
                        ),
                        "help_seeking": updated_help_seeking,
                        "inferred_at": datetime.now(timezone.utc),
                    }
                ),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return SocraticProfileUpdateResult(
            profile=updated_profile,
            applied=True,
            kc_mastery_updates=kc_updates,
            lo_mastery_updates=lo_updates,
            propagated_kc_mastery_updates=(
                migration_result.kc_mastery_updates if migration_result is not None else {}
            ),
            propagated_lo_mastery_updates=(
                migration_result.lo_mastery_updates if migration_result is not None else {}
            ),
            confidence_calibration=updated_profile.metacognitive_state.confidence_calibration,
            self_monitoring=updated_profile.metacognitive_state.self_monitoring,
            help_seeking=updated_help_seeking,
        )

    def _apply_mastery_updates(
        self,
        *,
        current_values: dict[str, float],
        target_ids: list[str],
        inferred_mastery: float,
        evidence_weight: float,
        evidence_strength: SocraticEvidenceStrength,
    ) -> dict[str, float]:
        updates: dict[str, float] = {}
        for target_id in target_ids:
            prior = current_values.get(target_id)
            if prior is None:
                updated_value = inferred_mastery
            else:
                adjusted_weight = evidence_weight
                if inferred_mastery < prior:
                    adjusted_weight *= {
                        SocraticEvidenceStrength.demonstrated: 0.2,
                        SocraticEvidenceStrength.emerging: 0.5,
                        SocraticEvidenceStrength.insufficient: 0.9,
                    }[evidence_strength]
                updated_value = _blend(prior, inferred_mastery, adjusted_weight)
            rounded = round(_clamp(updated_value), 2)
            current_values[target_id] = rounded
            updates[target_id] = rounded
        return updates

    def _evidence_weight(self, strength: SocraticEvidenceStrength, evidence_score: float) -> float:
        base_weight = {
            SocraticEvidenceStrength.insufficient: 0.2,
            SocraticEvidenceStrength.emerging: 0.38,
            SocraticEvidenceStrength.demonstrated: 0.58,
        }[strength]
        return min(0.72, base_weight + (evidence_score * 0.12))

    def _target_help_score(self, response: SocraticAssessmentResponse) -> float:
        if response.evaluation.evidence_strength == SocraticEvidenceStrength.demonstrated:
            return 0.1 if response.evaluation.evidence_dimensions.confidence_alignment >= 0.7 else 0.25
        if response.evaluation.evidence_strength == SocraticEvidenceStrength.emerging:
            return 0.45
        if response.evaluation.evidence_dimensions.misconception_risk >= 0.45:
            return 0.95
        return 0.72
