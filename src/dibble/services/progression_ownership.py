from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from dibble.models.generation import ContentIntent, GenerationRequest, RequestedContentType
from dibble.services.kc_sequence_planner import KcSequencePlanner
from dibble.services.observation_profile_update import ObservationProfileUpdater
from dibble.services.protocols import AuditStore, KnowledgeComponentStore, ObservationStore


@dataclass(frozen=True, slots=True)
class ProgressionOwnershipDecision:
    request: GenerationRequest
    action: str = "stay_on_requested_target"
    source: str = "requested_target"
    requested_target_kc_ids: list[str] = field(default_factory=list)
    applied_target_kc_ids: list[str] = field(default_factory=list)
    deferred_target_kc_ids: list[str] = field(default_factory=list)
    bridge_kc_ids: list[str] = field(default_factory=list)
    rationale: str | None = None
    evidence_observation_count: int = 0
    evidence_assessment_count: int = 0
    evidence_confidence: float = 0.0
    average_observed_mastery: float | None = None
    average_assessment_mastery: float | None = None
    requested_content_type: str | None = None
    applied_content_type: str | None = None
    mastery_gate_applied: bool = False
    mastery_gate_reason: str | None = None


@dataclass(slots=True)
class ProgressionOwnershipService:
    knowledge_component_store: KnowledgeComponentStore
    strategy_signal_service: object
    within_session_adaptation_service: object
    observation_store: ObservationStore | None = None
    audit_store: AuditStore | None = None
    observation_profile_updater: ObservationProfileUpdater | None = None
    kc_sequence_planner: KcSequencePlanner | None = None

    def __post_init__(self) -> None:
        if self.kc_sequence_planner is None:
            self.kc_sequence_planner = KcSequencePlanner(knowledge_component_store=self.knowledge_component_store)

    def resolve_request(self, *, student_id: UUID, request: GenerationRequest) -> ProgressionOwnershipDecision:
        requested_target_kc_ids = list(request.target_kc_ids)
        if not requested_target_kc_ids:
            return ProgressionOwnershipDecision(
                request=request,
                requested_target_kc_ids=[],
                applied_target_kc_ids=[],
            )

        strategy = self.strategy_signal_service.strategy_for(student_id=student_id, request=request)
        session = self.within_session_adaptation_service.adaptation_for(student_id=student_id, request=request)
        prerequisite_kc_ids = self._prerequisite_kc_ids(requested_target_kc_ids)
        sequence = self.kc_sequence_planner.plan(
            strategy_summary=strategy,
            target_kc_ids=requested_target_kc_ids,
            prerequisite_kc_ids=prerequisite_kc_ids,
        )
        evidence_decision = self._evidence_decision(
            student_id=student_id,
            request=request,
            session_summary=session,
        )

        action = "stay_on_requested_target"
        source = "requested_target"
        applied_target_kc_ids = list(requested_target_kc_ids)
        rationale = None
        requested_content_type = (
            request.requested_content_type.value if request.requested_content_type is not None else None
        )
        applied_request = request
        mastery_gate_applied = False
        mastery_gate_reason = None

        if (
            session.phase == "bridge" or session.recovery_intent == "bridge_target"
        ) and sequence.bridge_kc_ids:
            action = "bridge_to_related_kc"
            source = session.source
            applied_target_kc_ids = [sequence.bridge_kc_ids[0]]
            rationale = session.rationale or (
                "Recent same-session recovery suggests bridging through a nearby KC before returning fully to the target."
            )
        elif (
            session.sequence_action == "hold_repair_target"
            and sequence.primary_kc_id is not None
            and sequence.primary_kc_id not in requested_target_kc_ids
        ):
            action = "hold_repair_target"
            source = session.source
            applied_target_kc_ids = [sequence.primary_kc_id]
            rationale = session.rationale or sequence.rationale
        elif (
            sequence.action == "rebuild_prerequisite_first"
            and sequence.primary_kc_id is not None
            and sequence.primary_kc_id not in requested_target_kc_ids
        ):
            action = sequence.action
            source = "strategy_profile"
            applied_target_kc_ids = [sequence.primary_kc_id]
            rationale = sequence.rationale
        elif evidence_decision.decision != "monitor":
            action = evidence_decision.decision
            source = "progression_evidence"
            rationale = evidence_decision.rationale

        applied_request, mastery_gate_action, mastery_gate_reason = self._apply_mastery_gate(
            request=applied_request.model_copy(
                update={
                    "target_kc_ids": applied_target_kc_ids,
                    "target_lo_ids": self._target_lo_ids(applied_target_kc_ids) or request.target_lo_ids,
                }
            ),
            action=action,
            rationale=rationale or sequence.rationale,
        )
        if mastery_gate_action is not None:
            action = mastery_gate_action
            source = "mastery_gate"
            mastery_gate_applied = True

        applied_content_type = (
            applied_request.requested_content_type.value if applied_request.requested_content_type is not None else None
        )

        if applied_target_kc_ids == requested_target_kc_ids:
            return ProgressionOwnershipDecision(
                request=applied_request,
                action=action,
                source=source,
                requested_target_kc_ids=requested_target_kc_ids,
                applied_target_kc_ids=applied_target_kc_ids,
                deferred_target_kc_ids=sequence.deferred_kc_ids,
                bridge_kc_ids=sequence.bridge_kc_ids,
                rationale=rationale or sequence.rationale,
                evidence_observation_count=evidence_decision.matched_observation_count,
                evidence_assessment_count=evidence_decision.matched_assessment_count,
                evidence_confidence=evidence_decision.confidence,
                average_observed_mastery=evidence_decision.average_observed_mastery,
                average_assessment_mastery=evidence_decision.average_assessment_mastery,
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
            requested_target_kc_ids=requested_target_kc_ids,
            applied_target_kc_ids=applied_target_kc_ids,
            deferred_target_kc_ids=sequence.deferred_kc_ids,
            bridge_kc_ids=sequence.bridge_kc_ids,
            rationale=rationale or sequence.rationale,
            evidence_observation_count=evidence_decision.matched_observation_count,
            evidence_assessment_count=evidence_decision.matched_assessment_count,
            evidence_confidence=evidence_decision.confidence,
            average_observed_mastery=evidence_decision.average_observed_mastery,
            average_assessment_mastery=evidence_decision.average_assessment_mastery,
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

    def _evidence_decision(self, *, student_id: UUID, request: GenerationRequest, session_summary):
        if (
            self.observation_store is None
            or self.audit_store is None
            or self.observation_profile_updater is None
        ):
            from dibble.services.observation_profile_update import ProgressionEvidenceDecision

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

    def _apply_mastery_gate(
        self,
        *,
        request: GenerationRequest,
        action: str,
        rationale: str | None,
    ) -> tuple[GenerationRequest, str | None, str | None]:
        assessment_requested = request.intent.value == "assessment" or (
            request.requested_content_type == RequestedContentType.assessment_probe
        )
        if not assessment_requested or action not in {"hold_target", "hold_repair_target"}:
            return request, None, None
        gate_reason = (
            rationale
            or "Recent same-session evidence still suggests the learner should stay on target practice before a transfer-style assessment."
        )
        return (
            request.model_copy(
                update={
                    "intent": ContentIntent.practice,
                    "requested_content_type": RequestedContentType.practice_problem,
                    "curriculum_context": [
                        *request.curriculum_context,
                        "Mastery gate: hold target before transfer-style assessment.",
                        gate_reason,
                    ],
                }
            ),
            "hold_target_before_assessment",
            gate_reason,
        )
