from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.within_session_adaptation import WithinSessionAdaptationService
from dibble.services.within_session_controller_store import SQLiteWithinSessionControllerStore
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
    first_summary = service.record_observation_event(student_id=student_id, event_payload=first_observation)

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
    second_summary = service.record_observation_event(student_id=student_id, event_payload=second_observation)
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
    assert service.adaptation_for(student_id=student_id, request=request).source == "session_controller"


def test_within_session_controller_moves_from_repair_to_transfer_check_after_recovery(tmp_path):
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
    service.record_observation_event(student_id=student_id, event_payload=negative_observation)

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
        recovery_summary = service.record_assessment_event(student_id=student_id, event_payload=recovery_payload)

    final_summary = service.adaptation_for(student_id=student_id, request=request)

    assert recovery_summary.phase == "transfer_check"
    assert recovery_summary.sequence_action == "attempt_transfer"
    assert recovery_summary.positive_streak == 2
    assert final_summary.signal == "positive"
    assert final_summary.phase == "transfer_check"
    assert final_summary.recovery_intent == "confirm_recovery"
