from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.within_session_adaptation import WithinSessionAdaptationService
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
