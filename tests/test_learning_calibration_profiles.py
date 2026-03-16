from __future__ import annotations

from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learning_calibration_profiles import LearningCalibrationProfileRecorder
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.storage import ensure_database


def test_learning_calibration_profile_recorder_compacts_matching_run_summaries(tmp_path):
    database_path = str(tmp_path / "learning-calibration-profile-recorder.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    recorder = LearningCalibrationProfileRecorder(audit_store=audit_store)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "intent": "practice",
            "learning_session_id": "session-1",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "run_summary_score": 0.82,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.76,
        },
    )
    anchor_summary = audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-2",
            "intent": "practice",
            "learning_session_id": "session-2",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "run_summary_score": 0.86,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.8,
        },
    )

    recorded = recorder.record_from_summary_events(summary_events=[anchor_summary])

    assert len(recorded) == 1
    profile_event = recorded[0]
    assert profile_event.event_type == "learning.calibration.profile"
    assert profile_event.payload["source_run_summary_event_id"] == anchor_summary.event_id
    assert profile_event.payload["matched_run_count"] == 2
    assert profile_event.payload["matched_session_count"] == 2
    assert profile_event.payload["profile_signal"] == "positive"
    assert profile_event.payload["average_run_outcome_score"] >= 0.84


def test_router_calibration_signal_service_prefers_cross_session_profile_events(tmp_path):
    database_path = str(tmp_path / "router-calibration-profile-events.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.calibration.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.83,
            "average_run_confidence": 0.78,
            "matched_run_count": 4,
            "matched_session_count": 2,
            "positive_run_rate": 0.75,
            "negative_run_rate": 0.0,
            "profile_signal": "positive",
        },
    )
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-3",
            "intent": "practice",
            "learning_session_id": "session-3",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "run_summary_score": 0.32,
            "run_calibration_signal": "negative",
            "run_calibration_confidence": 0.8,
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
        }
    )
    signal = RouterCalibrationSignalService(audit_store=audit_store).signal_for(
        student_id=request.student_id,
        request=request,
    )

    assert signal.signal == "positive"
    assert signal.source == "profile"
    assert signal.matched_run_count == 4
    assert signal.average_run_outcome_score == 0.83
