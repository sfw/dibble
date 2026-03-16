from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationModeCalibration,
    GenerationRequest,
    InterventionType,
    RequestedContentType,
    TargetKcGenerationHint,
)
from dibble.models.profile import LearnerProfile
from dibble.services.generation_modes import build_generation_mode_plan
from tests.support import build_profile


def test_generation_mode_plan_assigns_support_difficulty_for_low_mastery():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.3,
            kc_mastery={"KC-1": 0.2},
            engagement="medium",
        )
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="practice")
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.practice_problem
    assert plan.request_context["selection_mode"] == "intent_default"
    assert plan.request_context["requested_content_type"] is None
    assert plan.request_context["selected_content_type"] == "practice_problem"
    assert plan.request_context["difficulty_band"] == "support"
    assert "support difficulty" in plan.prompt_guidance


def test_generation_mode_plan_assigns_completion_fading_for_worked_examples():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.45,
            kc_mastery={"KC-1": 0.55},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        requested_content_type="worked_example",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.worked_example
    assert plan.request_context["selection_mode"] == "explicit"
    assert plan.request_context["requested_content_type"] == "worked_example"
    assert plan.request_context["selected_content_type"] == "worked_example"
    assert plan.request_context["fading_strategy"] == "completion"
    assert plan.request_context["worked_steps_visible"] == 2
    assert "final step" in plan.prompt_guidance


def test_generation_mode_plan_auto_selects_worked_example_for_high_help_seeking():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.35,
            kc_mastery={"KC-1": 0.58},
            engagement="medium",
            confidence_calibration=0.3,
            help_seeking="high",
        )
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="explanation")
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.worked_example
    assert plan.request_context["selection_mode"] == "adaptive"
    assert plan.request_context["requested_content_type"] is None
    assert plan.request_context["selected_content_type"] == "worked_example"
    assert "selection_rationale" in plan.request_context


def test_generation_mode_plan_uses_recent_socratic_step_back_to_select_worked_example():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.32,
            kc_mastery={"KC-1": 0.63},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        learning_session_id="session-socratic-step-back",
        target_kc_ids=["KC-1"],
        intent="explanation",
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="session_controller",
            confidence=0.8,
            support_bias=-1,
            session_signal="negative",
            session_source="session_controller",
            session_confidence=0.8,
            session_support_bias=-1,
            session_assessment_count=1,
            session_phase="repair",
            session_recovery_intent="increase_support",
            session_latest_prompt_style="scaffolded_step_back",
            session_latest_next_action="step_back",
            session_latest_evidence_strength="insufficient",
            socratic_steering_action="repair_then_model",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.worked_example
    assert plan.request_context["selection_mode"] == "socratic_follow_up"
    assert plan.request_context["socratic_follow_up"]["action"] == "repair_then_model"
    assert "selection_rationale" in plan.request_context


def test_generation_mode_plan_uses_recent_socratic_transfer_to_select_practice():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.28,
            kc_mastery={"KC-1": 0.74},
            engagement="high",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        learning_session_id="session-socratic-transfer",
        target_kc_ids=["KC-1"],
        intent="explanation",
        mode_calibration=GenerationModeCalibration(
            signal="positive",
            source="session_controller",
            confidence=0.83,
            support_bias=1,
            session_signal="positive",
            session_source="session_controller",
            session_confidence=0.83,
            session_support_bias=1,
            session_assessment_count=1,
            session_phase="transfer_check",
            session_recovery_intent="check_transfer",
            session_latest_prompt_style="transfer_check",
            session_latest_next_action="advance",
            session_latest_evidence_strength="demonstrated",
            socratic_steering_action="verify_transfer",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="low",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.practice_problem
    assert plan.request_context["selection_mode"] == "socratic_follow_up"
    assert plan.request_context["socratic_follow_up"]["action"] == "verify_transfer"
    assert "selection_rationale" in plan.request_context


def test_generation_mode_plan_uses_bridge_arc_to_select_guided_practice():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.34,
            kc_mastery={"KC-1": 0.68},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        learning_session_id="session-bridge-arc",
        target_kc_ids=["KC-1"],
        intent="explanation",
        mode_calibration=GenerationModeCalibration(
            signal="recovering",
            source="session_controller",
            confidence=0.76,
            support_bias=0,
            session_signal="recovering",
            session_source="session_controller",
            session_confidence=0.76,
            session_support_bias=0,
            session_assessment_count=2,
            session_phase="bridge",
            session_recovery_intent="bridge_target",
            session_support_step_budget=1,
            session_support_steps_remaining=1,
            session_arc_action="bridge_with_target",
            session_latest_prompt_style="clarification",
            session_latest_next_action="advance",
            session_latest_evidence_strength="emerging",
            socratic_steering_action="clarify_then_check",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == RequestedContentType.practice_problem
    assert plan.request_context["selection_mode"] == "session_arc"
    assert plan.request_context["session_adaptation"]["arc_action"] == "bridge_with_target"
    assert "guided bridge" in plan.prompt_guidance


def test_generation_mode_plan_assigns_independent_fading_for_stable_high_mastery_worked_example():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.3,
            kc_mastery={"KC-1": 0.88},
            engagement="high",
            confidence_calibration=0.82,
            help_seeking="low",
            self_monitoring=0.82,
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        requested_content_type="worked_example",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.stretch,
        delivery_mode=DeliveryMode.blended,
        scaffolding_level="low",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["fading_strategy"] == "independent"
    assert plan.request_context["worked_steps_visible"] == 1


def test_generation_mode_plan_uses_positive_mode_calibration_to_raise_practice_difficulty():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.3,
            kc_mastery={"KC-1": 0.2},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
        mode_calibration=GenerationModeCalibration(
            signal="positive",
            source="profile",
            confidence=0.78,
            matched_run_count=4,
            average_run_outcome_score=0.84,
            support_bias=1,
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["difficulty_band"] == "on_grade"
    assert plan.request_context["mode_calibration"]["support_bias"] == 1
    assert plan.request_context["mode_calibration_applied"] is True
    assert "on_grade difficulty" in plan.prompt_guidance


def test_generation_mode_plan_uses_negative_mode_calibration_to_increase_worked_example_support():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.45,
            kc_mastery={"KC-1": 0.55},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        requested_content_type="worked_example",
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="run_summary",
            confidence=0.81,
            matched_run_count=2,
            average_run_outcome_score=0.34,
            support_bias=-1,
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["fading_strategy"] == "full"
    assert plan.request_context["worked_steps_visible"] == 3
    assert plan.request_context["mode_calibration"]["source"] == "run_summary"
    assert plan.request_context["mode_calibration_applied"] is True


def test_generation_mode_plan_surfaces_session_controller_metadata():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.35,
            kc_mastery={"KC-1": 0.55},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        learning_session_id="session-controller",
        target_kc_ids=["KC-1"],
        intent="practice",
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="session_controller",
            confidence=0.82,
            support_bias=-1,
            sequence_action="hold_target",
            sequence_primary_kc_id="KC-1",
            sequence_kc_ids=["KC-1"],
            sequence_source="session_controller",
            session_signal="negative",
            session_source="session_controller",
            session_confidence=0.82,
            session_support_bias=-1,
            session_sequence_action="hold_target",
            session_primary_kc_id="KC-1",
            session_observation_count=2,
            session_assessment_count=0,
            session_phase="repair",
            session_recovery_intent="increase_support",
            session_generated_step_count=1,
            session_positive_streak=0,
            session_negative_streak=2,
            session_rationale="Controller is holding the repair target.",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["session_adaptation"]["source"] == "session_controller"
    assert plan.request_context["session_adaptation"]["phase"] == "repair"
    assert plan.request_context["session_adaptation"]["support_step_budget"] == 0
    assert plan.request_context["session_adaptation"]["generated_step_count"] == 1
    assert plan.request_context["session_adaptation"]["negative_streak"] == 2


def test_generation_mode_plan_holds_support_practice_during_repair_phase():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.25,
            kc_mastery={"KC-1": 0.72},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="session_controller",
            confidence=0.8,
            support_bias=1,
            session_signal="negative",
            session_source="session_controller",
            session_phase="repair",
            session_recovery_intent="increase_support",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["difficulty_band"] == "support"
    assert plan.request_context["difficulty_progression_action"] == "repair_rebuild"
    assert plan.request_context["practice_distractor_style"] == "misconception_contrast"
    assert "repair rebuild" in plan.prompt_guidance


def test_generation_mode_plan_surfaces_loop_risk_in_session_context():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="medium",
            total_load=0.46,
            kc_mastery={"KC-1": 0.49},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        learning_session_id="session-loop-risk",
        target_kc_ids=["KC-1"],
        intent="practice",
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="session_controller",
            confidence=0.71,
            support_bias=-1,
            session_signal="negative",
            session_source="session_controller",
            session_confidence=0.71,
            session_support_bias=-1,
            session_assessment_count=1,
            session_phase="repair",
            session_recovery_intent="increase_support",
            session_support_step_budget=2,
            session_support_steps_remaining=0,
            session_stuck_loop_risk="high",
            session_arc_action="reprobe_new_angle",
            session_latest_prompt_style="clarification",
            session_latest_next_action="clarify",
            session_latest_evidence_strength="emerging",
            socratic_steering_action="clarify_then_check",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["session_adaptation"]["stuck_loop_risk"] == "high"
    assert plan.request_context["session_adaptation"]["support_steps_remaining"] == 0
    assert plan.request_context["socratic_follow_up"]["arc_action"] == "reprobe_new_angle"
    assert "Change the representation" in plan.prompt_guidance


def test_generation_mode_plan_uses_target_kc_misconceptions_to_focus_distractors():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.25,
            kc_mastery={"KC-1": 0.44},
            engagement="medium",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
        target_kc_hints=[
            TargetKcGenerationHint(
                kc_id="KC-1",
                kc_name="Generate equivalent fractions",
                misconception_ids=["fraction-whole-number-bias"],
                misconception_labels=["Whole-number bias"],
                remediation_hints=["Compare the total amount before comparing the parts."],
            )
        ],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert "Whole-number bias" in plan.request_context["practice_distractor_focus"]
    assert "misconception_mirror" in plan.request_context["practice_distractor_slots"][0]
    assert "avoids Whole-number bias" in plan.request_context["practice_answer_check_focus"]
    assert plan.request_context["practice_distractor_misconception_ids"] == ["fraction-whole-number-bias"]
    assert (
        plan.request_context["practice_distractor_remediation_hint"]
        == "Compare the total amount before comparing the parts."
    )
    assert "Whole-number bias" in plan.prompt_guidance
    assert "Distractor slots:" in plan.prompt_guidance
    assert "Compare the total amount before comparing the parts." in plan.prompt_guidance


def test_generation_mode_plan_uses_bridge_progression_for_worked_examples():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.3,
            kc_mastery={"KC-1": 0.78},
            engagement="high",
            confidence_calibration=0.78,
            help_seeking="low",
            self_monitoring=0.8,
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        requested_content_type="worked_example",
        mode_calibration=GenerationModeCalibration(
            signal="recovering",
            source="session_controller",
            confidence=0.81,
            support_bias=0,
            session_signal="recovering",
            session_source="session_controller",
            session_phase="bridge",
            session_recovery_intent="bridge_target",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["fading_strategy"] == "completion"
    assert plan.request_context["worked_example_progression_action"] == "bridge_release"
    assert plan.request_context["worked_example_fade_focus"] == "a near-target example with the transfer move left unfinished"
    assert "worked bridge" in plan.request_context["worked_example_step_outline"][1]
    assert "learner sees how the example returns" in plan.request_context["worked_example_learner_release"]
    assert "near-target example" in plan.prompt_guidance


def test_generation_mode_plan_names_visible_and_hidden_worked_example_roles():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.28,
            kc_mastery={"KC-1": 0.83},
            engagement="high",
            confidence_calibration=0.8,
            help_seeking="low",
            self_monitoring=0.82,
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        requested_content_type="worked_example",
        target_kc_hints=[
            TargetKcGenerationHint(
                kc_id="KC-1",
                kc_name="Generate equivalent fractions",
                nearby_kc_names=["Compare equivalent fractions"],
            )
        ],
        mode_calibration=GenerationModeCalibration(
            signal="positive",
            source="session_controller",
            confidence=0.84,
            support_bias=1,
            session_signal="positive",
            session_source="session_controller",
            session_phase="transfer_check",
            session_recovery_intent="check_transfer",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.stretch,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="low",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["worked_example_visible_step_roles"] == ["cue"]
    assert plan.request_context["worked_example_hidden_step_role"] == "independent application"
    assert (
        plan.request_context["worked_example_transfer_move"]
        == "apply Generate equivalent fractions in Compare equivalent fractions"
    )
    assert "cue: give only the lightest setup needed" in plan.request_context["worked_example_step_outline"][0]
    assert "independent application" in plan.request_context["worked_example_learner_release"]
    assert "visible step roles (cue)" in plan.prompt_guidance
    assert "independent application" in plan.prompt_guidance
    assert "Use this step outline:" in plan.prompt_guidance


def test_generation_mode_plan_advances_practice_after_improving_progress():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.28,
            kc_mastery={"KC-1": 0.64},
            engagement="high",
        )
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
        mode_calibration=GenerationModeCalibration(
            signal="positive",
            source="progress_profile",
            confidence=0.82,
            support_bias=1,
            progress_signal="improving",
            strategy_trajectory_state="accelerating",
            rationale="test",
        ),
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="low",
        reasons=["test"],
    )

    plan = build_generation_mode_plan(profile, request, route)

    assert plan.request_context["difficulty_band"] == "stretch"
    assert plan.request_context["difficulty_progression_action"] == "advance_after_improvement"
    assert plan.request_context["practice_distractor_style"] == "near_transfer"
