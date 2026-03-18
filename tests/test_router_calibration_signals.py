from __future__ import annotations

from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.storage import ensure_database


def test_router_calibration_signal_service_returns_negative_signal_for_recent_struggle(
    tmp_path,
):
    database_path = str(tmp_path / "router-calibration-negative.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "intent": "explanation",
            "generation_id": "gen-1",
            "learning_session_id": "run-1",
            "target_kc_ids": ["KC-1"],
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.baseline",
            "prompt_template_variant": "baseline",
            "quality_score": 0.88,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "learning_session_id": "run-1",
            "observed_content_type": "micro_explanation",
            "task_type": "explanation",
            "target_kc_ids": ["KC-1"],
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.84,
            "confidence_calibration": 0.28,
            "help_seeking": "high",
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "target_kc_ids": ["KC-1"],
            "intent": "explanation",
        }
    )
    signal = RouterCalibrationSignalService(audit_store=audit_store).signal_for(
        student_id=request.student_id,
        request=request,
    )

    assert signal.signal == "negative"
    assert signal.source == "derived"
    assert signal.confidence >= 0.6
    assert signal.average_run_outcome_score is not None
    assert signal.average_run_outcome_score < 0.5
    assert signal.matched_run_count == 1


def test_router_calibration_signal_service_prefers_same_session_matches(tmp_path):
    database_path = str(tmp_path / "router-calibration-session.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "generation_id": "gen-wrong",
            "learning_session_id": "other-run",
            "target_kc_ids": ["KC-1"],
            "content_type": "practice_problem",
            "prompt_template_name": "practice_problem.baseline",
            "prompt_template_variant": "baseline",
            "quality_score": 0.8,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-wrong",
            "learning_session_id": "other-run",
            "observed_content_type": "practice_problem",
            "task_type": "practice",
            "target_kc_ids": ["KC-1"],
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.82,
            "confidence_calibration": 0.24,
            "help_seeking": "high",
        },
    )
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "generation_id": "gen-right",
            "learning_session_id": "request-run",
            "target_kc_ids": ["KC-1"],
            "content_type": "practice_problem",
            "prompt_template_name": "practice_problem.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.76,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-right",
            "learning_session_id": "request-run",
            "observed_content_type": "practice_problem",
            "task_type": "practice",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.22,
            "confidence_calibration": 0.84,
            "help_seeking": "low",
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "request-run",
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        }
    )
    signal = RouterCalibrationSignalService(audit_store=audit_store).signal_for(
        student_id=request.student_id,
        request=request,
    )

    assert signal.signal == "positive"
    assert signal.source == "derived"
    assert signal.matched_run_count == 1
    assert signal.average_run_outcome_score is not None
    assert signal.average_run_outcome_score > 0.75


def test_router_calibration_signal_service_returns_insufficient_without_matching_runs(
    tmp_path,
):
    database_path = str(tmp_path / "router-calibration-insufficient.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)

    request = GenerationRequest.model_validate(
        {
            "student_id": str(uuid4()),
            "target_kc_ids": ["KC-1"],
            "intent": "explanation",
        }
    )
    signal = RouterCalibrationSignalService(audit_store=audit_store).signal_for(
        student_id=request.student_id,
        request=request,
    )

    assert signal.signal == "insufficient"
    assert signal.source == "insufficient"
    assert signal.matched_run_count == 0
    assert signal.average_run_outcome_score is None


def test_router_calibration_signal_service_prefers_persisted_run_summaries(tmp_path):
    database_path = str(tmp_path / "router-calibration-summary-events.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "intent": "practice",
            "learning_session_id": "request-run",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "run_summary_score": 0.86,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.82,
        },
    )
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-2",
            "intent": "practice",
            "learning_session_id": "request-run",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "run_summary_score": 0.81,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.79,
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "request-run",
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
        }
    )
    signal = RouterCalibrationSignalService(audit_store=audit_store).signal_for(
        student_id=request.student_id,
        request=request,
    )

    assert signal.signal == "positive"
    assert signal.source == "run_summary"
    assert signal.matched_run_count == 2
    assert signal.average_run_outcome_score is not None
    assert signal.average_run_outcome_score > 0.8


def test_router_calibration_signal_service_prefers_progress_profiles(tmp_path):
    database_path = str(tmp_path / "router-calibration-progress-profile.db")
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
            "average_run_outcome_score": 0.74,
            "average_run_confidence": 0.8,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "positive_run_rate": 0.5,
            "negative_run_rate": 0.0,
            "recent_average_run_outcome_score": 0.81,
            "prior_average_run_outcome_score": 0.66,
            "progress_delta": 0.15,
            "progress_signal": "improving",
        },
    )
    audit_store.append(
        event_type="learning.calibration.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": [],
            "average_run_outcome_score": 0.61,
            "average_run_confidence": 0.76,
            "matched_run_count": 3,
            "matched_session_count": 2,
            "positive_run_rate": 0.34,
            "negative_run_rate": 0.0,
            "profile_signal": "mixed",
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

    assert signal.source == "progress_profile"
    assert signal.signal == "mixed"
    assert signal.progress_signal == "improving"
    assert signal.progress_delta == 0.15
    assert signal.average_run_outcome_score == 0.74
