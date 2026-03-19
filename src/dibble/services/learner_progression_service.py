from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from dibble.models.curriculum import Outcome, KnowledgeComponent
from dibble.models.profile import (
    OutcomeProgressSummary,
    LearnerCurriculumProgressionSummary,
    LearnerFlowSummary,
    OrdinaryMasterySummary,
)
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.mastery_decay import decayed_kc_mastery
from dibble.services.protocols import (
    KnowledgeComponentStore,
    OutcomeStore,
    ProfileStore,
)
from dibble.services.workflow_rationale import combine_rationales

MASTERY_THRESHOLD = 0.8
PREREQUISITE_READY_THRESHOLD = 0.65
ACTIVE_OUTCOME_LIMIT = 3

# ORCH-001: Trend-aware threshold adjustments.  An improving trend on an
# outcome's KCs makes mastery easier to reach (lower threshold) so the
# learner can advance sooner.  A declining trend makes it harder so the
# learner is held until the decline stabilises.
TREND_MASTERY_BONUS = 0.04  # improving: lower mastery threshold
TREND_MASTERY_PENALTY = 0.03  # declining: raise mastery threshold
TREND_PREREQUISITE_BONUS = 0.03  # improving: lower prerequisite threshold
TREND_PREREQUISITE_PENALTY = 0.04  # declining: raise prerequisite threshold

# ADAPT-006: Mastery quality gate.  Even when raw KC mastery exceeds the
# mastery threshold, the outcome is not truly mastered if the ordinary
# mastery profile shows the learner reached that score with heavy support
# or volatile evidence.  These signals and confidence floors gate outcome
# mastery so dependents do not unlock prematurely.
MASTERY_QUALITY_GATE_SIGNALS = {"support_dependent", "fragile"}
MASTERY_QUALITY_GATE_CONFIDENCE = 0.4


@dataclass(slots=True)
class OutcomePlanningEntry:
    summary: OutcomeProgressSummary
    dependency_outcome_ids: list[str]
    blocked_prerequisite_kc_ids: list[str]
    current_flow_match_count: int = 0
    deferred_flow_match_count: int = 0
    depth: int = 0


@dataclass(slots=True)
class LearnerProgressionService:
    profile_store: ProfileStore
    outcome_store: OutcomeStore
    knowledge_component_store: KnowledgeComponentStore
    learner_flow_service: LearnerFlowService
    ordinary_mastery_signal_service: object | None = None
    quality_gate_signal_service: object | None = None

    def build_for_student(
        self, *, student_id: UUID
    ) -> LearnerCurriculumProgressionSummary | None:
        profile = self.profile_store.get(student_id)
        if profile is None:
            return None

        outcomes = sorted(
            self.outcome_store.list(), key=lambda outcome: outcome.outcome_id
        )
        if not outcomes:
            flow = self.learner_flow_service.build_for_student(student_id=student_id)
            return LearnerCurriculumProgressionSummary(
                flow_type=flow.flow_type,
                current_stage=flow.current_phase,
                progression_action=flow.progression_action,
                active_target_kc_ids=list(flow.active_target_kc_ids),
                rationale="No curriculum outcomes are available for broader progression tracking.",
                updated_at=flow.updated_at or profile.updated_at,
            )

        flow = self.learner_flow_service.build_for_student(student_id=student_id)
        components = {
            component.kc_id: component
            for component in self.knowledge_component_store.list()
        }
        active_target_kc_ids = list(
            flow.active_target_kc_ids or flow.next_step.target_kc_ids
        )
        deferred_target_kc_ids = self._deferred_target_kc_ids(flow=flow)
        outcome_by_id = {outcome.outcome_id: outcome for outcome in outcomes}
        kc_to_outcome_ids = self._kc_to_outcome_ids(outcomes=outcomes)

        # DATA-004: Apply time-based mastery decay so KCs that have not been
        # practiced recently are discounted before outcome classification.
        now = datetime.now(timezone.utc)
        effective_kc_mastery = decayed_kc_mastery(
            profile.knowledge_state.kc_mastery,
            profile.knowledge_state.kc_last_practiced,
            reference_time=now,
        )

        # ORCH-001: Collect per-KC ordinary mastery trend signals so outcome
        # classification can adjust thresholds for improving/declining KCs.
        # ADAPT-006: Also collect the full signal summaries so the mastery
        # quality gate can block outcomes whose KCs are support_dependent
        # or fragile even when raw mastery is above threshold.
        kc_trends, kc_mastery_signals = self._kc_mastery_profiles(
            student_id=student_id, components=components
        )

        # ADAPT-006: Compute the effective quality gate confidence once,
        # adjusting for outcome feedback if the signal service is available.
        effective_quality_gate_confidence = self._effective_quality_gate_confidence(
            student_id=student_id
        )

        entries = [
            self._outcome_entry(
                outcome=outcome,
                components=components,
                kc_mastery=effective_kc_mastery,
                flow=flow,
                active_target_kc_ids=active_target_kc_ids,
                deferred_target_kc_ids=deferred_target_kc_ids,
                current_stage=flow.target_stage,
                outcome_by_id=outcome_by_id,
                kc_to_outcome_ids=kc_to_outcome_ids,
                kc_trends=kc_trends,
                kc_mastery_signals=kc_mastery_signals,
                quality_gate_confidence=effective_quality_gate_confidence,
            )
            for outcome in outcomes
        ]
        depth_cache: dict[str, int] = {}
        for entry in entries:
            entry.depth = self._outcome_depth(
                outcome_id=entry.summary.outcome_id,
                dependency_map={
                    item.summary.outcome_id: item.dependency_outcome_ids
                    for item in entries
                },
                cache=depth_cache,
                visiting=set(),
            )

        active_outcomes = sorted(
            [entry for entry in entries if entry.summary.state == "active"],
            key=self._active_priority,
        )
        ready_outcomes = sorted(
            [entry for entry in entries if entry.summary.state == "ready"],
            key=self._ready_priority,
        )
        blocked_outcomes = sorted(
            [entry for entry in entries if entry.summary.state == "blocked"],
            key=self._blocked_priority,
        )
        mastered_outcomes = sorted(
            [entry for entry in entries if entry.summary.state == "mastered"],
            key=lambda entry: (entry.depth, entry.summary.outcome_id),
        )

        current_outcome = active_outcomes[0].summary if active_outcomes else None
        next_outcome = ready_outcomes[0].summary if ready_outcomes else None
        if current_outcome is not None:
            status = "active_curriculum_focus"
            rationale = current_outcome.rationale
        elif next_outcome is not None:
            status = "ready_for_next_outcome"
            rationale = next_outcome.rationale
        elif blocked_outcomes:
            status = "blocked_on_prerequisites"
            rationale = blocked_outcomes[0].summary.rationale
        else:
            status = "catalog_mastered"
            rationale = (
                "Current mapped curriculum outcomes appear sufficiently mastered."
            )

        return LearnerCurriculumProgressionSummary(
            status=status,
            flow_type=flow.flow_type,
            current_stage=flow.current_phase,
            progression_action=flow.progression_action,
            active_target_kc_ids=active_target_kc_ids,
            outcome_count=len(entries),
            mastered_outcome_count=len(mastered_outcomes),
            ready_outcome_count=len(ready_outcomes),
            blocked_outcome_count=len(blocked_outcomes),
            active_outcome_count=len(active_outcomes),
            mastered_outcome_ratio=(
                round(len(mastered_outcomes) / len(entries), 2) if entries else 0.0
            ),
            current_outcome=current_outcome,
            next_outcome=next_outcome,
            blocked_outcomes=[
                entry.summary for entry in blocked_outcomes[:ACTIVE_OUTCOME_LIMIT]
            ],
            ready_outcomes=[
                entry.summary for entry in ready_outcomes[:ACTIVE_OUTCOME_LIMIT]
            ],
            rationale=rationale,
            updated_at=flow.updated_at or profile.updated_at,
        )

    def _outcome_entry(
        self,
        *,
        outcome: Outcome,
        components: dict[str, KnowledgeComponent],
        kc_mastery: dict[str, float],
        flow: LearnerFlowSummary,
        active_target_kc_ids: list[str],
        deferred_target_kc_ids: list[str],
        current_stage: str,
        outcome_by_id: dict[str, Outcome],
        kc_to_outcome_ids: dict[str, list[str]],
        kc_trends: dict[str, str] | None = None,
        kc_mastery_signals: dict[str, OrdinaryMasterySummary] | None = None,
        quality_gate_confidence: float = MASTERY_QUALITY_GATE_CONFIDENCE,
    ) -> OutcomePlanningEntry:
        required_kc_ids = list(outcome.knowledge_component_ids)

        # ORCH-001: Compute trend-adjusted thresholds for this outcome.
        outcome_mastery_threshold, outcome_prerequisite_threshold = (
            self._trend_adjusted_thresholds(
                kc_ids=required_kc_ids,
                components=components,
                kc_trends=kc_trends or {},
            )
        )

        mastery_ratio = self._mastery_ratio(
            kc_ids=required_kc_ids,
            kc_mastery=kc_mastery,
        )
        blocked_prerequisites = self._blocked_prerequisites(
            kc_ids=required_kc_ids,
            components=components,
            kc_mastery=kc_mastery,
            prerequisite_threshold=outcome_prerequisite_threshold,
        )
        current_flow_match_count = len(set(required_kc_ids) & set(active_target_kc_ids))
        deferred_flow_match_count = len(
            set(required_kc_ids) & set(deferred_target_kc_ids)
        )
        current_flow_aligned = current_flow_match_count > 0
        dependency_outcome_ids = self._dependency_outcome_ids(
            outcome=outcome,
            components=components,
            kc_to_outcome_ids=kc_to_outcome_ids,
        )
        # ADAPT-006: Check mastery quality — even when raw scores pass, an
        # outcome is not truly mastered if the learner's ordinary mastery
        # profile shows support_dependent or fragile signals.  The confidence
        # threshold is adjusted by quality gate outcome feedback.
        mastery_quality = self._mastery_quality(
            kc_ids=required_kc_ids,
            kc_mastery_signals=kc_mastery_signals or {},
            confidence_threshold=quality_gate_confidence,
        )

        if current_flow_aligned:
            state = "active"
            rationale = (
                flow.rationale
                or "The current learner flow is focused on this curriculum outcome."
            )
        elif self._is_mastered(
            kc_ids=required_kc_ids,
            kc_mastery=kc_mastery,
            mastery_threshold=outcome_mastery_threshold,
            prerequisite_threshold=outcome_prerequisite_threshold,
        ):
            if mastery_quality in MASTERY_QUALITY_GATE_SIGNALS:
                # Raw scores pass but evidence quality is not strong enough
                # to consider the outcome truly mastered.
                state = "ready"
                quality_label = (
                    "scaffolded"
                    if mastery_quality == "support_dependent"
                    else "unstable"
                )
                rationale = (
                    f"Mastery scores are above threshold, but recent evidence looks {quality_label}. "
                    "Demonstrate independent understanding to complete this outcome."
                )
            else:
                state = "mastered"
                rationale = "Mastery across this outcome's mapped targets is strong enough to treat it as complete."
        elif self._is_deferred_target_being_unlocked(
            flow=flow,
            blocked_prerequisites=blocked_prerequisites,
            active_target_kc_ids=active_target_kc_ids,
            deferred_flow_match_count=deferred_flow_match_count,
        ):
            state = "ready"
            blocked_labels = ", ".join(
                self._blocked_prerequisite_label(
                    kc_id=kc_id,
                    components=components,
                    kc_mastery=kc_mastery,
                )
                for kc_id in blocked_prerequisites
            )
            rationale = (
                combine_rationales(
                    (
                        f"The current learner flow is actively repairing prerequisite KCs {blocked_labels} for this outcome, "
                        "so it remains the planned next curriculum focus instead of falling behind unrelated ready work."
                    ),
                    self._deferred_target_rationale(flow=flow, outcome=outcome),
                    "The backend can move here as soon as the current learner flow releases the active target.",
                )
                or "The backend can move here as soon as the current learner flow releases the active target."
            )
        elif blocked_prerequisites:
            state = "blocked"
            blocked_labels = ", ".join(
                self._blocked_prerequisite_label(
                    kc_id=kc_id,
                    components=components,
                    kc_mastery=kc_mastery,
                )
                for kc_id in blocked_prerequisites
            )
            blocking_outcome_titles = self._blocking_outcome_titles(
                prerequisite_kc_ids=blocked_prerequisites,
                outcome_by_id=outcome_by_id,
                kc_to_outcome_ids=kc_to_outcome_ids,
                current_outcome_id=outcome.outcome_id,
            )
            rationale = (
                f"Prerequisite KCs {blocked_labels} are not yet strong enough, so this outcome stays blocked "
                "instead of becoming the next curriculum focus."
            )
            if blocking_outcome_titles:
                rationale = (
                    combine_rationales(
                        rationale,
                        f"This outcome is still waiting behind {', '.join(blocking_outcome_titles)}.",
                    )
                    or rationale
                )
        else:
            state = "ready"
            rationale = (
                combine_rationales(
                    "Prerequisites are met, so this outcome is available as the next curriculum focus.",
                    (
                        self._deferred_target_rationale(flow=flow, outcome=outcome)
                        if deferred_flow_match_count > 0
                        else None
                    ),
                    (
                        "The backend can move here as soon as the current learner flow releases the active target."
                        if flow.status != "idle"
                        else None
                    ),
                )
                or "Prerequisites are met, so this outcome is available as the next curriculum focus."
            )

        return OutcomePlanningEntry(
            summary=OutcomeProgressSummary(
                outcome_id=outcome.outcome_id,
                title=outcome.title,
                state=state,
                knowledge_component_ids=required_kc_ids,
                blocked_prerequisite_kc_ids=blocked_prerequisites,
                mastery_ratio=mastery_ratio,
                current_flow_aligned=current_flow_aligned,
                target_stage=current_stage if current_flow_aligned else "target",
                mastery_quality=mastery_quality,
                rationale=rationale,
            ),
            dependency_outcome_ids=dependency_outcome_ids,
            blocked_prerequisite_kc_ids=blocked_prerequisites,
            current_flow_match_count=current_flow_match_count,
            deferred_flow_match_count=deferred_flow_match_count,
        )

    def _kc_to_outcome_ids(self, *, outcomes: list[Outcome]) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        for outcome in outcomes:
            for kc_id in outcome.knowledge_component_ids:
                outcome_ids = index.setdefault(kc_id, [])
                if outcome.outcome_id not in outcome_ids:
                    outcome_ids.append(outcome.outcome_id)
        return index

    def _dependency_outcome_ids(
        self,
        *,
        outcome: Outcome,
        components: dict[str, KnowledgeComponent],
        kc_to_outcome_ids: dict[str, list[str]],
    ) -> list[str]:
        dependency_ids: list[str] = []
        for kc_id in outcome.knowledge_component_ids:
            component = components.get(kc_id)
            if component is None:
                continue
            for prerequisite_id in component.prerequisite_kc_ids:
                for outcome_id in kc_to_outcome_ids.get(prerequisite_id, []):
                    if (
                        outcome_id != outcome.outcome_id
                        and outcome_id not in dependency_ids
                    ):
                        dependency_ids.append(outcome_id)
        return dependency_ids

    def _outcome_depth(
        self,
        *,
        outcome_id: str,
        dependency_map: dict[str, list[str]],
        cache: dict[str, int],
        visiting: set[str],
    ) -> int:
        if outcome_id in cache:
            return cache[outcome_id]
        if outcome_id in visiting:
            return 0
        visiting.add(outcome_id)
        dependencies = dependency_map.get(outcome_id, [])
        if not dependencies:
            depth = 0
        else:
            depth = 1 + max(
                self._outcome_depth(
                    outcome_id=dependency_id,
                    dependency_map=dependency_map,
                    cache=cache,
                    visiting=visiting,
                )
                for dependency_id in dependencies
            )
        visiting.remove(outcome_id)
        cache[outcome_id] = depth
        return depth

    def _active_priority(self, entry: OutcomePlanningEntry) -> tuple[int, int, str]:
        return (-entry.current_flow_match_count, entry.depth, entry.summary.outcome_id)

    def _ready_priority(self, entry: OutcomePlanningEntry) -> tuple[int, int, int, str]:
        return (
            -entry.deferred_flow_match_count,
            entry.depth,
            len(entry.dependency_outcome_ids),
            entry.summary.outcome_id,
        )

    def _blocked_priority(self, entry: OutcomePlanningEntry) -> tuple[int, int, str]:
        return (
            len(entry.blocked_prerequisite_kc_ids),
            entry.depth,
            entry.summary.outcome_id,
        )

    def _deferred_target_kc_ids(self, *, flow: LearnerFlowSummary) -> list[str]:
        return list(
            dict.fromkeys(
                [
                    *flow.deferred_target_kc_ids,
                    *flow.transfer_target_kc_ids,
                ]
            )
        )

    def _blocked_prerequisite_label(
        self,
        *,
        kc_id: str,
        components: dict[str, KnowledgeComponent],
        kc_mastery: dict[str, float],
    ) -> str:
        component = components.get(kc_id)
        label = component.name if component is not None else kc_id
        score = float(kc_mastery.get(kc_id, 0.0))
        return f"{label} ({score:.2f}/{PREREQUISITE_READY_THRESHOLD:.2f})"

    def _blocking_outcome_titles(
        self,
        *,
        prerequisite_kc_ids: list[str],
        outcome_by_id: dict[str, Outcome],
        kc_to_outcome_ids: dict[str, list[str]],
        current_outcome_id: str,
    ) -> list[str]:
        titles: list[str] = []
        for kc_id in prerequisite_kc_ids:
            for outcome_id in kc_to_outcome_ids.get(kc_id, []):
                if outcome_id == current_outcome_id:
                    continue
                outcome = outcome_by_id.get(outcome_id)
                if outcome is None or outcome.title in titles:
                    continue
                titles.append(outcome.title)
        return titles

    def _deferred_target_rationale(
        self,
        *,
        flow: LearnerFlowSummary,
        outcome: Outcome,
    ) -> str | None:
        if flow.status == "idle":
            return None
        if flow.target_stage == "repair":
            return (
                f"This outcome is the deferred return target while the backend holds repair on the current prerequisite path "
                f"before reopening {outcome.title}."
            )
        if flow.target_stage == "bridge":
            return (
                f"This outcome is the deferred return target while the backend holds one guided bridge step "
                f"before reopening {outcome.title}."
            )
        if flow.target_stage == "transfer":
            return "This outcome is the current transfer-return target once the active flow completes."
        return None

    def _is_deferred_target_being_unlocked(
        self,
        *,
        flow: LearnerFlowSummary,
        blocked_prerequisites: list[str],
        active_target_kc_ids: list[str],
        deferred_flow_match_count: int,
    ) -> bool:
        if deferred_flow_match_count <= 0 or not blocked_prerequisites:
            return False
        if flow.target_stage not in {"repair", "bridge"}:
            return False
        return set(blocked_prerequisites).issubset(set(active_target_kc_ids))

    def _blocked_prerequisites(
        self,
        *,
        kc_ids: list[str],
        components: dict[str, KnowledgeComponent],
        kc_mastery: dict[str, float],
        prerequisite_threshold: float = PREREQUISITE_READY_THRESHOLD,
    ) -> list[str]:
        blocked: list[str] = []
        for kc_id in kc_ids:
            component = components.get(kc_id)
            if component is None:
                continue
            for prerequisite_id in component.prerequisite_kc_ids:
                if float(kc_mastery.get(prerequisite_id, 0.0)) < prerequisite_threshold:
                    blocked.append(prerequisite_id)
        return list(dict.fromkeys(blocked))

    def _is_mastered(
        self,
        *,
        kc_ids: list[str],
        kc_mastery: dict[str, float],
        mastery_threshold: float = MASTERY_THRESHOLD,
        prerequisite_threshold: float = PREREQUISITE_READY_THRESHOLD,
    ) -> bool:
        if not kc_ids:
            return False
        scores = [float(kc_mastery.get(kc_id, 0.0)) for kc_id in kc_ids]
        return (
            bool(scores)
            and min(scores) >= prerequisite_threshold
            and sum(scores) / len(scores) >= mastery_threshold
        )

    def _mastery_ratio(
        self,
        *,
        kc_ids: list[str],
        kc_mastery: dict[str, float],
    ) -> float:
        scores = [float(kc_mastery.get(kc_id, 0.0)) for kc_id in kc_ids]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 2)

    # --- ORCH-001 + ADAPT-006: Mastery profile helpers ---

    def _effective_quality_gate_confidence(self, *, student_id: UUID) -> float:
        """Return the quality gate confidence threshold, adjusted by outcome
        feedback when available.

        ADAPT-006: The quality gate signal service aggregates recent gate
        outcomes and produces a bounded confidence adjustment.  A positive
        adjustment means the gate has been too aggressive (raise threshold to
        gate less), a negative adjustment means the gate has been helping
        (lower threshold to gate more readily).
        """
        base = MASTERY_QUALITY_GATE_CONFIDENCE
        if self.quality_gate_signal_service is None:
            return base
        try:
            signal = self.quality_gate_signal_service.signal_for_student(
                student_id=student_id
            )
            return max(0.15, min(0.7, base + signal.confidence_threshold_adjustment))
        except Exception:
            return base

    def _kc_mastery_profiles(
        self,
        *,
        student_id: UUID,
        components: dict[str, KnowledgeComponent],
    ) -> tuple[dict[str, str], dict[str, OrdinaryMasterySummary]]:
        """Return ({kc_id: trend}, {kc_id: OrdinaryMasterySummary}) for all KCs
        that have ordinary mastery profiles.  The trend dict is the same format
        used by _trend_adjusted_thresholds; the signal dict is used by the
        ADAPT-006 mastery quality gate."""
        if self.ordinary_mastery_signal_service is None:
            return {}, {}
        trends: dict[str, str] = {}
        signals: dict[str, OrdinaryMasterySummary] = {}
        for kc_id in components:
            summary: OrdinaryMasterySummary = (
                self.ordinary_mastery_signal_service.latest_for_student(
                    student_id=student_id,
                    target_kc_ids=[kc_id],
                    target_lo_ids=[],
                )
            )
            if summary.signal != "insufficient":
                signals[kc_id] = summary
                if summary.mastery_trend != "stable":
                    trends[kc_id] = summary.mastery_trend
        return trends, signals

    def _mastery_quality(
        self,
        *,
        kc_ids: list[str],
        kc_mastery_signals: dict[str, OrdinaryMasterySummary],
        confidence_threshold: float = MASTERY_QUALITY_GATE_CONFIDENCE,
    ) -> str | None:
        """Return the worst mastery quality signal across an outcome's KCs,
        or None if all KCs are healthy or have insufficient data.

        ADAPT-006: An outcome is not truly mastered if any required KC shows
        support_dependent or fragile evidence with sufficient confidence.
        The confidence threshold is adjusted by quality gate outcome feedback
        when available."""
        worst: str | None = None
        for kc_id in kc_ids:
            summary = kc_mastery_signals.get(kc_id)
            if summary is None:
                continue
            if (
                summary.signal in MASTERY_QUALITY_GATE_SIGNALS
                and summary.confidence >= confidence_threshold
            ):
                if summary.signal == "support_dependent":
                    return "support_dependent"
                worst = summary.signal
        return worst

    def _trend_adjusted_thresholds(
        self,
        *,
        kc_ids: list[str],
        components: dict[str, KnowledgeComponent],
        kc_trends: dict[str, str],
    ) -> tuple[float, float]:
        """Return (mastery_threshold, prerequisite_threshold) adjusted for trend signals.

        The adjustment is based on the dominant trend across the outcome's
        required KCs and their prerequisites.  If more KCs are improving than
        declining, thresholds ease; if more are declining, thresholds tighten.
        """
        if not kc_trends:
            return MASTERY_THRESHOLD, PREREQUISITE_READY_THRESHOLD

        # Collect trends for this outcome's KCs and their prerequisites.
        relevant_kc_ids = set(kc_ids)
        for kc_id in kc_ids:
            component = components.get(kc_id)
            if component is not None:
                relevant_kc_ids.update(component.prerequisite_kc_ids)

        improving = sum(
            1 for kc_id in relevant_kc_ids if kc_trends.get(kc_id) == "improving"
        )
        declining = sum(
            1 for kc_id in relevant_kc_ids if kc_trends.get(kc_id) == "declining"
        )

        if improving == 0 and declining == 0:
            return MASTERY_THRESHOLD, PREREQUISITE_READY_THRESHOLD

        mastery_threshold = MASTERY_THRESHOLD
        prerequisite_threshold = PREREQUISITE_READY_THRESHOLD

        if improving > declining:
            mastery_threshold -= TREND_MASTERY_BONUS
            prerequisite_threshold -= TREND_PREREQUISITE_BONUS
        elif declining > improving:
            mastery_threshold += TREND_MASTERY_PENALTY
            prerequisite_threshold += TREND_PREREQUISITE_PENALTY

        return mastery_threshold, prerequisite_threshold
