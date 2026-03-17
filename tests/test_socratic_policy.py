from __future__ import annotations

from uuid import uuid4

from dibble.models.assessment import (
    SocraticAssessmentEvaluation,
    SocraticAssessmentRequest,
    SocraticAssessmentSession,
    SocraticEvidenceDimensions,
    SocraticEvidenceStrength,
    SocraticNextAction,
    SocraticPromptStyle,
    SocraticSteeringAction,
    SocraticTurnRecord,
)
from dibble.services.socratic_policy import SocraticTurnPolicy


def test_socratic_policy_starts_with_diagnostic_probe():
    student_id = uuid4()
    policy = SocraticTurnPolicy()
    session = SocraticAssessmentSession(session_id="session-1", student_id=student_id)
    evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.insufficient,
        inferred_mastery=0.0,
        rationale="No learner response yet.",
        next_action=SocraticNextAction.ask_probe,
    )

    decision = policy.decide(
        session,
        SocraticAssessmentRequest(student_id=student_id),
        evaluation,
    )

    assert decision.prompt_style == SocraticPromptStyle.diagnostic
    assert decision.steering_action == SocraticSteeringAction.open_probe


def test_socratic_policy_steps_back_after_repeated_low_signal_turns():
    student_id = uuid4()
    policy = SocraticTurnPolicy()
    weak_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.insufficient,
        evidence_dimensions=SocraticEvidenceDimensions(misconception_risk=0.52),
        inferred_mastery=0.24,
        rationale="Weak evidence.",
        next_action=SocraticNextAction.step_back,
    )
    session = SocraticAssessmentSession(
        session_id="session-2",
        student_id=student_id,
        turns=[
            SocraticTurnRecord(
                turn_id="turn-1",
                prompt="Why does that work?",
                prompt_style=SocraticPromptStyle.diagnostic,
                policy_rationale="Probe.",
                learner_response="I guess the top changes.",
                evaluation=weak_evaluation,
            ),
            SocraticTurnRecord(
                turn_id="turn-2",
                prompt="Can you say more?",
                prompt_style=SocraticPromptStyle.clarification,
                policy_rationale="Clarify.",
                learner_response="Not sure.",
                evaluation=weak_evaluation,
            ),
        ],
    )

    decision = policy.decide(
        session,
        SocraticAssessmentRequest(student_id=student_id),
        weak_evaluation,
    )

    assert decision.prompt_style == SocraticPromptStyle.scaffolded_step_back
    assert decision.steering_action == SocraticSteeringAction.repair_then_model


def test_socratic_policy_advances_to_transfer_when_evidence_is_demonstrated():
    student_id = uuid4()
    policy = SocraticTurnPolicy()
    session = SocraticAssessmentSession(session_id="session-3", student_id=student_id)
    strong_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.demonstrated,
        evidence_score=0.78,
        evidence_dimensions=SocraticEvidenceDimensions(
            lexical_alignment=0.8,
            reasoning_signal=0.7,
            confidence_alignment=0.9,
            progression_signal=0.6,
            misconception_risk=0.12,
        ),
        inferred_mastery=0.79,
        rationale="Grounded reasoning is present.",
        next_action=SocraticNextAction.advance,
    )

    decision = policy.decide(
        session,
        SocraticAssessmentRequest(
            student_id=student_id,
            learner_response="They are equivalent because the model shows the same amount.",
            learner_confidence=0.75,
        ),
        strong_evaluation,
    )

    assert decision.prompt_style == SocraticPromptStyle.transfer_check
    assert decision.steering_action == SocraticSteeringAction.verify_transfer


def test_socratic_policy_uses_clarification_after_recovery_from_step_back():
    student_id = uuid4()
    policy = SocraticTurnPolicy()
    prior_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.insufficient,
        evidence_score=0.22,
        evidence_dimensions=SocraticEvidenceDimensions(misconception_risk=0.62),
        inferred_mastery=0.21,
        rationale="Needed prerequisite repair.",
        next_action=SocraticNextAction.step_back,
    )
    current_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.demonstrated,
        evidence_score=0.74,
        evidence_dimensions=SocraticEvidenceDimensions(
            lexical_alignment=0.72,
            reasoning_signal=0.61,
            confidence_alignment=0.42,
            progression_signal=0.48,
            misconception_risk=0.18,
        ),
        inferred_mastery=0.71,
        rationale="The learner recovered but still sounds tentative.",
        next_action=SocraticNextAction.advance,
    )
    session = SocraticAssessmentSession(
        session_id="session-4",
        student_id=student_id,
        turns=[
            SocraticTurnRecord(
                turn_id="turn-1",
                prompt="What does the denominator count?",
                prompt_style=SocraticPromptStyle.scaffolded_step_back,
                policy_rationale="Step back.",
                learner_response="It counts the equal parts.",
                evaluation=prior_evaluation,
            )
        ],
    )

    decision = policy.decide(
        session,
        SocraticAssessmentRequest(
            student_id=student_id,
            learner_response="It counts the equal parts, but I am not fully sure.",
            learner_confidence=0.41,
        ),
        current_evaluation,
    )

    assert decision.prompt_style == SocraticPromptStyle.clarification
    assert decision.steering_action == SocraticSteeringAction.restate_then_apply
    assert decision.steering_action == SocraticSteeringAction.restate_then_apply


def test_socratic_policy_clarifies_after_failed_transfer_check_when_gap_is_narrow():
    student_id = uuid4()
    policy = SocraticTurnPolicy()
    transfer_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.demonstrated,
        evidence_score=0.8,
        evidence_dimensions=SocraticEvidenceDimensions(misconception_risk=0.12),
        inferred_mastery=0.79,
        rationale="Strong transfer attempt.",
        next_action=SocraticNextAction.advance,
    )
    current_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.insufficient,
        evidence_score=0.33,
        evidence_dimensions=SocraticEvidenceDimensions(
            lexical_alignment=0.3,
            reasoning_signal=0.36,
            confidence_alignment=0.5,
            progression_signal=0.38,
            misconception_risk=0.22,
        ),
        inferred_mastery=0.41,
        rationale="The transfer failed, but the misunderstanding looks narrow.",
        next_action=SocraticNextAction.clarify,
    )
    session = SocraticAssessmentSession(
        session_id="session-5",
        student_id=student_id,
        turns=[
            SocraticTurnRecord(
                turn_id="turn-1",
                prompt="How would this work with 3/6 and 1/2?",
                prompt_style=SocraticPromptStyle.transfer_check,
                policy_rationale="Check transfer.",
                learner_response="I think they are the same.",
                evaluation=transfer_evaluation,
            )
        ],
    )

    decision = policy.decide(
        session,
        SocraticAssessmentRequest(
            student_id=student_id,
            learner_response="I think it is the same but I cannot explain why.",
        ),
        current_evaluation,
    )

    assert decision.prompt_style == SocraticPromptStyle.clarification


def test_socratic_policy_reprobes_from_new_angle_when_clarification_loops():
    student_id = uuid4()
    policy = SocraticTurnPolicy()
    prior_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.emerging,
        evidence_score=0.46,
        evidence_dimensions=SocraticEvidenceDimensions(
            lexical_alignment=0.44,
            reasoning_signal=0.42,
            confidence_alignment=0.48,
            progression_signal=0.4,
            misconception_risk=0.28,
        ),
        inferred_mastery=0.48,
        rationale="Partially correct but still vague.",
        next_action=SocraticNextAction.clarify,
    )
    current_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.emerging,
        evidence_score=0.45,
        evidence_dimensions=SocraticEvidenceDimensions(
            lexical_alignment=0.43,
            reasoning_signal=0.41,
            confidence_alignment=0.5,
            progression_signal=0.42,
            misconception_risk=0.26,
        ),
        inferred_mastery=0.5,
        rationale="Still circling the same gap.",
        next_action=SocraticNextAction.clarify,
    )
    session = SocraticAssessmentSession(
        session_id="session-clarification-loop",
        student_id=student_id,
        turns=[
            SocraticTurnRecord(
                turn_id="turn-1",
                prompt="Can you say why those fractions match?",
                prompt_style=SocraticPromptStyle.clarification,
                policy_rationale="Clarify the explanation.",
                learner_response="Because they both change the same way.",
                evaluation=prior_evaluation,
            ),
            SocraticTurnRecord(
                turn_id="turn-2",
                prompt="What exactly stays the same?",
                prompt_style=SocraticPromptStyle.clarification,
                policy_rationale="Clarify again.",
                learner_response="The amount stays the same, I think.",
                evaluation=prior_evaluation,
            ),
        ],
    )

    decision = policy.decide(
        session,
        SocraticAssessmentRequest(
            student_id=student_id,
            learner_response="The amount stays the same, but I still cannot explain it clearly.",
            learner_confidence=0.48,
        ),
        current_evaluation,
    )

    assert decision.prompt_style == SocraticPromptStyle.diagnostic
    assert decision.steering_action == SocraticSteeringAction.probe_from_new_angle
