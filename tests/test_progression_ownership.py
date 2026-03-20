from __future__ import annotations

from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponent
from dibble.models.generation import GenerationRequest
from dibble.models.observations import LearnerObservationCreate
from dibble.models.profile import LearnerStrategySummary, OrdinaryMasterySummary
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.observation_profile_update import ObservationProfileUpdater
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.progression_ownership import ProgressionOwnershipService
from dibble.services.within_session_adaptation import WithinSessionAdaptationSummary
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


class StubKnowledgeComponentStore:
    def __init__(self) -> None:
        self.components = {
            "KC-1": KnowledgeComponent(
                kc_id="KC-1",
                name="Prerequisite fraction model reading",
                outcome_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=[],
                difficulty=0.3,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
            "KC-2": KnowledgeComponent(
                kc_id="KC-2",
                name="Bridge equivalent fractions",
                outcome_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
                difficulty=0.4,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
            "KC-3": KnowledgeComponent(
                kc_id="KC-3",
                name="Target equivalent fractions",
                outcome_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
                difficulty=0.5,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
        }

    def list(self):
        return list(self.components.values())

    def get(self, kc_id):
        return self.components.get(kc_id)


class StubStrategySignalService:
    def __init__(self, summary: LearnerStrategySummary) -> None:
        self.summary = summary

    def strategy_for(self, *, student_id, request):
        return self.summary


class StubWithinSessionAdaptationService:
    def __init__(self, summary: WithinSessionAdaptationSummary) -> None:
        self.summary = summary

    def adaptation_for(self, *, student_id, request):
        return self.summary


class StubOrdinaryMasterySignalService:
    def __init__(self, summary: OrdinaryMasterySummary) -> None:
        self.summary = summary

    def latest_for_student(self, *, student_id, target_kc_ids, target_lo_ids):
        return self.summary


def _build_observation(
    *,
    session_id: str,
    support_level: str,
    confidence: float,
    hints: int,
    errors: int,
    target_kc_id: str = "KC-3",
):
    return LearnerObservationCreate.model_validate(
        {
            "response_time_ms": 16000,
            "hints_used": hints,
            "error_count": errors,
            "pause_count": 0,
            "modality_switches": 0,
            "completed": True,
            "confidence": confidence,
            "task_type": "practice",
            "support_level": support_level,
            "expected_duration_ms": 18000,
            "learning_session_id": session_id,
            "target_kc_ids": [target_kc_id],
            "target_lo_ids": ["LO-1"],
        }
    )


def test_progression_ownership_rebuilds_prerequisite_before_requested_target():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            curriculum_context=["Equivalent fractions"],
        ),
    )

    assert decision.action == "rebuild_prerequisite_first"
    assert decision.source == "strategy_profile"
    assert decision.target_stage == "repair"
    assert decision.target_redirect_applied is True
    assert decision.requested_target_kc_ids == ["KC-3"]
    assert decision.applied_target_kc_ids == ["KC-1"]
    assert decision.transfer_target_kc_ids == ["KC-3"]
    assert decision.request.target_kc_ids == ["KC-1"]
    assert (
        decision.request.curriculum_context[-2]
        == "Progression ownership: rebuild_prerequisite_first."
    )


def test_progression_ownership_preserves_strategy_hold_target_as_explicit_action():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                support_bias=-1,
                recovery_focus="guided_practice",
                trajectory_state="plateaued",
                recommended_next_action="introduce_varied_support",
                rationale="Recent strategy signals suggest staying on the target KC until the learner stabilizes.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_target"
    assert decision.source == "strategy_profile"
    assert decision.target_stage == "target"
    assert decision.applied_target_kc_ids == ["KC-1"]
    assert (
        decision.rationale
        == "Recent strategy signals suggest staying on the target KC until the learner stabilizes."
    )


def test_progression_ownership_preserves_bridge_hold_target_during_bridge_phase():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary(
                signal="recovering",
                source="session_controller",
                phase="bridge",
                recovery_intent="bridge_target",
                sequence_action="hold_bridge_target",
                rationale="Bridge through a nearby KC before the final return.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-bridge",
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
        ),
    )

    assert decision.action == "hold_bridge_target"
    assert decision.source == "session_controller"
    assert decision.target_stage == "bridge"
    assert decision.applied_target_kc_ids == ["KC-2"]
    assert decision.bridge_kc_ids == ["KC-2"]
    assert decision.request.target_kc_ids == ["KC-2"]


def test_progression_ownership_holds_target_when_recent_success_is_support_heavy(
    tmp_path,
):
    database_path = str(tmp_path / "progression-hold.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    observation_store = SQLiteObservationStore(conn)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    for observation in [
        _build_observation(
            session_id="session-hold",
            support_level="high",
            confidence=0.62,
            hints=3,
            errors=0,
            target_kc_id="KC-1",
        ),
        _build_observation(
            session_id="session-hold",
            support_level="high",
            confidence=0.6,
            hints=2,
            errors=1,
            target_kc_id="KC-1",
        ),
    ]:
        observation_store.append(student_id=str(student_id), observation=observation)
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        observation_store=observation_store,
        audit_store=audit_store,
        observation_profile_updater=ObservationProfileUpdater(),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-hold",
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_target"
    assert decision.source == "progression_evidence"
    assert decision.target_stage == "target"
    assert decision.evidence_observation_count == 2
    assert decision.evidence_assessment_count == 0


def test_progression_ownership_uses_repair_target_evidence_after_backend_redirect(
    tmp_path,
):
    database_path = str(tmp_path / "progression-repair-evidence.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    observation_store = SQLiteObservationStore(conn)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    for observation in [
        _build_observation(
            session_id="session-repair-evidence",
            support_level="medium",
            confidence=0.78,
            hints=0,
            errors=0,
            target_kc_id="KC-1",
        ),
        _build_observation(
            session_id="session-repair-evidence",
            support_level="medium",
            confidence=0.74,
            hints=0,
            errors=0,
            target_kc_id="KC-1",
        ),
    ]:
        observation_store.append(student_id=str(student_id), observation=observation)
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary(
                signal="recovering",
                source="session_controller",
                phase="repair",
                recovery_intent="hold_repair",
                sequence_action="hold_repair_target",
                rationale="Stay on the repair target until transfer readiness is less support-dependent.",
            )
        ),
        observation_store=observation_store,
        audit_store=audit_store,
        observation_profile_updater=ObservationProfileUpdater(),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-repair-evidence",
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_repair_target"
    assert decision.source == "progression_evidence"
    assert decision.target_stage == "repair"
    assert decision.applied_target_kc_ids == ["KC-1"]
    assert decision.evidence_observation_count == 2
    assert decision.average_observed_mastery is not None
    assert decision.average_observed_mastery >= 0.72


def test_progression_ownership_attempts_transfer_when_assessment_confirms_readiness(
    tmp_path,
):
    database_path = str(tmp_path / "progression-transfer.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    observation_store = SQLiteObservationStore(conn)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    for observation in [
        _build_observation(
            session_id="session-transfer",
            support_level="low",
            confidence=0.76,
            hints=0,
            errors=0,
            target_kc_id="KC-1",
        ),
        _build_observation(
            session_id="session-transfer",
            support_level="low",
            confidence=0.74,
            hints=1,
            errors=0,
            target_kc_id="KC-1",
        ),
    ]:
        observation_store.append(student_id=str(student_id), observation=observation)
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=str(student_id),
        payload={
            "learning_session_id": "session-transfer",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.83,
            "inferred_mastery": 0.79,
        },
    )
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        observation_store=observation_store,
        audit_store=audit_store,
        observation_profile_updater=ObservationProfileUpdater(),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-transfer",
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "attempt_transfer"
    assert decision.source == "progression_evidence"
    assert decision.target_stage == "transfer"
    assert decision.transfer_target_kc_ids == ["KC-1"]
    assert decision.evidence_observation_count == 2
    assert decision.evidence_assessment_count == 1
    assert decision.evidence_confidence >= 0.7
    assert "Same-session evidence confidence 0.76" in decision.rationale
    assert "2 observation(s)" in decision.rationale
    assert "1 assessment(s)" in decision.rationale


def test_progression_ownership_holds_assessment_request_on_target_practice_until_mastery_is_stronger(
    tmp_path,
):
    database_path = str(tmp_path / "progression-mastery-gate.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    observation_store = SQLiteObservationStore(conn)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    for observation in [
        _build_observation(
            session_id="session-mastery-gate",
            support_level="high",
            confidence=0.61,
            hints=3,
            errors=0,
            target_kc_id="KC-1",
        ),
        _build_observation(
            session_id="session-mastery-gate",
            support_level="high",
            confidence=0.58,
            hints=2,
            errors=1,
            target_kc_id="KC-1",
        ),
    ]:
        observation_store.append(student_id=str(student_id), observation=observation)
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        observation_store=observation_store,
        audit_store=audit_store,
        observation_profile_updater=ObservationProfileUpdater(),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-mastery-gate",
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            intent="assessment",
            requested_content_type="assessment_probe",
        ),
    )

    assert decision.action == "hold_target_before_assessment"
    assert decision.source == "mastery_gate"
    assert decision.target_stage == "target"
    assert decision.mastery_gate_applied is True
    assert decision.requested_content_type == "assessment_probe"
    assert decision.applied_content_type == "practice_problem"
    assert "Same-session evidence confidence 0.56" in decision.rationale
    assert "2 observation(s)" in decision.rationale
    assert decision.request.intent.value == "practice"
    assert decision.request.requested_content_type == "practice_problem"


def test_progression_ownership_prefers_strong_same_session_transfer_over_prerequisite_rebuild(
    tmp_path,
):
    database_path = str(tmp_path / "progression-transfer-override.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    observation_store = SQLiteObservationStore(conn)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    for observation in [
        _build_observation(
            session_id="session-transfer-override",
            support_level="low",
            confidence=0.82,
            hints=0,
            errors=0,
            target_kc_id="KC-3",
        ),
        _build_observation(
            session_id="session-transfer-override",
            support_level="low",
            confidence=0.79,
            hints=1,
            errors=0,
            target_kc_id="KC-3",
        ),
    ]:
        observation_store.append(student_id=str(student_id), observation=observation)
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=str(student_id),
        payload={
            "learning_session_id": "session-transfer-override",
            "target_kc_ids": ["KC-3"],
            "target_lo_ids": ["LO-1"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.86,
            "inferred_mastery": 0.81,
        },
    )
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        observation_store=observation_store,
        audit_store=audit_store,
        observation_profile_updater=ObservationProfileUpdater(),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-transfer-override",
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "attempt_transfer"
    assert decision.source == "progression_evidence"
    assert decision.target_stage == "transfer"
    assert decision.applied_target_kc_ids == ["KC-3"]
    assert decision.transfer_target_kc_ids == ["KC-3"]
    assert decision.evidence_assessment_count == 1


def test_progression_ownership_gates_bridge_redirected_assessment_back_to_practice():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary(
                signal="recovering",
                source="session_controller",
                phase="bridge",
                recovery_intent="bridge_target",
                sequence_action="hold_bridge_target",
                rationale="Bridge through a nearby KC before the final return.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-bridge-assessment",
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            intent="assessment",
            requested_content_type="assessment_probe",
        ),
    )

    assert decision.action == "bridge_before_assessment"
    assert decision.source == "mastery_gate"
    assert decision.target_stage == "bridge"
    assert decision.mastery_gate_applied is True
    assert decision.applied_target_kc_ids == ["KC-2"]
    assert decision.request.requested_content_type == "practice_problem"


def test_progression_ownership_uses_durable_ordinary_mastery_to_hold_target_before_transfer():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="independence_ready",
                source="strategy_profile",
                support_bias=1,
                trajectory_state="accelerating",
                recommended_next_action="check_transfer_readiness",
                rationale="Recent cross-session strategy suggests checking transfer readiness.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.78,
                average_observed_mastery=0.61,
                rationale="Ordinary practice is still too support-heavy for transfer.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            intent="assessment",
            requested_content_type="assessment_probe",
        ),
    )

    assert decision.action == "hold_target_before_assessment"
    assert decision.source == "mastery_gate"
    assert decision.target_stage == "target"
    assert decision.ordinary_mastery_signal == "support_dependent"
    assert decision.ordinary_mastery_source == "ordinary_mastery_profile"
    assert decision.ordinary_mastery_confidence == 0.78
    assert decision.rationale == (
        "Ordinary practice is still too support-heavy for transfer. "
        "Keep the learner on target practice instead of assigning a transfer check yet. "
        "Ordinary mastery signal support_dependent at 0.78 confidence; average observed mastery 0.61."
    )
    assert decision.request.requested_content_type == "practice_problem"


def test_progression_ownership_uses_durable_ordinary_mastery_to_hold_repair_target_after_redirect():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.79,
                average_observed_mastery=0.59,
                rationale="Recent ordinary practice on the prerequisite KC is still support-heavy.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_repair_target"
    assert decision.source == "ordinary_mastery_profile"
    assert decision.target_stage == "repair"
    assert decision.applied_target_kc_ids == ["KC-1"]
    assert decision.ordinary_mastery_signal == "support_dependent"
    assert decision.rationale == (
        "Recent ordinary practice on the prerequisite KC is still support-heavy. "
        "Keep the learner on the repair target instead of returning to the target KC yet. "
        "Ordinary mastery signal support_dependent at 0.79 confidence; average observed mastery 0.59."
    )


def test_asymmetric_repair_hold_support_dependent_triggers_at_lower_confidence():
    """ADAPT-006: repair targets use 0.45 threshold for support_dependent
    instead of the regular 0.55, so a confidence of 0.48 should hold repair
    but NOT hold a regular target."""
    student_id = uuid4()

    # At confidence 0.48 for repair stage -> should hold
    repair_service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.48,
                average_observed_mastery=0.55,
                rationale="Repair target still support-dependent at moderate confidence.",
            )
        ),
    )

    repair_decision = repair_service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    # Repair stage should hold because 0.48 >= 0.45
    assert repair_decision.action == "hold_repair_target"
    assert repair_decision.source == "ordinary_mastery_profile"
    assert repair_decision.target_stage == "repair"

    # At the same confidence for target stage -> should NOT hold
    target_service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.48,
                average_observed_mastery=0.55,
                rationale="Target still support-dependent at moderate confidence.",
            )
        ),
    )

    target_decision = target_service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    # Target stage should NOT hold because 0.48 < 0.55
    assert target_decision.action != "hold_target"


def test_asymmetric_repair_hold_fragile_triggers_at_lower_confidence():
    """ADAPT-006: repair targets use 0.55 threshold for fragile instead of
    the regular 0.65, so a confidence of 0.58 should hold repair but NOT
    hold a regular target."""
    student_id = uuid4()

    # At confidence 0.58 for repair stage -> should hold
    repair_service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="fragile",
                source="ordinary_mastery_profile",
                confidence=0.58,
                average_observed_mastery=0.48,
                rationale="Repair target still fragile at moderate confidence.",
            )
        ),
    )

    repair_decision = repair_service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert repair_decision.action == "hold_repair_target"
    assert repair_decision.source == "ordinary_mastery_profile"
    assert repair_decision.target_stage == "repair"

    # At the same confidence for target stage -> should NOT hold
    target_service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="fragile",
                source="ordinary_mastery_profile",
                confidence=0.58,
                average_observed_mastery=0.48,
                rationale="Target still fragile at moderate confidence.",
            )
        ),
    )

    target_decision = target_service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert target_decision.action != "hold_target"


def test_high_low_support_success_rate_relaxes_hold_threshold():
    """ADAPT-006: When the ordinary mastery profile has a high low-support
    success rate (>= 0.5), the hold threshold should be raised so that the
    learner with growing independence is not held as aggressively."""
    student_id = uuid4()
    # Confidence 0.58 is above the base support_dependent threshold (0.55)
    # for target stage, but should NOT hold when low_support_success_rate
    # is high enough to raise the effective threshold to 0.63.
    # matched_observation_count must be >= 4 for the full bonus to apply.
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.58,
                matched_observation_count=6,
                average_observed_mastery=0.60,
                low_support_success_rate=0.55,
                high_support_dependency_rate=0.2,
                rationale="Support-dependent but with growing independence.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    # Should NOT hold because the effective threshold was raised by 0.08
    assert decision.action != "hold_target"


def test_sparse_evidence_scales_down_low_support_bonus():
    """ADAPT-006: When there are very few observations, the low-support
    success rate bonus should be scaled down so sparse evidence doesn't
    earn the full threshold adjustment."""
    student_id = uuid4()
    # Same as test_high_low_support_success_rate_relaxes_hold_threshold
    # but with only 1 observation — the bonus should be scaled to 0.02
    # (0.08 * 1/4), making the effective threshold 0.57 instead of 0.63.
    # Since confidence=0.58 >= 0.57, the learner SHOULD be held.
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.58,
                matched_observation_count=1,
                average_observed_mastery=0.60,
                low_support_success_rate=0.55,
                high_support_dependency_rate=0.2,
                rationale="Support-dependent but with sparse independence evidence.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    # Should hold because the scaled bonus (0.02) doesn't raise the
    # threshold enough: effective threshold = 0.57, confidence = 0.58.
    assert decision.action == "hold_target"
    assert decision.source == "ordinary_mastery_profile"


def test_high_support_dependency_rate_tightens_hold_threshold():
    """ADAPT-006: When the ordinary mastery profile has a very high support
    dependency rate (>= 0.7), the hold threshold should be lowered so that
    borderline cases are held more aggressively."""
    student_id = uuid4()
    # Confidence 0.50 is below the base support_dependent threshold (0.55)
    # for target stage, but SHOULD hold when high_support_dependency_rate
    # is high enough to lower the effective threshold to 0.49.
    # matched_observation_count must be >= 4 for the full penalty to apply.
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.50,
                matched_observation_count=5,
                average_observed_mastery=0.52,
                low_support_success_rate=0.1,
                high_support_dependency_rate=0.75,
                rationale="Very support-heavy ordinary practice.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    # Should hold because the effective threshold was lowered by 0.06
    assert decision.action == "hold_target"
    assert decision.source == "ordinary_mastery_profile"


def test_stuck_repair_context_surfaces_in_rationale_for_many_observations():
    """ADAPT-006: When a learner has been held for many observations across
    many sessions without improving, the rationale should include a stuck-
    repair context hint for downstream consumers."""
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.82,
                matched_observation_count=8,
                matched_session_count=4,
                average_observed_mastery=0.54,
                low_support_success_rate=0.1,
                high_support_dependency_rate=0.7,
                rationale="Many observations but still support-dependent.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_repair_target"
    assert "extended hold" in decision.rationale
    assert "teacher review" in decision.rationale
    assert "8 matched observation(s)" in decision.rationale
    assert "across 4 sessions" in decision.rationale


def test_improving_trend_relaxes_hold_threshold():
    """ADAPT-006: An improving mastery trend should raise the effective hold
    threshold so a learner who is gaining ground is not held as aggressively."""
    student_id = uuid4()
    # Confidence 0.58 is above the base target threshold (0.55) for
    # support_dependent, but with an improving trend the effective threshold
    # rises by 0.06 to 0.61, so 0.58 should NOT trigger a hold.
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.58,
                average_observed_mastery=0.55,
                mastery_trend="improving",
                rationale="Support-dependent but improving.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    # Improving trend should prevent the hold
    assert decision.action != "hold_target"


def test_declining_trend_tightens_hold_threshold():
    """ADAPT-006: A declining mastery trend should lower the effective hold
    threshold so a learner who is losing ground is held more aggressively."""
    student_id = uuid4()
    # Confidence 0.52 is below the base target threshold (0.55) for
    # support_dependent, but with a declining trend the effective threshold
    # drops by 0.05 to 0.50, so 0.52 should NOW trigger a hold.
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="support_dependent",
                source="ordinary_mastery_profile",
                confidence=0.52,
                average_observed_mastery=0.50,
                mastery_trend="declining",
                rationale="Support-dependent and declining.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_target"
    assert decision.source == "ordinary_mastery_profile"
    assert "declining" in decision.rationale


def test_declining_trend_triggers_earlier_stuck_detection():
    """ADAPT-006: A declining trend should trigger the stuck-repair signal
    earlier (4 observations / 2 sessions) instead of the usual 6 / 3."""
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="rebuild_prerequisite_first",
                source="strategy_profile",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="fragile",
                source="ordinary_mastery_profile",
                confidence=0.62,
                matched_observation_count=4,
                matched_session_count=2,
                average_observed_mastery=0.42,
                mastery_trend="declining",
                rationale="Repair target fragile and declining.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_repair_target"
    assert "declining hold" in decision.rationale
    assert "teacher review" in decision.rationale


def test_stable_trend_does_not_trigger_early_stuck_detection():
    """ADAPT-006: With a stable trend, the stuck signal should still require
    the standard 6 observations / 3 sessions threshold."""
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="rebuild_prerequisite_first",
                source="strategy_profile",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="fragile",
                source="ordinary_mastery_profile",
                confidence=0.62,
                matched_observation_count=4,
                matched_session_count=2,
                average_observed_mastery=0.42,
                mastery_trend="stable",
                rationale="Repair target fragile and stable.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_repair_target"
    # With stable trend and only 4 observations / 2 sessions, no stuck signal
    assert "extended hold" not in (decision.rationale or "")
    assert "declining hold" not in (decision.rationale or "")


def test_progression_ownership_high_volatility_lowers_hold_threshold():
    """A learner with high mastery volatility should be held more aggressively
    because the aggregate mastery signal is unreliable."""
    student_id = uuid4()

    # Use KC-1 (no prerequisites) to avoid prerequisite redirects.
    # With confidence 0.60 and no volatility, a fragile signal at target stage
    # would NOT trigger a hold because the default fragile threshold is 0.65.
    # But with high volatility (>= 0.18), the threshold drops by 0.07 * evidence_scale,
    # making it 0.58 — now the hold triggers.
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="insufficient",
                source="insufficient",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="fragile",
                source="ordinary_mastery_profile",
                confidence=0.60,
                matched_observation_count=6,
                matched_session_count=3,
                average_observed_mastery=0.48,
                mastery_volatility=0.22,
                rationale="Ordinary practice highly volatile.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    assert decision.action == "hold_target"
    assert decision.source == "ordinary_mastery_profile"
    assert "volatility" in (decision.rationale or "")


def test_progression_ownership_no_volatility_penalty_when_low():
    """A learner with low volatility should not get a volatility-driven hold
    that would not have happened without it."""
    student_id = uuid4()

    # Use KC-1 (no prerequisites) to avoid prerequisite redirects.
    # Fragile with confidence 0.60 and low volatility — should NOT hold at
    # the default fragile target threshold of 0.65.
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="insufficient",
                source="insufficient",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary()
        ),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            OrdinaryMasterySummary(
                signal="fragile",
                source="ordinary_mastery_profile",
                confidence=0.60,
                matched_observation_count=6,
                matched_session_count=3,
                average_observed_mastery=0.48,
                mastery_volatility=0.05,
                rationale="Ordinary practice low volatility.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            requested_content_type="practice_problem",
        ),
    )

    # Confidence 0.60 < fragile threshold 0.65, and no volatility penalty
    assert decision.action == "stay_on_requested_target"
