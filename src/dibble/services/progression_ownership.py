from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from dibble.models.generation import (
    ContentIntent,
    GenerationRequest,
    RequestedContentType,
)
from dibble.models.profile import OrdinaryMasterySummary
from dibble.services.kc_sequence_planner import KcSequencePlanner
from dibble.services.observation_profile_update import ObservationProfileUpdater
from dibble.services.progression_outcome_signals import (
    ProgressionOutcomeSignal,
    ProgressionOutcomeSignalService,
)
from dibble.services.protocols import (
    AuditStore,
    KnowledgeComponentStore,
    ObservationStore,
)
from dibble.services.workflow_rationale import append_evidence_snapshot


@dataclass(frozen=True, slots=True)
class ProgressionOwnershipDecision:
    request: GenerationRequest
    action: str = "stay_on_requested_target"
    source: str = "requested_target"
    target_stage: str = "target"
    target_redirect_applied: bool = False
    requested_target_kc_ids: list[str] = field(default_factory=list)
    applied_target_kc_ids: list[str] = field(default_factory=list)
    transfer_target_kc_ids: list[str] = field(default_factory=list)
    deferred_target_kc_ids: list[str] = field(default_factory=list)
    bridge_kc_ids: list[str] = field(default_factory=list)
    rationale: str | None = None
    evidence_observation_count: int = 0
    evidence_assessment_count: int = 0
    evidence_confidence: float = 0.0
    average_observed_mastery: float | None = None
    average_assessment_mastery: float | None = None
    ordinary_mastery_signal: str = "insufficient"
    ordinary_mastery_source: str = "insufficient"
    ordinary_mastery_confidence: float = 0.0
    ordinary_mastery_average_observed_mastery: float | None = None
    ordinary_mastery_rationale: str | None = None
    requested_content_type: str | None = None
    applied_content_type: str | None = None
    mastery_gate_applied: bool = False
    mastery_gate_reason: str | None = None


@dataclass(frozen=True, slots=True)
class OrdinaryProgressionDecision:
    decision: str = "monitor"
    rationale: str | None = None
    summary: OrdinaryMasterySummary = field(default_factory=OrdinaryMasterySummary)


@dataclass(slots=True)
class ProgressionOwnershipService:
    knowledge_component_store: KnowledgeComponentStore
    strategy_signal_service: object
    within_session_adaptation_service: object
    observation_store: ObservationStore | None = None
    audit_store: AuditStore | None = None
    observation_profile_updater: ObservationProfileUpdater | None = None
    ordinary_mastery_signal_service: object | None = None
    progression_outcome_signal_service: ProgressionOutcomeSignalService | None = None
    kc_sequence_planner: KcSequencePlanner | None = None

    def __post_init__(self) -> None:
        if self.kc_sequence_planner is None:
            self.kc_sequence_planner = KcSequencePlanner(
                knowledge_component_store=self.knowledge_component_store
            )

    def resolve_request(
        self, *, student_id: UUID, request: GenerationRequest
    ) -> ProgressionOwnershipDecision:
        requested_target_kc_ids = list(request.target_kc_ids)
        if not requested_target_kc_ids:
            return ProgressionOwnershipDecision(
                request=request,
                requested_target_kc_ids=[],
                applied_target_kc_ids=[],
            )

        strategy = self.strategy_signal_service.strategy_for(
            student_id=student_id, request=request
        )
        session = self.within_session_adaptation_service.adaptation_for(
            student_id=student_id, request=request
        )
        prerequisite_kc_ids = self._prerequisite_kc_ids(requested_target_kc_ids)
        sequence = self.kc_sequence_planner.plan(
            strategy_summary=strategy,
            target_kc_ids=requested_target_kc_ids,
            prerequisite_kc_ids=prerequisite_kc_ids,
        )
        transfer_target_kc_ids = list(
            sequence.deferred_kc_ids or requested_target_kc_ids
        )

        action = "stay_on_requested_target"
        source = "requested_target"
        target_stage = "target"
        applied_target_kc_ids = list(requested_target_kc_ids)
        rationale = None
        requested_content_type = (
            request.requested_content_type.value
            if request.requested_content_type is not None
            else None
        )
        applied_request = request
        mastery_gate_applied = False
        mastery_gate_reason = None

        if (
            session.phase == "bridge" or session.recovery_intent == "bridge_target"
        ) and sequence.bridge_kc_ids:
            action = (
                "hold_bridge_target"
                if session.sequence_action == "hold_bridge_target"
                else "bridge_to_related_kc"
            )
            source = session.source
            target_stage = "bridge"
            applied_target_kc_ids = [sequence.bridge_kc_ids[0]]
            rationale = session.rationale or sequence.rationale
        elif (
            session.sequence_action == "hold_repair_target"
            and sequence.primary_kc_id is not None
            and sequence.primary_kc_id not in requested_target_kc_ids
        ):
            action = "hold_repair_target"
            source = session.source
            target_stage = "repair"
            applied_target_kc_ids = [sequence.primary_kc_id]
            rationale = session.rationale or sequence.rationale
        elif (
            sequence.action == "rebuild_prerequisite_first"
            and sequence.primary_kc_id is not None
            and sequence.primary_kc_id not in requested_target_kc_ids
        ):
            action = sequence.action
            source = "strategy_profile"
            target_stage = "repair"
            applied_target_kc_ids = [sequence.primary_kc_id]
            rationale = sequence.rationale
        elif sequence.action == "hold_target" and strategy.source != "insufficient":
            action = "hold_target"
            source = "strategy_profile"
            target_stage = "target"
            rationale = sequence.rationale

        stage_request = request.model_copy(
            update={
                "target_kc_ids": applied_target_kc_ids,
                "target_lo_ids": self._target_lo_ids(applied_target_kc_ids)
                or request.target_lo_ids,
            }
        )
        evidence_decision = self._evidence_decision(
            student_id=student_id,
            request=stage_request,
            session_summary=session,
        )
        outcome_signal = self._outcome_signal(
            student_id=student_id,
            target_kc_ids=applied_target_kc_ids,
        )
        ordinary_mastery_decision = self._ordinary_mastery_decision(
            student_id=student_id,
            request=stage_request,
            current_action=action,
            target_stage=target_stage,
            outcome_signal=outcome_signal,
        )
        bridge_hold_active = action == "hold_bridge_target"
        if (
            self._should_prefer_transfer(
                evidence_decision=evidence_decision,
                outcome_signal=outcome_signal,
            )
            and not bridge_hold_active
        ):
            action = "attempt_transfer"
            source = "progression_evidence"
            target_stage = "transfer"
            applied_target_kc_ids = list(
                transfer_target_kc_ids or requested_target_kc_ids
            )
            rationale = self._transfer_rationale(
                request=stage_request,
                transfer_target_kc_ids=applied_target_kc_ids,
                evidence_decision=evidence_decision,
            )
        elif evidence_decision.decision != "monitor" and not (
            bridge_hold_active and evidence_decision.decision == "attempt_transfer"
        ):
            action = evidence_decision.decision
            source = "progression_evidence"
            target_stage = self._target_stage_for_action(
                action=action, fallback=target_stage
            )
            rationale = self._append_progression_evidence_snapshot(
                evidence_decision.rationale
                or "Recent same-session progression evidence suggests holding the current stage target.",
                evidence_decision=evidence_decision,
            )
        elif ordinary_mastery_decision.decision != "monitor":
            action = ordinary_mastery_decision.decision
            source = "ordinary_mastery_profile"
            target_stage = self._target_stage_for_action(
                action=action, fallback=target_stage
            )
            rationale = ordinary_mastery_decision.rationale

        applied_request, mastery_gate_action, mastery_gate_reason = (
            self._apply_mastery_gate(
                request=applied_request.model_copy(
                    update={
                        "target_kc_ids": applied_target_kc_ids,
                        "target_lo_ids": self._target_lo_ids(applied_target_kc_ids)
                        or request.target_lo_ids,
                    }
                ),
                action=action,
                target_stage=target_stage,
                rationale=rationale or sequence.rationale,
            )
        )
        if mastery_gate_action is not None:
            action = mastery_gate_action
            source = "mastery_gate"
            mastery_gate_applied = True

        applied_content_type = (
            applied_request.requested_content_type.value
            if applied_request.requested_content_type is not None
            else None
        )
        target_redirect_applied = applied_target_kc_ids != requested_target_kc_ids

        if applied_target_kc_ids == requested_target_kc_ids:
            return ProgressionOwnershipDecision(
                request=applied_request,
                action=action,
                source=source,
                target_stage=target_stage,
                target_redirect_applied=target_redirect_applied,
                requested_target_kc_ids=requested_target_kc_ids,
                applied_target_kc_ids=applied_target_kc_ids,
                transfer_target_kc_ids=transfer_target_kc_ids,
                deferred_target_kc_ids=sequence.deferred_kc_ids,
                bridge_kc_ids=sequence.bridge_kc_ids,
                rationale=rationale or sequence.rationale,
                evidence_observation_count=evidence_decision.matched_observation_count,
                evidence_assessment_count=evidence_decision.matched_assessment_count,
                evidence_confidence=evidence_decision.confidence,
                average_observed_mastery=evidence_decision.average_observed_mastery,
                average_assessment_mastery=evidence_decision.average_assessment_mastery,
                ordinary_mastery_signal=ordinary_mastery_decision.summary.signal,
                ordinary_mastery_source=ordinary_mastery_decision.summary.source,
                ordinary_mastery_confidence=ordinary_mastery_decision.summary.confidence,
                ordinary_mastery_average_observed_mastery=ordinary_mastery_decision.summary.average_observed_mastery,
                ordinary_mastery_rationale=ordinary_mastery_decision.summary.rationale,
                requested_content_type=requested_content_type,
                applied_content_type=applied_content_type,
                mastery_gate_applied=mastery_gate_applied,
                mastery_gate_reason=mastery_gate_reason,
            )

        updated_request = applied_request.model_copy(
            update={
                "curriculum_context": [
                    *applied_request.curriculum_context,
                    f"Progression ownership: {action}.",
                    mastery_gate_reason
                    or rationale
                    or sequence.rationale
                    or "Stay on the current repair path before advancing.",
                ],
            }
        )
        return ProgressionOwnershipDecision(
            request=updated_request,
            action=action,
            source=source,
            target_stage=target_stage,
            target_redirect_applied=target_redirect_applied,
            requested_target_kc_ids=requested_target_kc_ids,
            applied_target_kc_ids=applied_target_kc_ids,
            transfer_target_kc_ids=transfer_target_kc_ids,
            deferred_target_kc_ids=sequence.deferred_kc_ids,
            bridge_kc_ids=sequence.bridge_kc_ids,
            rationale=rationale or sequence.rationale,
            evidence_observation_count=evidence_decision.matched_observation_count,
            evidence_assessment_count=evidence_decision.matched_assessment_count,
            evidence_confidence=evidence_decision.confidence,
            average_observed_mastery=evidence_decision.average_observed_mastery,
            average_assessment_mastery=evidence_decision.average_assessment_mastery,
            ordinary_mastery_signal=ordinary_mastery_decision.summary.signal,
            ordinary_mastery_source=ordinary_mastery_decision.summary.source,
            ordinary_mastery_confidence=ordinary_mastery_decision.summary.confidence,
            ordinary_mastery_average_observed_mastery=ordinary_mastery_decision.summary.average_observed_mastery,
            ordinary_mastery_rationale=ordinary_mastery_decision.summary.rationale,
            requested_content_type=requested_content_type,
            applied_content_type=applied_content_type,
            mastery_gate_applied=mastery_gate_applied,
            mastery_gate_reason=mastery_gate_reason,
        )

    def _prerequisite_kc_ids(self, target_kc_ids: list[str]) -> list[str]:
        prerequisites: list[str] = []
        for kc_id in target_kc_ids:
            component = self.knowledge_component_store.get(kc_id)
            if component is None:
                continue
            for prerequisite_kc_id in component.prerequisite_kc_ids:
                if prerequisite_kc_id not in prerequisites:
                    prerequisites.append(prerequisite_kc_id)
        return prerequisites

    def _target_lo_ids(self, target_kc_ids: list[str]) -> list[str]:
        lo_ids: list[str] = []
        for kc_id in target_kc_ids:
            component = self.knowledge_component_store.get(kc_id)
            if component is None or component.parent_lo_id in lo_ids:
                continue
            lo_ids.append(component.parent_lo_id)
        return lo_ids

    def _evidence_decision(
        self, *, student_id: UUID, request: GenerationRequest, session_summary
    ):
        if (
            self.observation_store is None
            or self.audit_store is None
            or self.observation_profile_updater is None
        ):
            from dibble.services.observation_profile_update import (
                ProgressionEvidenceDecision,
            )

            return ProgressionEvidenceDecision()
        observations = self.observation_store.list_recent(student_id=str(student_id))
        assessment_payloads = [
            event.payload
            for event in self.audit_store.list(limit=200)
            if event.student_id is not None
            and str(event.student_id) == str(student_id)
            and event.event_type == "assessment.socratic"
        ]
        return self.observation_profile_updater.evaluate_progression_evidence(
            request=request,
            observations=observations,
            assessment_payloads=assessment_payloads,
            session_sequence_action=session_summary.sequence_action,
            session_rationale=session_summary.rationale,
        )

    def _outcome_signal(
        self,
        *,
        student_id: UUID,
        target_kc_ids: list[str],
    ) -> ProgressionOutcomeSignal:
        if self.progression_outcome_signal_service is None:
            return ProgressionOutcomeSignal()
        return self.progression_outcome_signal_service.signal_for_student(
            student_id=student_id,
            target_kc_ids=target_kc_ids or None,
        )

    def _ordinary_mastery_decision(
        self,
        *,
        student_id: UUID,
        request: GenerationRequest,
        current_action: str,
        target_stage: str,
        outcome_signal: ProgressionOutcomeSignal | None = None,
    ) -> OrdinaryProgressionDecision:
        if self.ordinary_mastery_signal_service is None:
            return OrdinaryProgressionDecision()
        if target_stage not in {"target", "repair"}:
            return OrdinaryProgressionDecision()
        if not request.target_kc_ids and not request.target_lo_ids:
            return OrdinaryProgressionDecision()
        if current_action not in {
            "stay_on_requested_target",
            "hold_target",
            "attempt_transfer",
            "rebuild_prerequisite_first",
            "hold_repair_target",
        }:
            return OrdinaryProgressionDecision()
        summary = self.ordinary_mastery_signal_service.latest_for_student(
            student_id=student_id,
            target_kc_ids=request.target_kc_ids,
            target_lo_ids=request.target_lo_ids,
        )
        hold_action = self._ordinary_mastery_hold_action(target_stage=target_stage)
        if hold_action is None:
            return OrdinaryProgressionDecision(summary=summary)

        # ADAPT-006: Repair targets use lower confidence thresholds because
        # the learner is explicitly in a remediation arc and should be held
        # more cautiously — releasing too early risks the same misconception
        # resurfacing on the original target.
        support_dependent_threshold = 0.45 if target_stage == "repair" else 0.55
        fragile_threshold = 0.55 if target_stage == "repair" else 0.65

        # ADAPT-006: If the learner has a genuinely high low-support success
        # rate despite the aggregate signal still reading support_dependent or
        # fragile, the hold is less warranted — the learner is demonstrating
        # growing independence even if the overall average is still shaky.
        # Conversely, a very high support-dependency rate tightens the hold so
        # borderline cases are not released prematurely.
        #
        # The bonus/penalty is scaled by evidence depth so sparse observation
        # windows don't earn the full adjustment.  A learner with only 1–2
        # observations shouldn't get the same threshold shift as one with 6+.
        effective_support_dependent_threshold = support_dependent_threshold
        effective_fragile_threshold = fragile_threshold
        evidence_scale = min(1.0, summary.matched_observation_count / 4)
        if summary.low_support_success_rate >= 0.5:
            scaled_bonus = 0.08 * evidence_scale
            effective_support_dependent_threshold += scaled_bonus
            effective_fragile_threshold += scaled_bonus
        if summary.high_support_dependency_rate >= 0.7:
            scaled_penalty = 0.06 * evidence_scale
            effective_support_dependent_threshold = max(
                effective_support_dependent_threshold - scaled_penalty,
                support_dependent_threshold - scaled_penalty,
            )
            effective_fragile_threshold = max(
                effective_fragile_threshold - scaled_penalty,
                fragile_threshold - scaled_penalty,
            )

        # ADAPT-006: Mastery trend adjusts hold aggressiveness.  An improving
        # learner is gaining ground, so the hold threshold rises (harder to
        # trigger a hold — give the learner room to continue improving).
        # A declining learner is losing ground, so the threshold drops (easier
        # to trigger — hold them before they fall further).
        if summary.mastery_trend == "improving":
            effective_support_dependent_threshold += 0.06
            effective_fragile_threshold += 0.06
        elif summary.mastery_trend == "declining":
            effective_support_dependent_threshold -= 0.05
            effective_fragile_threshold -= 0.05

        # DATA-004 + ORCH-001: High mastery volatility means the aggregate
        # signal is less trustworthy — the learner's mastery swings enough
        # that an average score could mask real struggle.  Lower the hold
        # threshold so the system errs on the side of caution.
        if summary.mastery_volatility >= 0.18:
            # Highly volatile: strong penalty — hold more aggressively.
            volatility_penalty = 0.07 * evidence_scale
            effective_support_dependent_threshold -= volatility_penalty
            effective_fragile_threshold -= volatility_penalty
        elif summary.mastery_volatility >= 0.12:
            # Meaningfully unstable: moderate penalty.
            volatility_penalty = 0.04 * evidence_scale
            effective_support_dependent_threshold -= volatility_penalty
            effective_fragile_threshold -= volatility_penalty

        # ADAPT-006 + DATA-004: Outcome-based threshold adjustment.
        # If prior hold decisions for this learner have mostly failed (negative
        # outcomes), raise the threshold so holds are harder to trigger.
        # If holds have been reliably positive, lower it to hold more easily.
        if (
            outcome_signal is not None
            and outcome_signal.hold_threshold_adjustment != 0.0
        ):
            effective_support_dependent_threshold += (
                outcome_signal.hold_threshold_adjustment
            )
            effective_fragile_threshold += outcome_signal.hold_threshold_adjustment

        if (
            summary.signal == "support_dependent"
            and summary.confidence >= effective_support_dependent_threshold
        ):
            return OrdinaryProgressionDecision(
                decision=hold_action,
                rationale=self._ordinary_mastery_hold_rationale(
                    target_stage=target_stage,
                    signal=summary.signal,
                    fallback=(
                        "Cross-session ordinary practice still looks support-dependent, so the backend should keep the learner on target practice."
                        if target_stage == "target"
                        else "Cross-session ordinary practice on the repair target still looks support-dependent, so the backend should hold repair before returning to the target."
                    ),
                    summary=summary,
                ),
                summary=summary,
            )
        if (
            summary.signal == "fragile"
            and summary.confidence >= effective_fragile_threshold
        ):
            return OrdinaryProgressionDecision(
                decision=hold_action,
                rationale=self._ordinary_mastery_hold_rationale(
                    target_stage=target_stage,
                    signal=summary.signal,
                    fallback=(
                        "Cross-session ordinary practice still looks fragile, so the backend should keep the learner on target practice."
                        if target_stage == "target"
                        else "Cross-session ordinary practice on the repair target still looks fragile, so the backend should hold repair before returning to the target."
                    ),
                    summary=summary,
                ),
                summary=summary,
            )
        if (
            current_action == "attempt_transfer"
            and summary.signal == "emerging_mastery"
            and summary.confidence >= 0.7
        ):
            return OrdinaryProgressionDecision(
                decision=hold_action,
                rationale=self._ordinary_mastery_hold_rationale(
                    target_stage=target_stage,
                    signal=summary.signal,
                    fallback=(
                        "Cross-session ordinary practice is improving but not yet durable enough to skip target practice."
                        if target_stage == "target"
                        else "Cross-session ordinary practice on the repair target is improving but not yet durable enough to return to the target."
                    ),
                    summary=summary,
                ),
                summary=summary,
            )
        return OrdinaryProgressionDecision(summary=summary)

    def _apply_mastery_gate(
        self,
        *,
        request: GenerationRequest,
        action: str,
        target_stage: str,
        rationale: str | None,
    ) -> tuple[GenerationRequest, str | None, str | None]:
        assessment_requested = request.intent.value == "assessment" or (
            request.requested_content_type == RequestedContentType.assessment_probe
        )
        if not assessment_requested or not self._should_gate_assessment(
            action=action, target_stage=target_stage
        ):
            return request, None, None
        gate_reason = rationale or self._default_mastery_gate_reason(
            target_stage=target_stage
        )
        gate_action = self._mastery_gate_action(
            action=action, target_stage=target_stage
        )
        return (
            request.model_copy(
                update={
                    "intent": ContentIntent.practice,
                    "requested_content_type": RequestedContentType.practice_problem,
                    "curriculum_context": [
                        *request.curriculum_context,
                        f"Mastery gate: {gate_action.replace('_', ' ')}.",
                        gate_reason,
                    ],
                }
            ),
            gate_action,
            gate_reason,
        )

    def _should_prefer_transfer(
        self,
        *,
        evidence_decision,
        outcome_signal: ProgressionOutcomeSignal | None = None,
    ) -> bool:
        # ADAPT-006: Outcome-based transfer confidence adjustment.
        # If prior transfers have been premature, require more confidence.
        # If they've been reliably succeeding, lower the bar slightly.
        transfer_threshold = 0.6
        if outcome_signal is not None:
            transfer_threshold += outcome_signal.transfer_confidence_adjustment
        return (
            evidence_decision.decision == "attempt_transfer"
            and evidence_decision.confidence >= transfer_threshold
        )

    def _transfer_rationale(
        self,
        *,
        request: GenerationRequest,
        transfer_target_kc_ids: list[str],
        evidence_decision,
    ) -> str:
        target_fragment = (
            ", ".join(transfer_target_kc_ids)
            if transfer_target_kc_ids
            else "the target KC"
        )
        return self._append_progression_evidence_snapshot(
            evidence_decision.rationale
            or f"Recent same-session evidence on {request.learning_session_id} was strong enough to resume transfer on {target_fragment}.",
            evidence_decision=evidence_decision,
        )

    def _should_gate_assessment(self, *, action: str, target_stage: str) -> bool:
        if target_stage in {"repair", "bridge"}:
            return True
        return action in {"hold_target", "hold_repair_target"}

    def _mastery_gate_action(self, *, action: str, target_stage: str) -> str:
        if target_stage == "bridge":
            return "bridge_before_assessment"
        if action == "hold_repair_target":
            return "hold_repair_target_before_assessment"
        if action == "rebuild_prerequisite_first" or target_stage == "repair":
            return "rebuild_prerequisite_before_assessment"
        return "hold_target_before_assessment"

    def _default_mastery_gate_reason(self, *, target_stage: str) -> str:
        if target_stage == "bridge":
            return "Recent same-session recovery still needs a guided bridge step before a transfer-style assessment."
        if target_stage == "repair":
            return "Recent same-session evidence still suggests rebuilding the prerequisite or repair target before assessment."
        return "Recent same-session evidence still suggests the learner should stay on target practice before a transfer-style assessment."

    def _target_stage_for_action(self, *, action: str, fallback: str) -> str:
        if action == "hold_bridge_target":
            return "bridge"
        if action in {
            "hold_repair_target",
            "rebuild_prerequisite_first",
            "rebuild_prerequisite_before_assessment",
            "hold_repair_target_before_assessment",
        }:
            return "repair"
        if action in {"attempt_transfer"}:
            return "transfer"
        return fallback

    def _ordinary_mastery_hold_action(self, *, target_stage: str) -> str | None:
        if target_stage == "target":
            return "hold_target"
        if target_stage == "repair":
            return "hold_repair_target"
        return None

    def _ordinary_mastery_hold_rationale(
        self,
        *,
        target_stage: str,
        signal: str,
        fallback: str,
        summary: OrdinaryMasterySummary,
    ) -> str:
        if summary.rationale:
            if target_stage == "target":
                if signal == "support_dependent":
                    return self._append_ordinary_mastery_snapshot(
                        (
                            f"{summary.rationale} Keep the learner on target practice instead of assigning a transfer check yet."
                        ),
                        summary=summary,
                    )
                if signal == "fragile":
                    return self._append_ordinary_mastery_snapshot(
                        (
                            f"{summary.rationale} Keep the learner on target practice until the ordinary evidence is less fragile."
                        ),
                        summary=summary,
                    )
                if signal == "emerging_mastery":
                    return self._append_ordinary_mastery_snapshot(
                        (
                            f"{summary.rationale} Keep the learner on target practice until the ordinary evidence looks more durable."
                        ),
                        summary=summary,
                    )
            if target_stage == "repair":
                if signal == "support_dependent":
                    return self._append_ordinary_mastery_snapshot(
                        (
                            f"{summary.rationale} Keep the learner on the repair target instead of returning to the target KC yet."
                        ),
                        summary=summary,
                    )
                if signal == "fragile":
                    return self._append_ordinary_mastery_snapshot(
                        (
                            f"{summary.rationale} Keep the learner on the repair target until the repair evidence is less fragile."
                        ),
                        summary=summary,
                    )
                if signal == "emerging_mastery":
                    return self._append_ordinary_mastery_snapshot(
                        (
                            f"{summary.rationale} Keep the learner on the repair target until the progress looks more durable."
                        ),
                        summary=summary,
                    )
            return self._append_ordinary_mastery_snapshot(
                summary.rationale, summary=summary
            )
        return self._append_ordinary_mastery_snapshot(fallback, summary=summary)

    def _append_ordinary_mastery_snapshot(
        self,
        rationale: str,
        *,
        summary: OrdinaryMasterySummary,
    ) -> str:
        fragments = [
            f"Ordinary mastery signal {summary.signal} at {summary.confidence:.2f} confidence"
        ]
        if summary.average_observed_mastery is not None:
            fragments.append(
                f"average observed mastery {summary.average_observed_mastery:.2f}"
            )
        if summary.mastery_trend != "stable":
            fragments.append(f"trend {summary.mastery_trend}")
        if summary.mastery_volatility >= 0.12:
            fragments.append(f"volatility {summary.mastery_volatility:.2f}")
        if summary.low_support_success_rate > 0.0:
            fragments.append(
                f"low-support success rate {summary.low_support_success_rate:.2f}"
            )
        if summary.high_support_dependency_rate > 0.0:
            fragments.append(
                f"high-support dependency rate {summary.high_support_dependency_rate:.2f}"
            )
        if summary.matched_observation_count > 0:
            fragments.append(
                f"{summary.matched_observation_count} matched observation(s)"
            )
        if summary.matched_session_count >= 2:
            fragments.append(f"across {summary.matched_session_count} sessions")
        # ADAPT-006: Surface stuck-repair context when a learner has many
        # observations without improving past support_dependent or fragile.
        # A declining trend triggers the stuck signal earlier (4 obs / 2 sessions)
        # because the learner is actively losing ground.
        if summary.signal in {"support_dependent", "fragile"}:
            stuck_observation_threshold = (
                4 if summary.mastery_trend == "declining" else 6
            )
            stuck_session_threshold = 2 if summary.mastery_trend == "declining" else 3
            if (
                summary.matched_observation_count >= stuck_observation_threshold
                and summary.matched_session_count >= stuck_session_threshold
            ):
                if summary.mastery_trend == "declining":
                    fragments.append("declining hold — consider teacher review")
                else:
                    fragments.append("extended hold — consider teacher review")
        return append_evidence_snapshot(rationale, fragments=fragments) or rationale

    def _append_progression_evidence_snapshot(
        self,
        rationale: str,
        *,
        evidence_decision,
    ) -> str:
        fragments = [
            f"Same-session evidence confidence {evidence_decision.confidence:.2f}"
        ]
        if evidence_decision.matched_observation_count > 0:
            fragments.append(
                f"{evidence_decision.matched_observation_count} observation(s)"
            )
        if evidence_decision.matched_assessment_count > 0:
            fragments.append(
                f"{evidence_decision.matched_assessment_count} assessment(s)"
            )
        if evidence_decision.average_observed_mastery is not None:
            fragments.append(
                f"average observed mastery {evidence_decision.average_observed_mastery:.2f}"
            )
        if evidence_decision.average_assessment_mastery is not None:
            fragments.append(
                f"average assessment mastery {evidence_decision.average_assessment_mastery:.2f}"
            )
        return append_evidence_snapshot(rationale, fragments=fragments) or rationale
