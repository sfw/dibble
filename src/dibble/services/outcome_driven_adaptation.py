from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dibble.models.generation import ModalityRoutingPrior, RoutingPriorScope
from dibble.models.rollout import AdaptationStrength, RolloutCapability
from dibble.models.telemetry import AuditEvent
from dibble.services.rollout_decision_service import RolloutDecisionService
from dibble.services.protocols import (
    AuditStore,
    CurriculumContentLibraryStore,
    ModalityRoutingPriorStore,
)

_GLOBAL_CONTEXT_KEY = "__global__"


@dataclass(frozen=True, slots=True)
class OutcomeDrivenAdaptationUpdate:
    learner_id: UUID
    generation_id: str
    updated_prior_keys: tuple[str, ...]
    library_entry_count: int = 0


@dataclass(slots=True)
class OutcomeDrivenAdaptationService:
    audit_store: AuditStore
    prior_store: ModalityRoutingPriorStore
    curriculum_content_library_store: CurriculumContentLibraryStore
    rollout_decision_service: RolloutDecisionService | None = None
    max_events: int = 500

    def record_from_summary_events(
        self,
        *,
        summary_events: list[AuditEvent],
    ) -> list[OutcomeDrivenAdaptationUpdate]:
        if not summary_events:
            return []
        events = self.audit_store.list(limit=self.max_events)
        events_by_id = {event.event_id: event for event in events}
        updates: list[OutcomeDrivenAdaptationUpdate] = []
        for summary_event in summary_events:
            learner_id = summary_event.student_id
            if learner_id is None:
                continue
            generation_event_id = str(
                summary_event.payload.get("source_generation_event_id", "")
            )
            generation_event = events_by_id.get(generation_event_id)
            if generation_event is None:
                continue
            plugin_id = str(generation_event.payload.get("modality_plugin_id", "text"))
            composition_ids = generation_event.payload.get("selected_modalities", ["text"])
            if not isinstance(composition_ids, list):
                composition_ids = ["text"]
            composition_key = "+".join(str(item) for item in composition_ids if item) or "text"
            context_key = str(
                generation_event.payload.get("routing_context_key") or _GLOBAL_CONTEXT_KEY
            )
            observed_at = summary_event.created_at
            raw_outcome_score = float(summary_event.payload.get("run_summary_score", 0.5))
            raw_engagement_score = _optional_float(
                summary_event.payload.get("downstream_observation_score")
            )
            raw_progress_score = _optional_float(
                summary_event.payload.get("downstream_assessment_score")
            )
            adaptation_decision = (
                self.rollout_decision_service.decision_for(
                    capability=RolloutCapability.outcome_driven_adaptation,
                    learner_id=str(learner_id),
                )
                if self.rollout_decision_service is not None
                else None
            )
            if (
                adaptation_decision is not None
                and adaptation_decision.mode == AdaptationStrength.off.value
            ):
                continue
            adaptation_factor = _adaptation_factor(
                adaptation_decision.mode if adaptation_decision is not None else None
            )
            outcome_score = _scale_score(raw_outcome_score, factor=adaptation_factor)
            engagement_score = _scale_optional_score(
                raw_engagement_score,
                factor=adaptation_factor,
            )
            progress_score = _scale_optional_score(
                raw_progress_score,
                factor=adaptation_factor,
            )
            updated_priors = [
                self._apply_prior_observation(
                    learner_id=learner_id,
                    scope=RoutingPriorScope.plugin,
                    prior_key=plugin_id,
                    context_key=context_key,
                    outcome_score=outcome_score,
                    engagement_score=engagement_score,
                    progress_score=progress_score,
                    observed_at=observed_at,
                ),
                self._apply_prior_observation(
                    learner_id=learner_id,
                    scope=RoutingPriorScope.plugin,
                    prior_key=plugin_id,
                    context_key=_GLOBAL_CONTEXT_KEY,
                    outcome_score=outcome_score,
                    engagement_score=engagement_score,
                    progress_score=progress_score,
                    observed_at=observed_at,
                ),
                self._apply_prior_observation(
                    learner_id=learner_id,
                    scope=RoutingPriorScope.composition,
                    prior_key=composition_key,
                    context_key=context_key,
                    outcome_score=outcome_score,
                    engagement_score=engagement_score,
                    progress_score=progress_score,
                    observed_at=observed_at,
                ),
                self._apply_prior_observation(
                    learner_id=learner_id,
                    scope=RoutingPriorScope.composition,
                    prior_key=composition_key,
                    context_key=_GLOBAL_CONTEXT_KEY,
                    outcome_score=outcome_score,
                    engagement_score=engagement_score,
                    progress_score=progress_score,
                    observed_at=observed_at,
                ),
            ]
            generation_id = str(summary_event.payload.get("generation_id", ""))
            updated_library_entries = (
                self.curriculum_content_library_store.record_outcome(
                    source_generation_id=generation_id,
                    outcome_score=outcome_score,
                    engagement_score=engagement_score,
                    progress_score=progress_score,
                )
                if generation_id
                else []
            )
            updates.append(
                OutcomeDrivenAdaptationUpdate(
                    learner_id=learner_id,
                    generation_id=generation_id,
                    updated_prior_keys=tuple(
                        f"{prior.scope.value}:{prior.prior_key}:{prior.context_key}"
                        for prior in updated_priors
                    ),
                    library_entry_count=len(updated_library_entries),
                )
            )
        return updates

    def _apply_prior_observation(
        self,
        *,
        learner_id: UUID,
        scope: RoutingPriorScope,
        prior_key: str,
        context_key: str,
        outcome_score: float,
        engagement_score: float | None,
        progress_score: float | None,
        observed_at: datetime,
    ) -> ModalityRoutingPrior:
        existing = self.prior_store.get(
            learner_id=learner_id,
            scope=scope.value,
            prior_key=prior_key,
            context_key=context_key,
        )
        if existing is None:
            prior = ModalityRoutingPrior(
                learner_id=learner_id,
                scope=scope,
                prior_key=prior_key,
                context_key=context_key,
                evidence_count=1,
                average_outcome_score=round(outcome_score, 2),
                average_engagement_score=(
                    round(engagement_score, 2) if engagement_score is not None else 0.5
                ),
                average_progress_score=(
                    round(progress_score, 2) if progress_score is not None else 0.5
                ),
                positive_outcome_rate=1.0 if outcome_score >= 0.65 else 0.0,
                last_outcome_score=round(outcome_score, 2),
                last_selected_at=observed_at,
                last_outcome_at=observed_at,
                updated_at=observed_at,
            )
            return self.prior_store.upsert(prior)
        next_count = existing.evidence_count + 1
        positive_count = round(existing.positive_outcome_rate * existing.evidence_count)
        if outcome_score >= 0.65:
            positive_count += 1
        recovery_attempt_count = existing.recovery_attempt_count
        recovery_success_count = existing.recovery_success_count
        if existing.last_outcome_score is not None and existing.last_outcome_score <= 0.45:
            recovery_attempt_count += 1
            if outcome_score >= 0.6:
                recovery_success_count += 1
        updated = existing.model_copy(
            update={
                "evidence_count": next_count,
                "average_outcome_score": _rolling_average(
                    existing.average_outcome_score,
                    outcome_score,
                    existing.evidence_count,
                ),
                "average_engagement_score": _rolling_average(
                    existing.average_engagement_score,
                    engagement_score,
                    existing.evidence_count,
                ),
                "average_progress_score": _rolling_average(
                    existing.average_progress_score,
                    progress_score,
                    existing.evidence_count,
                ),
                "recent_outcome_delta": round(
                    outcome_score - existing.average_outcome_score,
                    2,
                ),
                "recent_engagement_delta": round(
                    (engagement_score if engagement_score is not None else existing.average_engagement_score)
                    - existing.average_engagement_score,
                    2,
                ),
                "recent_progress_delta": round(
                    (progress_score if progress_score is not None else existing.average_progress_score)
                    - existing.average_progress_score,
                    2,
                ),
                "positive_outcome_rate": round(positive_count / next_count, 2),
                "recovery_attempt_count": recovery_attempt_count,
                "recovery_success_count": recovery_success_count,
                "last_outcome_score": round(outcome_score, 2),
                "last_selected_at": observed_at,
                "last_outcome_at": observed_at,
                "updated_at": observed_at,
            }
        )
        return self.prior_store.upsert(updated)


def _rolling_average(
    current_average: float,
    observed_value: float | None,
    current_count: int,
) -> float:
    if observed_value is None:
        return round(current_average, 2)
    if current_count <= 0:
        return round(observed_value, 2)
    return round(
        ((current_average * current_count) + observed_value) / (current_count + 1),
        2,
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _adaptation_factor(mode: str | None) -> float:
    if mode == AdaptationStrength.aggressive.value:
        return 1.25
    if mode == AdaptationStrength.standard.value:
        return 1.0
    if mode == AdaptationStrength.conservative.value:
        return 0.35
    return 1.0


def _scale_score(value: float, *, factor: float) -> float:
    centered = value - 0.5
    return round(max(0.0, min(1.0, 0.5 + (centered * factor))), 2)


def _scale_optional_score(value: float | None, *, factor: float) -> float | None:
    if value is None:
        return None
    return _scale_score(value, factor=factor)
