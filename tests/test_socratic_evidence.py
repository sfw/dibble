from __future__ import annotations

from uuid import uuid4

from dibble.models.assessment import (
    SocraticAssessmentEvaluation,
    SocraticAssessmentRequest,
    SocraticAssessmentSession,
    SocraticEvidenceStrength,
    SocraticMessage,
    SocraticMessageRole,
    SocraticNextAction,
    SocraticPromptStyle,
    SocraticTurnRecord,
)
from dibble.models.curriculum import CurriculumResource
from dibble.services.socratic_evidence import SocraticEvidenceScorer


class FakeCurriculumStore:
    def list(self) -> list[CurriculumResource]:
        return [
            CurriculumResource(
                resource_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                subject="math",
                learning_objective_ids=["LO-1"],
                knowledge_component_ids=["KC-1"],
                tags=["fractions", "equivalent fractions"],
                body="Use visual fraction models to explain why equivalent fractions name the same amount.",
            )
        ]


def test_socratic_evidence_scores_grounded_reasoning_as_demonstrated():
    student_id = uuid4()
    scorer = SocraticEvidenceScorer(FakeCurriculumStore())
    session = SocraticAssessmentSession(
        session_id="session-1",
        student_id=student_id,
        target_kc_ids=["KC-1"],
        target_lo_ids=["LO-1"],
        curriculum_context=["Equivalent fractions"],
        conversation_history=[
            SocraticMessage(role=SocraticMessageRole.tutor, text="How do you know 1/2 and 2/4 are equal?")
        ],
    )

    evaluation = scorer.evaluate(
        session,
        SocraticAssessmentRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            target_lo_ids=["LO-1"],
            curriculum_context=["Equivalent fractions"],
            learner_response="They are equivalent fractions because both models show the same amount.",
            learner_confidence=0.72,
        ),
    )

    assert evaluation.evidence_strength == SocraticEvidenceStrength.demonstrated
    assert evaluation.evidence_score >= 0.62
    assert evaluation.next_action == SocraticNextAction.advance
    assert evaluation.evidence_dimensions.lexical_alignment >= 0.6
    assert evaluation.evidence_dimensions.reasoning_signal >= 0.45
    assert "equivalent" in evaluation.matched_terms


def test_socratic_evidence_steps_back_on_overconfident_thin_response():
    student_id = uuid4()
    scorer = SocraticEvidenceScorer(FakeCurriculumStore())
    session = SocraticAssessmentSession(
        session_id="session-2",
        student_id=student_id,
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )

    evaluation = scorer.evaluate(
        session,
        SocraticAssessmentRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            curriculum_context=["Equivalent fractions"],
            learner_response="Just the top numbers. I am sure.",
            learner_confidence=0.95,
        ),
    )

    assert evaluation.evidence_strength == SocraticEvidenceStrength.insufficient
    assert evaluation.next_action == SocraticNextAction.step_back
    assert evaluation.evidence_dimensions.misconception_risk >= 0.45
    assert evaluation.evidence_dimensions.confidence_alignment < 0.5


def test_socratic_evidence_tracks_progress_against_recent_turns():
    student_id = uuid4()
    scorer = SocraticEvidenceScorer(FakeCurriculumStore())
    prior_evaluation = SocraticAssessmentEvaluation(
        evidence_strength=SocraticEvidenceStrength.insufficient,
        inferred_mastery=0.22,
        rationale="Earlier response stayed shallow.",
        next_action=SocraticNextAction.step_back,
    )
    session = SocraticAssessmentSession(
        session_id="session-3",
        student_id=student_id,
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
        conversation_history=[
            SocraticMessage(role=SocraticMessageRole.tutor, text="What makes these fractions equal?")
        ],
        turns=[
            SocraticTurnRecord(
                turn_id="turn-1",
                prompt="What makes these fractions equal?",
                prompt_style=SocraticPromptStyle.diagnostic,
                policy_rationale="Initial probe.",
                learner_response="I don't know.",
                evaluation=prior_evaluation,
            )
        ],
    )

    evaluation = scorer.evaluate(
        session,
        SocraticAssessmentRequest(
            student_id=student_id,
            session_id="session-3",
            learner_response="Equivalent fractions mean the same amount because the model covers equal space.",
            learner_confidence=0.7,
        ),
    )

    assert evaluation.evidence_strength in {
        SocraticEvidenceStrength.emerging,
        SocraticEvidenceStrength.demonstrated,
    }
    assert evaluation.evidence_dimensions.progression_signal > 0.5
    assert evaluation.inferred_mastery > prior_evaluation.inferred_mastery
