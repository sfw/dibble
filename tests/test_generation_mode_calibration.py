from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.learning_state_profiles import LearnerStateSignalService
from dibble.services.learning_trait_profiles import LearnerTraitProfileSignalService
from dibble.services.learner_strategy_profiles import LearnerStrategySignalService
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.services.within_session_adaptation import WithinSessionAdaptationService
from dibble.services.within_session_controller_store import SQLiteWithinSessionControllerStore
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
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
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
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
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
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "progress_profile"
    assert calibrated_request.mode_calibration.progress_signal == "improving"
    assert calibrated_request.mode_calibration.support_bias == 1


def test_generation_mode_calibrator_can_use_strategy_profile_without_run_calibration(tmp_path):
    database_path = str(tmp_path / "generation-mode-strategy-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.strategy.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "average_run_outcome_score": 0.51,
            "average_run_confidence": 0.79,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "progress_signal": "declining",
            "progress_delta": -0.12,
            "strategy_signal": "support_intensive",
            "strategy_support_bias": -1,
            "strategy_recovery_focus": "prerequisite_rebuild",
            "strategy_trajectory_state": "relapsing",
            "strategy_recommended_next_action": "rebuild_prerequisite",
            "strategy_volatility_index": 0.0,
            "strategy_relapse_risk": 0.73,
            "strategy_rationale": "The learner has struggled across sessions and should step back before more independence.",
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
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "strategy_profile"
    assert calibrated_request.mode_calibration.signal == "negative"
    assert calibrated_request.mode_calibration.support_bias == -1
    assert calibrated_request.mode_calibration.strategy_signal == "support_intensive"
    assert calibrated_request.mode_calibration.strategy_trajectory_state == "relapsing"
    assert calibrated_request.mode_calibration.strategy_recommended_next_action == "rebuild_prerequisite"
    assert calibrated_request.mode_calibration.strategy_sequence_action == "hold_target"
    assert calibrated_request.mode_calibration.strategy_sequence_kc_ids == ["KC-1"]


def test_generation_mode_calibrator_exposes_transfer_sequence_for_independence_ready_strategy(tmp_path):
    database_path = str(tmp_path / "generation-mode-strategy-sequencing.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.strategy.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "explanation",
            "content_type": "micro_explanation",
            "target_kc_ids": ["KC-2"],
            "average_run_outcome_score": 0.82,
            "average_run_confidence": 0.77,
            "matched_run_count": 4,
            "matched_session_count": 3,
            "progress_signal": "improving",
            "progress_delta": 0.14,
            "strategy_signal": "independence_ready",
            "strategy_support_bias": 1,
            "strategy_recovery_focus": "independent_practice",
            "strategy_trajectory_state": "accelerating",
            "strategy_recommended_next_action": "check_transfer_readiness",
            "strategy_volatility_index": 0.0,
            "strategy_relapse_risk": 0.05,
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "target_kc_ids": ["KC-2"],
            "intent": "explanation",
            "requested_content_type": "micro_explanation",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.strategy_sequence_action == "attempt_transfer"
    assert calibrated_request.mode_calibration.strategy_sequence_primary_kc_id == "KC-2"


def test_generation_mode_calibrator_uses_durable_state_profile_when_other_signals_are_sparse(tmp_path):
    database_path = str(tmp_path / "generation-mode-state-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=student_id,
        payload={
            "intent": "practice",
            "content_type": "practice_problem",
            "target_kc_ids": ["KC-1"],
            "matched_run_count": 4,
            "matched_session_count": 3,
            "average_run_confidence": 0.74,
            "state_profile_signal": "support_needed",
            "total_load": 0.71,
            "confidence_calibration": 0.38,
            "help_seeking": "high",
            "load_reliability": 0.8,
            "overload_risk": 0.82,
            "metacognitive_reliability": 0.66,
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
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
        trait_profile_signal_service=LearnerTraitProfileSignalService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "state_profile"
    assert calibrated_request.mode_calibration.support_bias == -1
    assert calibrated_request.mode_calibration.state_profile_signal == "support_needed"
    assert calibrated_request.mode_calibration.state_profile_overload_risk == 0.82


def test_generation_mode_calibrator_surfaces_trait_profile_release_readiness(tmp_path):
    database_path = str(tmp_path / "generation-mode-trait-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=student_id,
        payload={
            "profile_signal": "stable",
            "trait_stability": 0.82,
            "challenge_tolerance": 0.74,
            "challenge_evidence_strength": 0.78,
            "processing_speed_reliability": 0.64,
            "working_memory_reliability": 0.76,
            "spatial_reasoning_reliability": 0.4,
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "target_kc_ids": ["KC-1"],
            "intent": "explanation",
            "requested_content_type": "worked_example",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
        state_signal_service=LearnerStateSignalService(audit_store=audit_store),
        trait_profile_signal_service=LearnerTraitProfileSignalService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.trait_profile_source == "trait_profile"
    assert calibrated_request.mode_calibration.trait_profile_trait_stability == 0.82
    assert calibrated_request.mode_calibration.trait_profile_challenge_tolerance == 0.74


def test_generation_mode_calibrator_uses_same_session_observation_to_raise_support(tmp_path):
    database_path = str(tmp_path / "generation-mode-session-negative.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-live",
            "target_kc_ids": ["KC-1"],
            "error_count": 3,
            "hints_used": 2,
            "support_level": "low",
            "frustration": "high",
            "total_load": 0.82,
            "confidence_calibration": 0.25,
            "help_seeking": "high",
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "session-live",
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "session_events"
    assert calibrated_request.mode_calibration.signal == "negative"
    assert calibrated_request.mode_calibration.support_bias == -1
    assert calibrated_request.mode_calibration.session_signal == "negative"
    assert calibrated_request.mode_calibration.sequence_action == "hold_target"


def test_generation_mode_calibrator_uses_same_session_assessment_to_attempt_transfer(tmp_path):
    database_path = str(tmp_path / "generation-mode-session-positive.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-live",
            "target_kc_ids": ["KC-2"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.83,
            "next_action": "advance",
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "session-live",
            "target_kc_ids": ["KC-2"],
            "intent": "explanation",
            "requested_content_type": "micro_explanation",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "session_events"
    assert calibrated_request.mode_calibration.signal == "positive"
    assert calibrated_request.mode_calibration.support_bias == 1
    assert calibrated_request.mode_calibration.session_signal == "positive"
    assert calibrated_request.mode_calibration.sequence_action == "attempt_transfer"
    assert calibrated_request.mode_calibration.session_latest_next_action == "advance"
    assert calibrated_request.mode_calibration.socratic_steering_action == "verify_transfer"


def test_generation_mode_calibrator_uses_persisted_session_controller_metadata(tmp_path):
    database_path = str(tmp_path / "generation-mode-session-controller.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    controller_store = SQLiteWithinSessionControllerStore(database_path)
    student_id = uuid4()
    service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=controller_store,
    )
    observation_payload = {
        "learning_session_id": "session-controller",
        "target_kc_ids": ["KC-3"],
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
        payload=observation_payload,
    )
    service.record_observation_event(student_id=student_id, event_payload=observation_payload)

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "session-controller",
            "target_kc_ids": ["KC-3"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=service,
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.source == "session_controller"
    assert calibrated_request.mode_calibration.sequence_source == "session_controller"
    assert calibrated_request.mode_calibration.session_phase == "stabilize"
    assert calibrated_request.mode_calibration.session_negative_streak == 1


def test_generation_mode_calibrator_carries_session_arc_loop_metadata(tmp_path):
    database_path = str(tmp_path / "generation-mode-session-loop-risk.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    controller_store = SQLiteWithinSessionControllerStore(database_path)
    student_id = uuid4()
    service = WithinSessionAdaptationService(
        audit_store=audit_store,
        controller_store=controller_store,
    )
    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "session-loop-risk",
            "target_kc_ids": ["KC-4"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
        }
    )
    observation_payload = {
        "learning_session_id": "session-loop-risk",
        "target_kc_ids": ["KC-4"],
        "error_count": 3,
        "hints_used": 2,
        "support_level": "low",
        "frustration": "high",
        "total_load": 0.84,
        "confidence_calibration": 0.24,
        "help_seeking": "high",
    }
    for _ in range(2):
        audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=str(student_id),
            payload=observation_payload,
        )
        service.record_observation_event(student_id=student_id, event_payload=observation_payload)
    service.record_generation_step(request=request, content_type="practice_problem", generation_id="gen-1")
    service.record_generation_step(request=request, content_type="practice_problem", generation_id="gen-2")

    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=service,
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.session_support_step_budget == 2
    assert calibrated_request.mode_calibration.session_support_steps_remaining == 0
    assert calibrated_request.mode_calibration.session_stuck_loop_risk == "high"
    assert calibrated_request.mode_calibration.session_arc_action == "reprobe_new_angle"
    assert "change representation" in calibrated_request.mode_calibration.rationale


def test_generation_mode_calibrator_carries_recent_socratic_prompt_metadata(tmp_path):
    database_path = str(tmp_path / "generation-mode-session-socratic-steering.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-steering",
            "target_kc_ids": ["KC-4"],
            "prompt_style": "scaffolded_step_back",
            "evidence_strength": "insufficient",
            "evidence_score": 0.24,
            "next_action": "step_back",
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "session-steering",
            "target_kc_ids": ["KC-4"],
            "intent": "explanation",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.session_latest_prompt_style == "scaffolded_step_back"
    assert calibrated_request.mode_calibration.session_latest_next_action == "step_back"
    assert calibrated_request.mode_calibration.session_latest_evidence_strength == "insufficient"
    assert calibrated_request.mode_calibration.socratic_steering_action == "repair_then_model"


def test_generation_mode_calibrator_carries_current_evidence_guardrail_from_session_observations(tmp_path):
    database_path = str(tmp_path / "generation-mode-session-current-evidence.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "session-live",
            "target_kc_ids": ["KC-1"],
            "error_count": 0,
            "hints_used": 2,
            "support_level": "high",
            "frustration": "low",
            "total_load": 0.42,
            "confidence_calibration": 0.66,
            "help_seeking": "medium",
            "current_evidence_signal": "support_dependence",
            "current_evidence_confidence": 0.78,
            "current_evidence_rationale": "Recent success still relies on heavy support.",
        },
    )

    request = GenerationRequest.model_validate(
        {
            "student_id": student_id,
            "learning_session_id": "session-live",
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
        }
    )
    calibrator = GenerationModeCalibrator(
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
        strategy_signal_service=LearnerStrategySignalService(audit_store=audit_store),
        within_session_adaptation_service=WithinSessionAdaptationService(audit_store=audit_store),
    )

    calibrated_request = calibrator.calibrate_request(request=request)

    assert calibrated_request.mode_calibration is not None
    assert calibrated_request.mode_calibration.current_evidence_signal == "support_dependence"
    assert calibrated_request.mode_calibration.current_evidence_confidence == 0.78
    assert calibrated_request.mode_calibration.support_bias == -1
