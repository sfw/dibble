from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.within_session_adaptation import WithinSessionAdaptationService
from dibble.services.within_session_controller_store import (
    SQLiteWithinSessionControllerStore,
)
from dibble.storage import ensure_database


def test_within_session_adaptation_detects_live_struggle_from_observations(tmp_path):
    database_path = str(tmp_path / "within-session-adaptation-negative.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "error_count": 3,
            "hints_used": 2,
            "support_level": "low",
            "frustration": "high",
            "total_load": 0.84,
            "confidence_calibration": 0.24,
            "help_seeking": "high",
        },
    )

    summary = WithinSessionAdaptationService(audit_store=audit_store).adaptation_for(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-1",
            target_kc_ids=["KC-1"],
            intent="practice",
            requested_content_type="practice_problem",
        ),
    )

    assert summary.signal == "negative"
    assert summary.support_bias == -1
    assert summary.sequence_action == "hold_target"
    assert summary.matched_observation_count == 1


def test_within_session_adaptation_detects_transfer_readiness_from_assessment(tmp_path):
    database_path = str(tmp_path / "within-session-adaptation-positive.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-2",
            "target_kc_ids": ["KC-2"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.81,
            "next_action": "advance",
        },
    )

    summary = WithinSessionAdaptationService(audit_store=audit_store).adaptation_for(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-2",
            target_kc_ids=["KC-2"],
            intent="assessment",
            requested_content_type="assessment_probe",
        ),
    )

    assert summary.signal == "positive"
    assert summary.support_bias == 1
    assert summary.sequence_action == "attempt_transfer"
    assert summary.matched_assessment_count == 1


def test_within_session_adaptation_uses_explicit_socratic_steering_action_when_present(
    tmp_path,
):
    database_path = str(tmp_path / "within-session-adaptation-steering.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-steering",
            "target_kc_ids": ["KC-2"],
            "prompt_style": "diagnostic",
            "steering_action": "open_probe",
            "evidence_strength": "insufficient",
            "evidence_score": 0.0,
            "next_action": "ask_probe",
        },
    )

    summary = WithinSessionAdaptationService(audit_store=audit_store).adaptation_for(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-steering",
            target_kc_ids=["KC-2"],
            intent="assessment",
            requested_content_type="assessment_probe",
        ),
    )

    assert summary.latest_assessment_prompt_style == "diagnostic"
    assert summary.socratic_steering_action == "open_probe"


def test_within_session_controller_persists_repair_state_across_steps(tmp_path):
    database_path = str(tmp_path / "within-session-controller-repair.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    controller_store = SQLiteWithinSessionControllerStore(database_path)
    student_id = uuid4()
    service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=controller_store,
    )
    request = GenerationRequest(
        student_id=student_id,
        learning_session_id="session-controller",
        target_kc_ids=["KC-1"],
        intent="practice",
        requested_content_type="practice_problem",
    )

    first_observation = {
        "learning_session_id": "session-controller",
        "target_kc_ids": ["KC-1"],
        "error_count": 3,
        "hints_used": 2,
        "support_level": "low",
        "frustration": "high",
        "total_load": 0.84,
        "confidence_calibration": 0.24,
        "help_seeking": "high",
    }
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload=first_observation,
    )
    first_summary = service.record_observation_event(
        student_id=student_id, event_payload=first_observation
    )

    second_observation = {
        **first_observation,
        "error_count": 2,
        "total_load": 0.8,
    }
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload=second_observation,
    )
    second_summary = service.record_observation_event(
        student_id=student_id, event_payload=second_observation
    )
    generated_summary = service.record_generation_step(
        request=request,
        content_type="practice_problem",
        generation_id="gen-1",
    )

    assert first_summary.source == "session_controller"
    assert first_summary.phase == "stabilize"
    assert first_summary.negative_streak == 1
    assert second_summary.signal == "negative"
    assert second_summary.phase == "repair"
    assert second_summary.negative_streak == 2
    assert generated_summary.phase == "repair"
    assert generated_summary.generated_step_count == 1
    assert (
        service.adaptation_for(student_id=student_id, request=request).source
        == "session_controller"
    )


def test_within_session_controller_detects_support_loop_after_budget_is_used(tmp_path):
    database_path = str(tmp_path / "within-session-controller-loop-risk.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    controller_store = SQLiteWithinSessionControllerStore(database_path)
    student_id = uuid4()
    service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=controller_store,
    )
    request = GenerationRequest(
        student_id=student_id,
        learning_session_id="session-loop-risk",
        target_kc_ids=["KC-1"],
        intent="practice",
        requested_content_type="practice_problem",
    )

    observation_payload = {
        "learning_session_id": "session-loop-risk",
        "target_kc_ids": ["KC-1"],
        "error_count": 3,
        "hints_used": 2,
        "support_level": "low",
        "frustration": "high",
        "total_load": 0.84,
        "confidence_calibration": 0.2,
        "help_seeking": "high",
    }
    for _ in range(2):
        audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=str(student_id),
            payload=observation_payload,
        )
        repair_summary = service.record_observation_event(
            student_id=student_id, event_payload=observation_payload
        )

    first_generation = service.record_generation_step(
        request=request,
        content_type="practice_problem",
        generation_id="gen-1",
    )
    second_generation = service.record_generation_step(
        request=request,
        content_type="practice_problem",
        generation_id="gen-2",
    )

    assert repair_summary.phase == "repair"
    assert repair_summary.support_step_budget == 2
    assert first_generation.support_steps_remaining == 1
    assert first_generation.stuck_loop_risk == "moderate"
    assert second_generation.support_steps_remaining == 0
    assert second_generation.stuck_loop_risk == "high"
    assert second_generation.arc_action == "reprobe_new_angle"


def test_within_session_controller_moves_from_repair_to_transfer_check_after_recovery(
    tmp_path,
):
    database_path = str(tmp_path / "within-session-controller-recovery.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    controller_store = SQLiteWithinSessionControllerStore(database_path)
    student_id = uuid4()
    service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=controller_store,
    )
    request = GenerationRequest(
        student_id=student_id,
        learning_session_id="session-recovery",
        target_kc_ids=["KC-2"],
        intent="assessment",
        requested_content_type="assessment_probe",
    )

    negative_observation = {
        "learning_session_id": "session-recovery",
        "target_kc_ids": ["KC-2"],
        "error_count": 3,
        "hints_used": 2,
        "support_level": "low",
        "frustration": "high",
        "total_load": 0.84,
        "confidence_calibration": 0.2,
        "help_seeking": "high",
    }
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload=negative_observation,
    )
    service.record_observation_event(
        student_id=student_id, event_payload=negative_observation
    )

    recovery_payload = {
        "learning_session_id": "session-recovery",
        "target_kc_ids": ["KC-2"],
        "evidence_strength": "demonstrated",
        "evidence_score": 0.95,
        "next_action": "advance",
    }
    for _ in range(3):
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=str(student_id),
            payload=recovery_payload,
        )
        recovery_summary = service.record_assessment_event(
            student_id=student_id, event_payload=recovery_payload
        )

    final_summary = service.adaptation_for(student_id=student_id, request=request)

    assert recovery_summary.phase == "transfer_check"
    assert recovery_summary.sequence_action == "attempt_transfer"
    assert recovery_summary.positive_streak == 3
    assert recovery_summary.arc_action == "attempt_transfer"
    assert final_summary.signal == "positive"
    assert final_summary.phase == "transfer_check"
    assert final_summary.recovery_intent == "check_transfer"


def test_within_session_controller_moves_through_consolidate_and_bridge_before_transfer(
    tmp_path,
):
    database_path = str(tmp_path / "within-session-controller-bridge.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    controller_store = SQLiteWithinSessionControllerStore(database_path)
    student_id = uuid4()
    service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=controller_store,
    )

    negative_observation = {
        "learning_session_id": "session-bridge",
        "target_kc_ids": ["KC-2"],
        "error_count": 3,
        "hints_used": 2,
        "support_level": "low",
        "frustration": "high",
        "total_load": 0.82,
        "confidence_calibration": 0.22,
        "help_seeking": "high",
    }
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload=negative_observation,
    )
    service.record_observation_event(
        student_id=student_id, event_payload=negative_observation
    )

    recovery_payload = {
        "learning_session_id": "session-bridge",
        "target_kc_ids": ["KC-2"],
        "evidence_strength": "demonstrated",
        "evidence_score": 0.88,
        "next_action": "advance",
    }
    phases: list[str] = []
    sequence_actions: list[str] = []
    for _ in range(3):
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=str(student_id),
            payload=recovery_payload,
        )
        summary = service.record_assessment_event(
            student_id=student_id, event_payload=recovery_payload
        )
        phases.append(summary.phase)
        sequence_actions.append(summary.sequence_action)

    assert phases == ["consolidate", "bridge", "transfer_check"]
    assert sequence_actions == ["hold_target", "hold_bridge_target", "attempt_transfer"]


def test_within_session_controller_blocks_transfer_when_live_evidence_still_shows_support_dependence(
    tmp_path,
):
    database_path = str(tmp_path / "within-session-controller-support-dependence.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    controller_store = SQLiteWithinSessionControllerStore(database_path)
    student_id = uuid4()
    service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=controller_store,
    )

    support_dependent_observation = {
        "learning_session_id": "session-support-dependent",
        "target_kc_ids": ["KC-2"],
        "error_count": 1,
        "hints_used": 3,
        "support_level": "high",
        "frustration": "low",
        "total_load": 0.58,
        "confidence_calibration": 0.42,
        "help_seeking": "high",
        "current_evidence_signal": "support_dependence",
        "current_evidence_confidence": 0.82,
    }
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(student_id),
        payload=support_dependent_observation,
    )
    service.record_observation_event(
        student_id=student_id, event_payload=support_dependent_observation
    )

    recovery_payload = {
        "learning_session_id": "session-support-dependent",
        "target_kc_ids": ["KC-2"],
        "evidence_strength": "demonstrated",
        "evidence_score": 0.9,
        "next_action": "advance",
    }
    phases: list[str] = []
    sequence_actions: list[str] = []
    for _ in range(3):
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=str(student_id),
            payload=recovery_payload,
        )
        summary = service.record_assessment_event(
            student_id=student_id, event_payload=recovery_payload
        )
        phases.append(summary.phase)
        sequence_actions.append(summary.sequence_action)

    final_summary = service.adaptation_for(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-support-dependent",
            target_kc_ids=["KC-2"],
            intent="assessment",
            requested_content_type="assessment_probe",
        ),
    )

    assert phases == ["consolidate", "bridge", "bridge"]
    assert sequence_actions == [
        "hold_target",
        "hold_bridge_target",
        "hold_bridge_target",
    ]
    assert final_summary.phase == "bridge"
    assert final_summary.sequence_action == "hold_bridge_target"
    assert final_summary.recovery_intent == "bridge_target"


def test_within_session_adaptation_keeps_productive_struggle_out_of_negative_bucket(
    tmp_path,
):
    database_path = str(tmp_path / "within-session-adaptation-productive-struggle.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-productive",
            "target_kc_ids": ["KC-1"],
            "error_count": 1,
            "hints_used": 1,
            "support_level": "low",
            "frustration": "low",
            "total_load": 0.48,
            "confidence_calibration": 0.58,
            "help_seeking": "low",
            "current_evidence_signal": "productive_struggle",
            "current_evidence_confidence": 0.76,
            "current_evidence_rationale": "Recoverable friction under low support.",
        },
    )

    summary = WithinSessionAdaptationService(audit_store=audit_store).adaptation_for(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-productive",
            target_kc_ids=["KC-1"],
            intent="practice",
            requested_content_type="practice_problem",
        ),
    )

    assert summary.current_evidence_signal == "productive_struggle"
    assert summary.signal in {"mixed", "positive"}
    assert summary.support_bias >= 0
