from __future__ import annotations

from uuid import uuid4

from dibble.models.assessment import (
    SocraticAssessmentEvaluation,
    SocraticAssessmentRequest,
    SocraticAssessmentResponse,
    SocraticAssessmentSession,
    SocraticEvidenceDimensions,
    SocraticEvidenceStrength,
    SocraticNextAction,
    SocraticPromptStyle,
)
from dibble.models.generation import AdaptiveRouteDecision
from dibble.models.profile import LearnerProfile, SignalLevel
from dibble.services.socratic_profile_update import SocraticProfileUpdater
from tests.support import build_profile


def build_assessment_response(student_id, *, evidence_strength, evidence_score, inferred_mastery, confidence_alignment):
    return SocraticAssessmentResponse(
        session_id="session-1",
        student_id=student_id,
        turn_id="turn-1",
        prompt="How would this work in another example?",
        prompt_style=SocraticPromptStyle.transfer_check,
        policy_rationale="Strong evidence supports transfer.",
        evaluation=SocraticAssessmentEvaluation(
            evidence_strength=evidence_strength,
            evidence_score=evidence_score,
            evidence_dimensions=SocraticEvidenceDimensions(
                lexical_alignment=0.78,
                reasoning_signal=0.74,
                confidence_alignment=confidence_alignment,
                progression_signal=0.68,
                misconception_risk=0.08,
            ),
            inferred_mastery=inferred_mastery,
            matched_terms=["equivalent", "fractions"],
            rationale="The learner gave a grounded explanation.",
            next_action=SocraticNextAction.advance,
        ),
        route=AdaptiveRouteDecision(
            intervention_type="reteach",
            delivery_mode="generated",
            scaffolding_level="medium",
            reasons=["test"],
        ),
    )


def test_socratic_profile_updater_updates_mastery_and_metacognition():
    student_id = uuid4()
    profile = LearnerProfile.model_validate(
        build_profile(
            student_id,
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.84},
            engagement="high",
            confidence_calibration=0.3,
            help_seeking="high",
            self_monitoring=0.35,
        )
    )
    updater = SocraticProfileUpdater()

    result = updater.apply(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            learner_response="Equivalent fractions are the same amount because the model covers equal space.",
            learner_confidence=0.9,
        ),
        build_assessment_response(
            student_id,
            evidence_strength=SocraticEvidenceStrength.demonstrated,
            evidence_score=0.79,
            inferred_mastery=0.9,
            confidence_alignment=0.93,
        ),
        SocraticAssessmentSession(
            session_id="session-1",
            student_id=student_id,
            target_kc_ids=["KC-1"],
        ),
    )

    assert result.applied is True
    assert result.kc_mastery_updates["KC-1"] > 0.84
    assert result.profile.metacognitive_state.confidence_calibration > 0.3
    assert result.profile.metacognitive_state.self_monitoring > 0.35
    assert result.profile.metacognitive_state.help_seeking in {SignalLevel.none, SignalLevel.low, SignalLevel.medium}


def test_socratic_profile_updater_uses_session_targets_on_followup_turns():
    student_id = uuid4()
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-1": 0.45}, frustration="low", total_load=0.2))
    updater = SocraticProfileUpdater()

    result = updater.apply(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            session_id="session-1",
            learner_response="Because both fraction models represent the same amount.",
            learner_confidence=0.72,
        ),
        build_assessment_response(
            student_id,
            evidence_strength=SocraticEvidenceStrength.demonstrated,
            evidence_score=0.73,
            inferred_mastery=0.81,
            confidence_alignment=0.84,
        ),
        SocraticAssessmentSession(
            session_id="session-1",
            student_id=student_id,
            target_kc_ids=["KC-1"],
        ),
    )

    assert result.applied is True
    assert result.kc_mastery_updates["KC-1"] > 0.45


def test_socratic_profile_updater_skips_updates_without_learner_response():
    student_id = uuid4()
    profile = LearnerProfile.model_validate(build_profile(student_id))
    updater = SocraticProfileUpdater()

    result = updater.apply(
        profile,
        SocraticAssessmentRequest(student_id=student_id, target_kc_ids=["KC-1"]),
        build_assessment_response(
            student_id,
            evidence_strength=SocraticEvidenceStrength.insufficient,
            evidence_score=0.0,
            inferred_mastery=0.0,
            confidence_alignment=0.5,
        ),
        SocraticAssessmentSession(session_id="session-1", student_id=student_id, target_kc_ids=["KC-1"]),
    )

    assert result.applied is False
    assert result.profile == profile
