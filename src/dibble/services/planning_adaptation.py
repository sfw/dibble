from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID, uuid4

from dibble.models.planning import (
    PlanningAdaptationSignal,
    PlanningAdaptationState,
    PlanningConceptClusterMarker,
    PlanningEffectivenessProfile,
    PlanningEvidenceStrength,
    PlanningRecoveryPattern,
    PlanningSignalKind,
    TrajectoryRevisionActionType,
    TrajectoryRevisionAdjustment,
    TrajectoryRiskLevel,
)
from dibble.models.profile import (
    LearnerStateProfileSummary,
    LearnerStrategySummary,
)
from dibble.models.telemetry import AuditEvent
from dibble.services.learner_state_signal import LearnerStateSignalService
from dibble.services.learner_strategy_signal import LearnerStrategySignalService
from dibble.services.protocols import AuditStore, ModalityRoutingPriorStore

_GLOBAL_CONTEXT_KEY = "__global__"


@dataclass(slots=True)
class PlanningAdaptationService:
    audit_store: AuditStore
    prior_store: ModalityRoutingPriorStore | None = None
    strategy_signal_service: LearnerStrategySignalService | None = None
    state_signal_service: LearnerStateSignalService | None = None
    max_events: int = 500
    max_profiles_per_dimension: int = 2

    def build_state(
        self,
        *,
        student_id: UUID,
        existing_state: PlanningAdaptationState | None = None,
    ) -> PlanningAdaptationState:
        events = self.audit_store.list(limit=self.max_events)
        summary_events = [
            event
            for event in events
            if event.event_type == "learning.run.summary" and event.student_id == student_id
        ]
        if not summary_events:
            return existing_state or PlanningAdaptationState()

        generation_events = {
            event.event_id: event
            for event in events
            if event.event_type == "content.generate" and event.student_id == student_id
        }
        strategy = (
            self.strategy_signal_service.latest_for_student(student_id=student_id)
            if self.strategy_signal_service is not None
            else LearnerStrategySummary()
        )
        state = (
            self.state_signal_service.latest_for_student(student_id=student_id)
            if self.state_signal_service is not None
            else LearnerStateProfileSummary()
        )

        cluster_markers = self._concept_cluster_markers(
            summary_events=summary_events,
        )
        recovery_patterns = self._recovery_patterns(
            summary_events=summary_events,
            generation_events=generation_events,
        )
        preferred_modality = self._preferred_modality(student_id=student_id)
        cluster_markers = [
            marker.model_copy(
                update={
                    "preferred_recovery_pattern": self._preferred_recovery_pattern_for(
                        cluster_key=marker.cluster_key,
                        recovery_patterns=recovery_patterns,
                    ),
                    "preferred_modality": preferred_modality
                    if preferred_modality is not None
                    and marker.risk_level != TrajectoryRiskLevel.low
                    else marker.preferred_modality,
                }
            )
            for marker in cluster_markers
        ]
        effectiveness_profiles = self._effectiveness_profiles(
            summary_events=summary_events,
            generation_events=generation_events,
        )
        recent_signals = self._recent_signals(
            summary_events=summary_events,
            generation_events=generation_events,
            strategy=strategy,
            state=state,
            cluster_markers=cluster_markers,
            recovery_patterns=recovery_patterns,
            effectiveness_profiles=effectiveness_profiles,
            preferred_modality=preferred_modality,
        )
        active_adjustments = self._active_adjustments(
            strategy=strategy,
            state=state,
            cluster_markers=cluster_markers,
            recovery_patterns=recovery_patterns,
            effectiveness_profiles=effectiveness_profiles,
            recent_signals=recent_signals,
        )
        return PlanningAdaptationState(
            revision_count=(existing_state.revision_count if existing_state is not None else 0),
            active_pacing_adjustment=self._active_pacing_adjustment(
                adjustments=active_adjustments,
                fallback=(
                    existing_state.active_pacing_adjustment
                    if existing_state is not None
                    else "standard"
                ),
            ),
            active_revisit_density=self._active_revisit_density(
                adjustments=active_adjustments
            ),
            preferred_scaffolding_pattern=self._preferred_scaffolding_pattern(
                recovery_patterns=recovery_patterns,
                cluster_markers=cluster_markers,
                fallback=(
                    existing_state.preferred_scaffolding_pattern
                    if existing_state is not None
                    else None
                ),
            ),
            preferred_modality=preferred_modality
            or (existing_state.preferred_modality if existing_state is not None else None),
            recent_signals=recent_signals,
            concept_cluster_markers=cluster_markers,
            recovery_patterns=recovery_patterns,
            effectiveness_profiles=effectiveness_profiles,
            active_adjustments=active_adjustments,
            updated_at=max(event.created_at for event in summary_events),
        )

    def _concept_cluster_markers(
        self,
        *,
        summary_events: list[AuditEvent],
    ) -> list[PlanningConceptClusterMarker]:
        grouped: dict[str, list[AuditEvent]] = defaultdict(list)
        for event in summary_events:
            cluster_key = self._cluster_key(event.payload.get("target_kc_ids"))
            if cluster_key is None:
                continue
            grouped[cluster_key].append(event)
        markers: list[PlanningConceptClusterMarker] = []
        for cluster_key, events in grouped.items():
            events.sort(key=lambda item: item.created_at)
            scores = [self._outcome_score(item) for item in events]
            stall_count = sum(1 for item in events if self._is_stall(item))
            recovery_success_count = 0
            for previous, current in zip(events, events[1:]):
                if self._outcome_score(previous) <= 0.5 and self._outcome_score(current) >= 0.65:
                    recovery_success_count += 1
            recent_scores = scores[-2:] or scores
            prior_scores = scores[:-2]
            recent_average = sum(recent_scores) / len(recent_scores)
            prior_average = (
                sum(prior_scores) / len(prior_scores) if prior_scores else recent_average
            )
            average_outcome = round(sum(scores) / len(scores), 2)
            recent_trend = round(recent_average - prior_average, 2)
            evidence_strength = self._evidence_strength(sample_count=len(events))
            risk_level = TrajectoryRiskLevel.low
            if (
                len(events) >= 4
                and stall_count >= 2
                and (average_outcome < 0.62 or recovery_success_count >= 1)
            ):
                risk_level = TrajectoryRiskLevel.high
            elif len(events) >= 2 and (stall_count >= 1 or average_outcome < 0.66):
                risk_level = TrajectoryRiskLevel.moderate
            target_kc_ids = self._target_kc_ids(events[0])
            markers.append(
                PlanningConceptClusterMarker(
                    cluster_key=cluster_key,
                    label=self._cluster_label(target_kc_ids),
                    target_kc_ids=target_kc_ids,
                    evidence_strength=evidence_strength,
                    risk_level=risk_level,
                    sample_count=len(events),
                    stall_count=stall_count,
                    recovery_success_count=recovery_success_count,
                    average_outcome_score=average_outcome,
                    recent_trend=recent_trend,
                    rationale=(
                        f"{stall_count} stall episode(s) and outcome average "
                        f"{average_outcome:.2f} across {len(events)} recent run(s)."
                    ),
                    last_observed_at=events[-1].created_at,
                )
            )
        markers.sort(
            key=lambda item: (
                item.risk_level == TrajectoryRiskLevel.high,
                item.risk_level == TrajectoryRiskLevel.moderate,
                item.sample_count,
                -item.average_outcome_score,
            ),
            reverse=True,
        )
        return markers

    def _recovery_patterns(
        self,
        *,
        summary_events: list[AuditEvent],
        generation_events: dict[str, AuditEvent],
    ) -> list[PlanningRecoveryPattern]:
        grouped: dict[str, list[AuditEvent]] = defaultdict(list)
        for event in summary_events:
            cluster_key = self._cluster_key(event.payload.get("target_kc_ids"))
            if cluster_key is None:
                continue
            grouped[cluster_key].append(event)
        pattern_data: dict[str, dict[str, object]] = {}
        for cluster_key, events in grouped.items():
            events.sort(key=lambda item: item.created_at)
            for previous, current in zip(events, events[1:]):
                if self._outcome_score(previous) > 0.5:
                    continue
                generation_event = generation_events.get(
                    str(current.payload.get("source_generation_event_id", ""))
                )
                pattern = self._pattern_fields(
                    summary_event=current,
                    generation_event=generation_event,
                )
                pattern_key = pattern["pattern_key"]
                if pattern_key is None:
                    continue
                existing = pattern_data.setdefault(
                    pattern_key,
                    {
                        "cluster_key": cluster_key,
                        "target_kc_ids": self._target_kc_ids(current),
                        "intent": pattern["intent"],
                        "content_type": pattern["content_type"],
                        "phase": pattern["phase"],
                        "modality": pattern["modality"],
                        "prompt_variant": pattern["prompt_variant"],
                        "sample_count": 0,
                        "success_count": 0,
                        "outcome_total": 0.0,
                        "last_observed_at": current.created_at,
                    },
                )
                existing["sample_count"] = int(existing["sample_count"]) + 1
                existing["outcome_total"] = float(existing["outcome_total"]) + self._outcome_score(
                    current
                )
                if self._outcome_score(current) >= 0.65:
                    existing["success_count"] = int(existing["success_count"]) + 1
                if current.created_at > existing["last_observed_at"]:
                    existing["last_observed_at"] = current.created_at

        patterns: list[PlanningRecoveryPattern] = []
        for pattern_key, data in pattern_data.items():
            sample_count = int(data["sample_count"])
            success_count = int(data["success_count"])
            average_outcome = round(float(data["outcome_total"]) / max(1, sample_count), 2)
            success_rate = round(success_count / max(1, sample_count), 2)
            evidence_strength = self._evidence_strength(sample_count=sample_count)
            patterns.append(
                PlanningRecoveryPattern(
                    pattern_key=pattern_key,
                    label=self._pattern_label(
                        intent=str(data["intent"]) if data["intent"] is not None else None,
                        content_type=(
                            str(data["content_type"])
                            if data["content_type"] is not None
                            else None
                        ),
                        phase=str(data["phase"]) if data["phase"] is not None else None,
                        modality=(
                            str(data["modality"]) if data["modality"] is not None else None
                        ),
                    ),
                    evidence_strength=evidence_strength,
                    sample_count=sample_count,
                    success_count=success_count,
                    success_rate=success_rate,
                    average_outcome_score=average_outcome,
                    cluster_key=str(data["cluster_key"]),
                    target_kc_ids=list(data["target_kc_ids"]),
                    intent=str(data["intent"]) if data["intent"] is not None else None,
                    content_type=(
                        str(data["content_type"])
                        if data["content_type"] is not None
                        else None
                    ),
                    phase=str(data["phase"]) if data["phase"] is not None else None,
                    modality=str(data["modality"]) if data["modality"] is not None else None,
                    prompt_variant=(
                        str(data["prompt_variant"])
                        if data["prompt_variant"] is not None
                        else None
                    ),
                    rationale=(
                        f"{success_count} successful recovery attempt(s) out of "
                        f"{sample_count} for {pattern_key}."
                    ),
                    last_observed_at=data["last_observed_at"],
                )
            )
        patterns.sort(
            key=lambda item: (
                item.success_rate,
                item.average_outcome_score,
                item.sample_count,
            ),
            reverse=True,
        )
        return patterns[:5]

    def _effectiveness_profiles(
        self,
        *,
        summary_events: list[AuditEvent],
        generation_events: dict[str, AuditEvent],
    ) -> list[PlanningEffectivenessProfile]:
        profiles: list[PlanningEffectivenessProfile] = []
        for dimension_type in ("intent", "content_type", "phase"):
            grouped: dict[str, list[tuple[AuditEvent, AuditEvent | None]]] = defaultdict(list)
            for event in summary_events:
                generation_event = generation_events.get(
                    str(event.payload.get("source_generation_event_id", ""))
                )
                fields = self._pattern_fields(
                    summary_event=event,
                    generation_event=generation_event,
                )
                dimension_key = fields.get(dimension_type)
                if not dimension_key:
                    continue
                grouped[str(dimension_key)].append((event, generation_event))
            ranked = sorted(
                grouped.items(),
                key=lambda item: (len(item[1]), self._group_average(item[1])),
                reverse=True,
            )
            for dimension_key, matches in ranked[: self.max_profiles_per_dimension]:
                sample_count = len(matches)
                average_outcome = round(self._group_average(matches), 2)
                success_rate = round(
                    sum(
                        1 for event, _ in matches if self._outcome_score(event) >= 0.65
                    )
                    / max(1, sample_count),
                    2,
                )
                recovery_success_rate = round(
                    sum(
                        1
                        for event, _ in matches
                        if self._outcome_score(event) >= 0.65
                        and event.payload.get("run_calibration_signal") == "positive"
                    )
                    / max(1, sample_count),
                    2,
                )
                first_fields = self._pattern_fields(
                    summary_event=matches[0][0],
                    generation_event=matches[0][1],
                )
                profiles.append(
                    PlanningEffectivenessProfile(
                        dimension_type=dimension_type,
                        dimension_key=dimension_key,
                        label=f"{dimension_type}:{dimension_key}",
                        evidence_strength=self._evidence_strength(
                            sample_count=sample_count
                        ),
                        sample_count=sample_count,
                        average_outcome_score=average_outcome,
                        success_rate=success_rate,
                        recovery_success_rate=recovery_success_rate,
                        intent=(
                            str(first_fields["intent"])
                            if first_fields["intent"] is not None
                            else None
                        ),
                        content_type=(
                            str(first_fields["content_type"])
                            if first_fields["content_type"] is not None
                            else None
                        ),
                        phase=(
                            str(first_fields["phase"])
                            if first_fields["phase"] is not None
                            else None
                        ),
                        modality=(
                            str(first_fields["modality"])
                            if first_fields["modality"] is not None
                            else None
                        ),
                        target_kc_ids=self._target_kc_ids(matches[0][0]),
                        rationale=(
                            f"{dimension_type} '{dimension_key}' averaged "
                            f"{average_outcome:.2f} over {sample_count} matched run(s)."
                        ),
                        updated_at=max(event.created_at for event, _ in matches),
                    )
                )
        profiles.sort(
            key=lambda item: (
                item.evidence_strength == PlanningEvidenceStrength.strong,
                item.sample_count,
                item.average_outcome_score,
            ),
            reverse=True,
        )
        return profiles[:6]

    def _recent_signals(
        self,
        *,
        summary_events: list[AuditEvent],
        generation_events: dict[str, AuditEvent],
        strategy: LearnerStrategySummary,
        state: LearnerStateProfileSummary,
        cluster_markers: list[PlanningConceptClusterMarker],
        recovery_patterns: list[PlanningRecoveryPattern],
        effectiveness_profiles: list[PlanningEffectivenessProfile],
        preferred_modality: str | None,
    ) -> list[PlanningAdaptationSignal]:
        signals: list[PlanningAdaptationSignal] = []
        session_signal = self._session_effectiveness_signal(
            summary_events=summary_events,
            strategy=strategy,
            state=state,
        )
        if session_signal is not None:
            signals.append(session_signal)
        for marker in cluster_markers[:2]:
            if marker.risk_level == TrajectoryRiskLevel.low:
                continue
            signals.append(
                PlanningAdaptationSignal(
                    signal_id=str(uuid4()),
                    kind=PlanningSignalKind.concept_cluster,
                    evidence_strength=marker.evidence_strength,
                    direction=(
                        "negative"
                        if marker.risk_level == TrajectoryRiskLevel.high
                        else "mixed"
                    ),
                    sample_count=marker.sample_count,
                    average_outcome_score=marker.average_outcome_score,
                    progress_delta=marker.recent_trend,
                    cluster_key=marker.cluster_key,
                    target_kc_ids=list(marker.target_kc_ids),
                    modality=marker.preferred_modality,
                    rationale=marker.rationale,
                    observed_at=marker.last_observed_at or summary_events[0].created_at,
                )
            )
        for pattern in recovery_patterns[:2]:
            if pattern.sample_count < 2:
                continue
            signals.append(
                PlanningAdaptationSignal(
                    signal_id=str(uuid4()),
                    kind=PlanningSignalKind.recovery_pattern,
                    evidence_strength=pattern.evidence_strength,
                    direction="positive" if pattern.success_rate >= 0.67 else "mixed",
                    sample_count=pattern.sample_count,
                    average_outcome_score=pattern.average_outcome_score,
                    success_rate=pattern.success_rate,
                    cluster_key=pattern.cluster_key,
                    target_kc_ids=list(pattern.target_kc_ids),
                    intent=pattern.intent,
                    content_type=pattern.content_type,
                    phase=pattern.phase,
                    modality=pattern.modality,
                    rationale=pattern.rationale,
                    observed_at=pattern.last_observed_at or summary_events[0].created_at,
                )
            )
        for profile in effectiveness_profiles[:2]:
            if profile.sample_count < 2:
                continue
            signals.append(
                PlanningAdaptationSignal(
                    signal_id=str(uuid4()),
                    kind=(
                        PlanningSignalKind.phase_effectiveness
                        if profile.dimension_type == "phase"
                        else PlanningSignalKind.content_type_effectiveness
                    ),
                    evidence_strength=profile.evidence_strength,
                    direction="positive" if profile.average_outcome_score >= 0.7 else "negative",
                    sample_count=profile.sample_count,
                    average_outcome_score=profile.average_outcome_score,
                    success_rate=profile.success_rate,
                    target_kc_ids=list(profile.target_kc_ids),
                    intent=profile.intent,
                    content_type=profile.content_type,
                    phase=profile.phase,
                    modality=profile.modality,
                    rationale=profile.rationale,
                    observed_at=profile.updated_at,
                )
            )
        if preferred_modality is not None and self.prior_store is not None:
            prior = next(
                (
                    item
                    for item in self.prior_store.list_for_learner(learner_id=summary_events[0].student_id)
                    if item.scope == "plugin"
                    and item.context_key == _GLOBAL_CONTEXT_KEY
                    and item.prior_key == preferred_modality
                ),
                None,
            )
            if prior is not None and prior.evidence_count >= 2:
                signals.append(
                    PlanningAdaptationSignal(
                        signal_id=str(uuid4()),
                        kind=PlanningSignalKind.modality_effectiveness,
                        evidence_strength=self._evidence_strength(
                            sample_count=prior.evidence_count
                        ),
                        direction="positive",
                        sample_count=prior.evidence_count,
                        average_outcome_score=prior.average_outcome_score,
                        success_rate=prior.positive_outcome_rate,
                        modality=preferred_modality,
                        rationale=(
                            f"Recent {preferred_modality} selections averaged "
                            f"{prior.average_outcome_score:.2f} over {prior.evidence_count} run(s)."
                        ),
                        observed_at=prior.updated_at,
                    )
                )
        signals.sort(
            key=lambda item: (
                item.evidence_strength == PlanningEvidenceStrength.strong,
                item.sample_count,
                item.average_outcome_score or 0.0,
            ),
            reverse=True,
        )
        return signals[:8]

    def _session_effectiveness_signal(
        self,
        *,
        summary_events: list[AuditEvent],
        strategy: LearnerStrategySummary,
        state: LearnerStateProfileSummary,
    ) -> PlanningAdaptationSignal | None:
        scores = [self._outcome_score(event) for event in summary_events[:5]]
        average_outcome = round(sum(scores) / len(scores), 2)
        recent_scores = scores[:2]
        prior_scores = scores[2:]
        progress_delta = (
            round(
                (sum(recent_scores) / len(recent_scores))
                - (sum(prior_scores) / len(prior_scores)),
                2,
            )
            if prior_scores
            else strategy.progress_delta
        )
        direction = "mixed"
        if (
            strategy.trajectory_state in {"relapsing", "plateaued"}
            or strategy.progress_signal == "declining"
            or progress_delta <= -0.08
        ):
            direction = "negative"
        elif strategy.trajectory_state == "accelerating" or progress_delta >= 0.08:
            direction = "positive"
        if len(summary_events) < 2 and strategy.matched_session_count < 2:
            return None
        return PlanningAdaptationSignal(
            signal_id=str(uuid4()),
            kind=PlanningSignalKind.session_effectiveness,
            evidence_strength=self._evidence_strength(
                sample_count=max(len(summary_events[:5]), strategy.matched_session_count)
            ),
            direction=direction,
            sample_count=max(len(summary_events[:5]), strategy.matched_session_count),
            average_outcome_score=average_outcome,
            progress_delta=progress_delta,
            rationale=(
                "Recent cross-session outcomes now inform pacing and revisit density "
                f"(trajectory={strategy.trajectory_state}, overload={state.overload_risk:.2f})."
            ),
            observed_at=summary_events[0].created_at,
        )

    def _active_adjustments(
        self,
        *,
        strategy: LearnerStrategySummary,
        state: LearnerStateProfileSummary,
        cluster_markers: list[PlanningConceptClusterMarker],
        recovery_patterns: list[PlanningRecoveryPattern],
        effectiveness_profiles: list[PlanningEffectivenessProfile],
        recent_signals: list[PlanningAdaptationSignal],
    ) -> list[TrajectoryRevisionAdjustment]:
        adjustments: list[TrajectoryRevisionAdjustment] = []
        session_signal = next(
            (
                signal
                for signal in recent_signals
                if signal.kind == PlanningSignalKind.session_effectiveness
            ),
            None,
        )
        if (
            session_signal is not None
            and session_signal.evidence_strength != PlanningEvidenceStrength.weak
            and (
                session_signal.direction == "negative"
                or strategy.trajectory_state in {"relapsing", "plateaued"}
                or state.overload_risk >= 0.65
            )
        ):
            adjustments.append(
                TrajectoryRevisionAdjustment(
                    action_type=TrajectoryRevisionActionType.slow_pacing,
                    evidence_strength=session_signal.evidence_strength,
                    value="slower",
                    rationale=(
                        "Recent session effectiveness is weak enough to slow the expected "
                        "pace instead of assuming the current rhythm still fits."
                    ),
                )
            )
            adjustments.append(
                TrajectoryRevisionAdjustment(
                    action_type=TrajectoryRevisionActionType.increase_revisit_density,
                    evidence_strength=session_signal.evidence_strength,
                    value="2",
                    rationale=(
                        "Durable session outcomes support adding explicit revisit density "
                        "before moving further ahead."
                    ),
                )
            )
        high_risk_marker = next(
            (
                marker
                for marker in cluster_markers
                if marker.risk_level == TrajectoryRiskLevel.high
            ),
            None,
        )
        if high_risk_marker is not None:
            adjustments.append(
                TrajectoryRevisionAdjustment(
                    action_type=TrajectoryRevisionActionType.slow_pacing,
                    evidence_strength=high_risk_marker.evidence_strength,
                    cluster_key=high_risk_marker.cluster_key,
                    target_kc_ids=list(high_risk_marker.target_kc_ids),
                    value="slower",
                    rationale=(
                        "Repeated low-quality progress on one cluster is enough to slow "
                        "the expected pacing, even if one recent run recovered."
                    ),
                )
            )
            adjustments.append(
                TrajectoryRevisionAdjustment(
                    action_type=TrajectoryRevisionActionType.increase_revisit_density,
                    evidence_strength=high_risk_marker.evidence_strength,
                    cluster_key=high_risk_marker.cluster_key,
                    target_kc_ids=list(high_risk_marker.target_kc_ids),
                    value="2",
                    rationale=(
                        "A high-friction concept cluster should get denser revisits before "
                        "the trajectory assumes durable recovery."
                    ),
                )
            )
            adjustments.append(
                TrajectoryRevisionAdjustment(
                    action_type=TrajectoryRevisionActionType.insert_recovery_scaffold,
                    evidence_strength=high_risk_marker.evidence_strength,
                    cluster_key=high_risk_marker.cluster_key,
                    target_kc_ids=list(high_risk_marker.target_kc_ids),
                    value=high_risk_marker.preferred_recovery_pattern
                    or "guided_rebuild",
                    rationale=(
                        "The learner has repeatedly stalled on this concept cluster, so "
                        "the plan should insert a bounded recovery scaffold before pushing ahead."
                    ),
                )
            )
        best_recovery = next(
            (
                pattern
                for pattern in recovery_patterns
                if pattern.sample_count >= 2 and pattern.success_rate >= 0.67
            ),
            None,
        )
        if best_recovery is not None:
            adjustments.append(
                TrajectoryRevisionAdjustment(
                    action_type=TrajectoryRevisionActionType.strengthen_scaffolding,
                    evidence_strength=best_recovery.evidence_strength,
                    cluster_key=best_recovery.cluster_key,
                    target_kc_ids=list(best_recovery.target_kc_ids),
                    value=best_recovery.label,
                    rationale=(
                        "Recovery success has clustered around one scaffolding pattern, so "
                        "planning should keep that pattern ready for similar stalls."
                    ),
                )
            )
        repair_profile = next(
            (
                profile
                for profile in effectiveness_profiles
                if profile.dimension_type == "phase"
                and profile.dimension_key in {"repair", "bridge"}
                and profile.sample_count >= 2
                and profile.average_outcome_score >= 0.7
            ),
            None,
        )
        if repair_profile is not None:
            adjustments.append(
                TrajectoryRevisionAdjustment(
                    action_type=TrajectoryRevisionActionType.alternative_ordering,
                    evidence_strength=repair_profile.evidence_strength,
                    value="repair_before_target",
                    rationale=(
                        "Repair and bridge phases have outperformed straight-ahead target work "
                        "recently, so the trajectory can bias toward scaffold-first ordering."
                    ),
                )
            )
        return adjustments[:5]

    def _active_pacing_adjustment(
        self,
        *,
        adjustments: list[TrajectoryRevisionAdjustment],
        fallback: str,
    ) -> str:
        return next(
            (
                adjustment.value
                for adjustment in adjustments
                if adjustment.action_type == TrajectoryRevisionActionType.slow_pacing
            ),
            fallback,
        )

    def _active_revisit_density(
        self,
        *,
        adjustments: list[TrajectoryRevisionAdjustment],
    ) -> int:
        raw_value = next(
            (
                adjustment.value
                for adjustment in adjustments
                if adjustment.action_type
                == TrajectoryRevisionActionType.increase_revisit_density
            ),
            "1",
        )
        try:
            return max(1, min(3, int(raw_value)))
        except ValueError:
            return 1

    def _preferred_scaffolding_pattern(
        self,
        *,
        recovery_patterns: list[PlanningRecoveryPattern],
        cluster_markers: list[PlanningConceptClusterMarker],
        fallback: str | None,
    ) -> str | None:
        best_pattern = next(
            (
                pattern.label
                for pattern in recovery_patterns
                if pattern.success_rate >= 0.67 and pattern.sample_count >= 2
            ),
            None,
        )
        if best_pattern is not None:
            return best_pattern
        return next(
            (
                marker.preferred_recovery_pattern
                for marker in cluster_markers
                if marker.preferred_recovery_pattern is not None
            ),
            fallback,
        )

    def _preferred_modality(self, *, student_id: UUID) -> str | None:
        if self.prior_store is None:
            return None
        priors = [
            prior
            for prior in self.prior_store.list_for_learner(learner_id=student_id)
            if prior.scope == "plugin"
            and prior.context_key == _GLOBAL_CONTEXT_KEY
            and prior.evidence_count >= 2
        ]
        if not priors:
            return None
        priors.sort(
            key=lambda prior: (
                prior.average_outcome_score,
                prior.positive_outcome_rate,
                prior.evidence_count,
            ),
            reverse=True,
        )
        return priors[0].prior_key

    def _preferred_recovery_pattern_for(
        self,
        *,
        cluster_key: str,
        recovery_patterns: list[PlanningRecoveryPattern],
    ) -> str | None:
        return next(
            (
                pattern.label
                for pattern in recovery_patterns
                if pattern.cluster_key == cluster_key and pattern.success_rate >= 0.5
            ),
            None,
        )

    def _pattern_fields(
        self,
        *,
        summary_event: AuditEvent,
        generation_event: AuditEvent | None,
    ) -> dict[str, object | None]:
        content_type = summary_event.payload.get("content_type")
        intent = summary_event.payload.get("intent")
        phase = None
        modality = None
        prompt_variant = None
        if generation_event is not None:
            phase = generation_event.payload.get("progression_target_stage")
            modality = generation_event.payload.get("modality_plugin_id")
            prompt_variant = generation_event.payload.get("prompt_template_variant")
            content_type = generation_event.payload.get("content_type") or content_type
            intent = generation_event.payload.get("intent") or intent
        pattern_key_parts = [
            str(item)
            for item in [phase, intent, content_type, modality, prompt_variant]
            if item
        ]
        return {
            "intent": intent,
            "content_type": content_type,
            "phase": phase,
            "modality": modality,
            "prompt_variant": prompt_variant,
            "pattern_key": ":".join(pattern_key_parts) if pattern_key_parts else None,
        }

    def _pattern_label(
        self,
        *,
        intent: str | None,
        content_type: str | None,
        phase: str | None,
        modality: str | None,
    ) -> str:
        label_parts = [
            part
            for part in [phase, intent, content_type, modality]
            if part is not None
        ]
        return " -> ".join(label_parts) if label_parts else "general_support"

    def _cluster_key(self, target_kc_ids: object) -> str | None:
        if not isinstance(target_kc_ids, list) or not target_kc_ids:
            return None
        return "|".join(sorted(str(item) for item in target_kc_ids if item))

    def _cluster_label(self, target_kc_ids: list[str]) -> str:
        if not target_kc_ids:
            return "Current concept cluster"
        if len(target_kc_ids) == 1:
            return f"KC {target_kc_ids[0]}"
        return f"KCs {', '.join(target_kc_ids[:3])}"

    def _target_kc_ids(self, event: AuditEvent) -> list[str]:
        raw_ids = event.payload.get("target_kc_ids", [])
        if not isinstance(raw_ids, list):
            return []
        return [str(item) for item in raw_ids if item is not None]

    def _group_average(
        self, matches: list[tuple[AuditEvent, AuditEvent | None]]
    ) -> float:
        return sum(self._outcome_score(event) for event, _ in matches) / max(1, len(matches))

    def _outcome_score(self, event: AuditEvent) -> float:
        return float(event.payload.get("run_summary_score", 0.5))

    def _is_stall(self, event: AuditEvent) -> bool:
        return self._outcome_score(event) <= 0.55 or event.payload.get(
            "run_calibration_signal"
        ) == "negative"

    def _evidence_strength(self, *, sample_count: int) -> PlanningEvidenceStrength:
        if sample_count >= 4:
            return PlanningEvidenceStrength.strong
        if sample_count >= 2:
            return PlanningEvidenceStrength.emerging
        return PlanningEvidenceStrength.weak
