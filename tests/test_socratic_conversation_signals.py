from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.socratic_conversation_signals import (
    SocraticConversationSignalService,
)
from dibble.storage import ensure_database


def test_socratic_conversation_signal_service_detects_model_then_release_history(
    tmp_path,
):
    database_path = str(tmp_path / "socratic-conversation-model.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_uuid = uuid4()
    student_id = str(student_uuid)
    for session_id, steering_action, evidence_strength in [
        ("session-1", "repair_then_model", "insufficient"),
        ("session-1", "repair_then_model", "emerging"),
        ("session-2", "clarify_then_check", "emerging"),
        ("session-2", "repair_then_model", "insufficient"),
    ]:
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": session_id,
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
                "prompt_style": "scaffolded_step_back",
                "steering_action": steering_action,
                "evidence_strength": evidence_strength,
            },
        )

    summary = SocraticConversationSignalService(audit_store=audit_store).summary_for(
        student_id=student_uuid,
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
                "intent": "explanation",
            }
        ),
    )

    assert summary.signal == "model_then_release"
    assert summary.source == "socratic_assessment_history"
    assert summary.matched_session_count == 2
    assert summary.dominant_steering_action == "repair_then_model"
    assert summary.repair_rate >= 0.5


def test_socratic_conversation_signal_service_detects_transfer_ready_history(tmp_path):
    database_path = str(tmp_path / "socratic-conversation-transfer.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_uuid = uuid4()
    student_id = str(student_uuid)
    for session_id, steering_action in [
        ("session-1", "verify_transfer"),
        ("session-1", "restate_then_apply"),
        ("session-2", "verify_transfer"),
        ("session-2", "verify_transfer"),
    ]:
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": session_id,
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-2"],
                "prompt_style": "transfer_check",
                "steering_action": steering_action,
                "evidence_strength": "demonstrated",
            },
        )

    summary = SocraticConversationSignalService(audit_store=audit_store).summary_for(
        student_id=student_uuid,
        request=GenerationRequest.model_validate(
            {
                "student_id": student_id,
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-2"],
                "intent": "practice",
                "requested_content_type": "practice_problem",
            }
        ),
    )

    assert summary.signal == "independent_check"
    assert summary.transfer_readiness >= 0.75
    assert summary.dominant_prompt_style == "transfer_check"
