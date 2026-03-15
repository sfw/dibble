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
