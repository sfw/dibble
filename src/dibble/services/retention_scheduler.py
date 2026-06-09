from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from dibble.models.observations import LearnerObservation, ObservationSupportLevel
from dibble.models.planning import (
    PlanningAdaptationState,
    PlanningEvidenceStrength,
    PlanningRecoveryPattern,
    TrajectoryRiskLevel,
)
from dibble.models.profile import (
    LearnerCurriculumProgressionSummary,
    OutcomeProgressSummary,
)
from dibble.models.retention import (
    RetentionReviewCandidate,
    RetentionReviewReason,
    RetentionReviewStatus,
    RetentionStrengthTier,
    RetentionSuppressionContext,
    retention_cluster_key,
)
from dibble.services.observation_profile_update import ObservationProfileUpdateResult
from dibble.services.protocols import RetentionReviewCandidateStore


_TIER_DUE_WINDOWS = {
    RetentionStrengthTier.light: timedelta(days=4),
    RetentionStrengthTier.standard: timedelta(days=2),
    RetentionStrengthTier.urgent: timedelta(days=1),
}

_TIER_RANK = {
    RetentionStrengthTier.light: 0,
    RetentionStrengthTier.standard: 1,
    RetentionStrengthTier.urgent: 2,
}


@dataclass(frozen=True, slots=True)
class RetentionNominationResult:
    candidates: list[RetentionReviewCandidate] = field(default_factory=list)
    suppressed: list[RetentionReviewCandidate] = field(default_factory=list)


@dataclass(slots=True)
class RetentionSchedulerService:
    candidate_store: RetentionReviewCandidateStore

    def upsert_candidates_for_student(
        self,
        *,
        learner_id: UUID,
        candidates: list[RetentionReviewCandidate],
        suppression_context: RetentionSuppressionContext | None = None,
    ) -> RetentionNominationResult:
        suppression_context = suppression_context or RetentionSuppressionContext()
        persisted: list[RetentionReviewCandidate] = []
        suppressed: list[RetentionReviewCandidate] = []
        for candidate in candidates:
            if str(candidate.learner_id) != str(learner_id):
                continue
            suppression_reason = self._suppression_reason(
                candidate=candidate,
                context=suppression_context,
            )
            if suppression_reason is not None:
                suppressed.append(
                    candidate.model_copy(
                        update={
                            "status": RetentionReviewStatus.suppressed,
                            "suppression_reason": suppression_reason,
                        }
                    )
                )
                continue
            existing = self.candidate_store.active_for_cluster(
                learner_id=str(learner_id),
                cluster_key=candidate.cluster_key or "",
            )
            if existing is not None:
                persisted.append(self._merge_existing_candidate(existing, candidate))
                continue
            persisted.append(self.candidate_store.upsert(candidate))
        return RetentionNominationResult(candidates=persisted, suppressed=suppressed)

    def nominate_from_observation_writeback(
        self,
        *,
        learner_id: UUID,
        observation: LearnerObservation,
        mastery_update: ObservationProfileUpdateResult,
        reference_time: datetime | None = None,
        suppression_context: RetentionSuppressionContext | None = None,
    ) -> RetentionNominationResult:
        reference_time = reference_time or datetime.now(timezone.utc)
        candidates = self._observation_writeback_candidates(
            learner_id=learner_id,
            observation=observation,
            mastery_update=mastery_update,
            reference_time=reference_time,
        )
        return self.upsert_candidates_for_student(
            learner_id=learner_id,
            candidates=candidates,
            suppression_context=suppression_context,
        )

    def nominate_from_progression_summary(
        self,
        *,
        learner_id: UUID,
        progression: LearnerCurriculumProgressionSummary,
        reference_time: datetime | None = None,
        suppression_context: RetentionSuppressionContext | None = None,
    ) -> RetentionNominationResult:
        reference_time = reference_time or datetime.now(timezone.utc)
        context = suppression_context or self.suppression_context_from_progression(
            progression
        )
        candidates: list[RetentionReviewCandidate] = []
        for outcome in self._progression_outcomes(progression):
            candidate = self.nominate_from_outcome_progress(
                learner_id=learner_id,
                outcome=outcome,
                reference_time=reference_time,
            )
            if candidate is not None:
                candidates.append(candidate)
        return self.upsert_candidates_for_student(
            learner_id=learner_id,
            candidates=candidates,
            suppression_context=context,
        )

    def nominate_from_outcome_progress(
        self,
        *,
        learner_id: UUID,
        outcome: OutcomeProgressSummary,
        reference_time: datetime | None = None,
    ) -> RetentionReviewCandidate | None:
        reference_time = reference_time or datetime.now(timezone.utc)
        if not outcome.knowledge_component_ids:
            return None
        if outcome.mastery_quality in {"fragile", "support_dependent"}:
            return self._candidate(
                learner_id=learner_id,
                kc_ids=outcome.knowledge_component_ids,
                outcome_id=outcome.outcome_id,
                reason=(
                    RetentionReviewReason.outcome_mastered
                    if outcome.state == "mastered"
                    else RetentionReviewReason.outcome_near_mastered
                ),
                tier=RetentionStrengthTier.standard,
                reference_time=reference_time,
                last_outcome_score=outcome.mastery_ratio,
                rationale="Outcome evidence is not independent enough for retention scheduling.",
                status=RetentionReviewStatus.suppressed,
                suppression_reason="fragile_or_support_dependent",
            )
        if outcome.state == "mastered":
            return self._candidate(
                learner_id=learner_id,
                kc_ids=outcome.knowledge_component_ids,
                outcome_id=outcome.outcome_id,
                reason=RetentionReviewReason.outcome_mastered,
                tier=RetentionStrengthTier.light,
                reference_time=reference_time,
                last_outcome_score=outcome.mastery_ratio,
                rationale="Outcome is currently classified as mastered; schedule a light retention check.",
            )
        if outcome.state == "ready" and outcome.mastery_ratio >= 0.76:
            return self._candidate(
                learner_id=learner_id,
                kc_ids=outcome.knowledge_component_ids,
                outcome_id=outcome.outcome_id,
                reason=RetentionReviewReason.outcome_near_mastered,
                tier=RetentionStrengthTier.standard,
                reference_time=reference_time,
                last_outcome_score=outcome.mastery_ratio,
                rationale="Outcome is near the mastery threshold and ready; schedule a retention check.",
            )
        return None

    def nominate_from_planning_state(
        self,
        *,
        learner_id: UUID,
        planning_state: PlanningAdaptationState,
        reference_time: datetime | None = None,
        suppression_context: RetentionSuppressionContext | None = None,
    ) -> RetentionNominationResult:
        reference_time = reference_time or datetime.now(timezone.utc)
        candidates: list[RetentionReviewCandidate] = []
        candidates.extend(
            self._risk_marker_candidates(
                learner_id=learner_id,
                planning_state=planning_state,
                reference_time=reference_time,
            )
        )
        candidates.extend(
            self._recovery_pattern_candidates(
                learner_id=learner_id,
                recovery_patterns=planning_state.recovery_patterns,
                reference_time=reference_time,
            )
        )
        return self.upsert_candidates_for_student(
            learner_id=learner_id,
            candidates=candidates,
            suppression_context=suppression_context,
        )

    def due_reviews_for_student(
        self,
        *,
        learner_id: UUID,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[RetentionReviewCandidate]:
        return self.candidate_store.due_reviews_for_student(
            learner_id=str(learner_id),
            now=now,
            limit=limit,
        )

    def scheduled_reviews_for_student(
        self,
        *,
        learner_id: UUID,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[RetentionReviewCandidate]:
        return self.candidate_store.scheduled_reviews_for_student(
            learner_id=str(learner_id),
            now=now,
            limit=limit,
        )

    def suppression_context_from_progression(
        self, progression: LearnerCurriculumProgressionSummary
    ) -> RetentionSuppressionContext:
        blocked_kc_ids: list[str] = []
        active_repair_kc_ids: list[str] = []
        for outcome in [progression.current_outcome, *progression.blocked_outcomes]:
            if outcome is None:
                continue
            blocked_kc_ids.extend(outcome.blocked_prerequisite_kc_ids)
        if progression.progression_action in {
            "hold_repair_target",
            "rebuild_prerequisite_first",
            "hold_bridge_target",
        } or progression.current_stage in {"repair", "bridge", "remediation"}:
            active_repair_kc_ids.extend(progression.active_target_kc_ids)
        return RetentionSuppressionContext(
            active_repair_kc_ids=sorted(dict.fromkeys(active_repair_kc_ids)),
            blocked_prerequisite_kc_ids=sorted(dict.fromkeys(blocked_kc_ids)),
            active_target_kc_ids=sorted(dict.fromkeys(progression.active_target_kc_ids)),
        )

    def _observation_writeback_candidates(
        self,
        *,
        learner_id: UUID,
        observation: LearnerObservation,
        mastery_update: ObservationProfileUpdateResult,
        reference_time: datetime,
    ) -> list[RetentionReviewCandidate]:
        updated_kc_ids = sorted((mastery_update.kc_mastery_updates or {}).keys())
        if not mastery_update.applied or not updated_kc_ids:
            return []
        observed_score = (
            mastery_update.average_recent_observed_mastery
            if mastery_update.average_recent_observed_mastery is not None
            else mastery_update.inferred_mastery
        )
        if observed_score is None or observed_score < 0.62:
            return []
        durable_signal = mastery_update.durable_mastery_signal
        if durable_signal in {"fragile", "support_dependent"}:
            return [
                self._candidate(
                    learner_id=learner_id,
                    kc_ids=updated_kc_ids,
                    reason=RetentionReviewReason.strengthened_kc_writeback,
                    tier=RetentionStrengthTier.standard,
                    reference_time=reference_time,
                    last_outcome_score=observed_score,
                    rationale="Recent KC writeback remains fragile or support-dependent.",
                    status=RetentionReviewStatus.suppressed,
                    suppression_reason="fragile_or_support_dependent",
                )
            ]
        strong_independent = (
            (
                mastery_update.evidence_strength.value
                if mastery_update.evidence_strength is not None
                else ""
            )
            == "demonstrated"
            and observation.support_level == ObservationSupportLevel.low
            and observed_score >= 0.72
        )
        if durable_signal not in {"emerging_mastery", "durable_mastery"} and not strong_independent:
            return []
        tier = (
            RetentionStrengthTier.light
            if durable_signal == "durable_mastery"
            and mastery_update.durable_mastery_confidence >= 0.45
            else RetentionStrengthTier.standard
        )
        return [
            self._candidate(
                learner_id=learner_id,
                kc_ids=updated_kc_ids,
                reason=RetentionReviewReason.strengthened_kc_writeback,
                tier=tier,
                reference_time=reference_time,
                last_outcome_score=observed_score,
                rationale="Recent KC writeback strengthened independently enough to schedule retention review.",
            )
        ]

    def _risk_marker_candidates(
        self,
        *,
        learner_id: UUID,
        planning_state: PlanningAdaptationState,
        reference_time: datetime,
    ) -> list[RetentionReviewCandidate]:
        candidates: list[RetentionReviewCandidate] = []
        for marker in planning_state.concept_cluster_markers:
            if marker.risk_level == TrajectoryRiskLevel.low:
                continue
            if marker.evidence_strength == PlanningEvidenceStrength.weak:
                continue
            tier = (
                RetentionStrengthTier.urgent
                if marker.risk_level == TrajectoryRiskLevel.high
                else RetentionStrengthTier.standard
            )
            candidates.append(
                self._candidate(
                    learner_id=learner_id,
                    kc_ids=marker.target_kc_ids,
                    cluster_key=marker.cluster_key,
                    reason=RetentionReviewReason.concept_cluster_risk,
                    tier=tier,
                    reference_time=reference_time,
                    last_outcome_score=marker.average_outcome_score,
                    rationale=marker.rationale
                    or "Concept-cluster risk is high enough to schedule a retention check.",
                )
            )
        return candidates

    def _recovery_pattern_candidates(
        self,
        *,
        learner_id: UUID,
        recovery_patterns: list[PlanningRecoveryPattern],
        reference_time: datetime,
    ) -> list[RetentionReviewCandidate]:
        candidates: list[RetentionReviewCandidate] = []
        for pattern in recovery_patterns:
            if pattern.success_count < 1:
                continue
            if pattern.success_rate < 0.5 or pattern.average_outcome_score < 0.65:
                continue
            if not pattern.target_kc_ids:
                continue
            candidates.append(
                self._candidate(
                    learner_id=learner_id,
                    kc_ids=pattern.target_kc_ids,
                    cluster_key=pattern.cluster_key,
                    reason=RetentionReviewReason.recovery_after_stall,
                    tier=RetentionStrengthTier.urgent,
                    reference_time=reference_time,
                    last_outcome_score=pattern.average_outcome_score,
                    rationale=pattern.rationale
                    or "A recent recovery after a stall should be checked soon.",
                )
            )
        return candidates

    def _progression_outcomes(
        self, progression: LearnerCurriculumProgressionSummary
    ) -> list[OutcomeProgressSummary]:
        outcomes = [
            item
            for item in [progression.current_outcome, progression.next_outcome]
            if item is not None
        ]
        outcomes.extend(progression.ready_outcomes)
        unique: dict[str, OutcomeProgressSummary] = {}
        for outcome in outcomes:
            unique[outcome.outcome_id] = outcome
        return list(unique.values())

    def _candidate(
        self,
        *,
        learner_id: UUID,
        kc_ids: list[str],
        reason: RetentionReviewReason,
        tier: RetentionStrengthTier,
        reference_time: datetime,
        outcome_id: str | None = None,
        cluster_key: str | None = None,
        last_outcome_score: float | None = None,
        rationale: str | None = None,
        status: RetentionReviewStatus = RetentionReviewStatus.scheduled,
        suppression_reason: str | None = None,
    ) -> RetentionReviewCandidate:
        normalized_kc_ids = sorted(dict.fromkeys(kc_ids))
        return RetentionReviewCandidate(
            candidate_id=str(uuid4()),
            learner_id=learner_id,
            kc_ids=normalized_kc_ids,
            cluster_key=retention_cluster_key(
                kc_ids=normalized_kc_ids,
                outcome_id=outcome_id,
                cluster_key=cluster_key,
            ),
            outcome_id=outcome_id,
            review_reason=reason,
            retention_strength_tier=tier,
            due_at=reference_time + _TIER_DUE_WINDOWS[tier],
            last_outcome_score=last_outcome_score,
            status=status,
            suppression_reason=suppression_reason,
            rationale=rationale,
            created_at=reference_time,
            updated_at=reference_time,
        )

    def _suppression_reason(
        self,
        *,
        candidate: RetentionReviewCandidate,
        context: RetentionSuppressionContext,
    ) -> str | None:
        candidate_kc_ids = set(candidate.kc_ids)
        if candidate.status == RetentionReviewStatus.suppressed:
            return candidate.suppression_reason or "suppressed_by_source_evidence"
        if candidate_kc_ids & set(context.active_repair_kc_ids):
            return "active_repair_on_same_cluster"
        if candidate_kc_ids & set(context.blocked_prerequisite_kc_ids):
            return "prerequisite_or_repair_outranks_review"
        fragile_or_supported = set(context.fragile_kc_ids) | set(
            context.support_dependent_kc_ids
        )
        if candidate_kc_ids & fragile_or_supported:
            return "fragile_or_support_dependent"
        if (
            context.overload_risk >= 0.85
            and candidate.retention_strength_tier != RetentionStrengthTier.urgent
        ):
            return "learner_overload"
        return None

    def _merge_existing_candidate(
        self,
        existing: RetentionReviewCandidate,
        proposed: RetentionReviewCandidate,
    ) -> RetentionReviewCandidate:
        tier = existing.retention_strength_tier
        if _TIER_RANK[proposed.retention_strength_tier] > _TIER_RANK[tier]:
            tier = proposed.retention_strength_tier
        due_at = min(existing.due_at, proposed.due_at)
        updated = existing.model_copy(
            update={
                "kc_ids": sorted(dict.fromkeys([*existing.kc_ids, *proposed.kc_ids])),
                "review_reason": proposed.review_reason,
                "retention_strength_tier": tier,
                "due_at": due_at,
                "last_outcome_score": proposed.last_outcome_score
                if proposed.last_outcome_score is not None
                else existing.last_outcome_score,
                "rationale": proposed.rationale or existing.rationale,
                "updated_at": max(existing.updated_at, proposed.updated_at),
            }
        )
        return self.candidate_store.upsert(updated)
