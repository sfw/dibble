from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.storage import ensure_database


def test_generation_mode_calibrator_raises_independence_for_strong_positive_profile_signal(tmp_path):
    database_path = str(tmp_path / "generation-mode-positive.db")
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
            "average_run_outcome_score": 0.84,
            "average_run_confidence": 0.78,
            "matched_run_count": 4,
            "matched_session_count": 2,
            "positive_run_rate": 0.75,
            "negative_run_rate": 0.0,
            "profile_signal": "positive",
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
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store)
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "profile"
    assert calibrated_request.mode_calibration.signal == "positive"
    assert calibrated_request.mode_calibration.support_bias == 1


def test_generation_mode_calibrator_adds_support_for_negative_run_summary(tmp_path):
    database_path = str(tmp_path / "generation-mode-negative.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "intent": "explanation",
            "learning_session_id": "session-1",
            "content_type": "worked_example",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "run_summary_score": 0.34,
            "run_calibration_signal": "negative",
            "run_calibration_confidence": 0.81,
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "intent": "explanation",
            "requested_content_type": "worked_example",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store)
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "run_summary"
    assert calibrated_request.mode_calibration.signal == "negative"
    assert calibrated_request.mode_calibration.support_bias == -1


def test_generation_mode_calibrator_uses_improving_progress_profile(tmp_path):
    database_path = str(tmp_path / "generation-mode-progress-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.73,
            "average_run_confidence": 0.8,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "positive_run_rate": 0.5,
            "negative_run_rate": 0.0,
            "recent_average_run_outcome_score": 0.8,
            "prior_average_run_outcome_score": 0.64,
            "progress_delta": 0.16,
            "progress_signal": "improving",
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
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store)
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "progress_profile"
    assert calibrated_request.mode_calibration.progress_signal == "improving"
    assert calibrated_request.mode_calibration.support_bias == 1
