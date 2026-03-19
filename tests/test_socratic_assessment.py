from dataclasses import dataclass
from uuid import uuid4

from dibble.models.assessment import SocraticAssessmentRequest
from dibble.models.generation import (
    AdaptiveRouteDecision,
    GeneratedBlock,
    GenerationMetadata,
    GenerationResponse,
    GroundingReference,
)
from dibble.models.profile import LearnerProfile
from dibble.services.socratic_assessment import SocraticAssessmentService
from dibble.services.socratic_evidence import SocraticEvidenceScorer
from dibble.services.socratic_policy import SocraticTurnPolicy
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore
from dibble.storage import ensure_database
from tests.support import build_profile


@dataclass
class FakeOutcome:
    outcome_id: str
    title: str
    strand_id: str
    knowledge_component_ids: list[str]
    description: str
    tags: list[str]


class FakeOutcomeStore:
    def list(self):
        return [
            FakeOutcome(
                outcome_id="CURR-1",
                title="Equivalent Fractions Foundations",
                strand_id="STRAND-1",
                knowledge_component_ids=["KC-1"],
                description="Equivalent fractions name the same amount with fraction models.",
                tags=["equivalent fractions", "fractions"],
            )
        ]

    def get(self, outcome_id: str):
        if outcome_id != "CURR-1":
            return None
        return FakeOutcome(
            outcome_id="CURR-1",
            title="Equivalent Fractions Foundations",
            strand_id="STRAND-1",
            knowledge_component_ids=["KC-1"],
            description="Equivalent fractions name the same amount with fraction models.",
            tags=["equivalent fractions", "fractions"],
        )


class FakeGenerationEngine:
    def __init__(self, response: GenerationResponse):
        self.response = response

    def generate(self, profile: LearnerProfile, request):
        return self.response


def build_service(tmp_path, response: GenerationResponse) -> SocraticAssessmentService:
    database_path = str(tmp_path / "socratic.db")
    ensure_database(database_path)
    return SocraticAssessmentService(
        generation_engine=FakeGenerationEngine(response),
        session_store=SQLiteSocraticSessionStore(database_path),
        evidence_scorer=SocraticEvidenceScorer(FakeOutcomeStore()),
        turn_policy=SocraticTurnPolicy(),
    )


def test_socratic_assessment_requests_probe_without_learner_response(tmp_path):
    student_id = uuid4()
    profile = LearnerProfile.model_validate(build_profile(student_id))
    response = GenerationResponse(
        student_id=student_id,
        route=AdaptiveRouteDecision(
            intervention_type="reteach",
            delivery_mode="generated",
            scaffolding_level="medium",
            reasons=["test"],
        ),
        blocks=[
            GeneratedBlock(
                kind="summary", title="Focus", body="Equivalent fractions matter."
            ),
            GeneratedBlock(
                kind="instruction",
                title="Think aloud",
                body="How do you know 1/2 and 2/4 are equal?",
            ),
        ],
        curriculum_context=["Equivalent fractions"],
        grounding=[
            GroundingReference(
                outcome_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=0.9,
                matched_terms=["equivalent", "fractions"],
            )
        ],
        safety_notes=[],
        generation_id="gen-1",
        generation_metadata=GenerationMetadata(
            prompt_template_name="assessment_probe.baseline"
        ),
    )
    service = build_service(tmp_path, response)

    result = service.assess(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            curriculum_context=["Equivalent fractions"],
        ),
    )

    assert result.prompt == "How do you know 1/2 and 2/4 are equal?"
    assert result.prompt_style.value == "diagnostic"
    assert result.evaluation.next_action.value == "ask_probe"
    assert result.evaluation.evidence_score == 0.0
    assert result.session_id is not None
    assert len(result.conversation_history) == 1
    assert result.summary.latest_prompt_style == "diagnostic"
    assert result.summary.next_step.content_type == "assessment_probe"


def test_socratic_assessment_advances_when_response_is_grounded(tmp_path):
    student_id = uuid4()
    profile = LearnerProfile.model_validate(build_profile(student_id))
    response = GenerationResponse(
        student_id=student_id,
        route=AdaptiveRouteDecision(
            intervention_type="reteach",
            delivery_mode="generated",
            scaffolding_level="medium",
            reasons=["test"],
        ),
        blocks=[
            GeneratedBlock(
                kind="summary", title="Focus", body="Equivalent fractions matter."
            ),
            GeneratedBlock(
                kind="instruction",
                title="Think aloud",
                body="Why are 1/2 and 2/4 the same amount?",
            ),
        ],
        curriculum_context=["Equivalent fractions"],
        grounding=[
            GroundingReference(
                outcome_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=0.9,
                matched_terms=["equivalent", "fractions", "same", "amount"],
            )
        ],
        safety_notes=[],
        generation_id="gen-2",
        generation_metadata=GenerationMetadata(
            prompt_template_name="assessment_probe.baseline"
        ),
    )
    service = build_service(tmp_path, response)

    result = service.assess(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            curriculum_context=["Equivalent fractions"],
            learner_response="They are equivalent fractions because they show the same amount on the model.",
        ),
    )

    assert result.evaluation.evidence_strength.value == "demonstrated"
    assert result.evaluation.next_action.value == "advance"
    assert result.prompt_style.value == "transfer_check"
    assert result.evaluation.evidence_score >= 0.62
    assert result.summary.status == "ready_for_follow_up"
    assert result.summary.next_step.content_type == "practice_problem"
    assert "equivalent" in result.evaluation.matched_terms


def test_socratic_assessment_reuses_persisted_session_history(tmp_path):
    student_id = uuid4()
    profile = LearnerProfile.model_validate(build_profile(student_id))
    response = GenerationResponse(
        student_id=student_id,
        route=AdaptiveRouteDecision(
            intervention_type="reteach",
            delivery_mode="generated",
            scaffolding_level="medium",
            reasons=["test"],
        ),
        blocks=[
            GeneratedBlock(
                kind="summary", title="Focus", body="Equivalent fractions matter."
            ),
            GeneratedBlock(
                kind="instruction",
                title="Think aloud",
                body="Why are 1/2 and 2/4 the same amount?",
            ),
        ],
        curriculum_context=["Equivalent fractions"],
        grounding=[
            GroundingReference(
                outcome_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=0.9,
                matched_terms=["equivalent", "fractions", "same", "amount"],
            )
        ],
        safety_notes=[],
        generation_id="gen-3",
        generation_metadata=GenerationMetadata(
            prompt_template_name="assessment_probe.baseline"
        ),
    )
    service = build_service(tmp_path, response)

    first_result = service.assess(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            curriculum_context=["Equivalent fractions"],
        ),
    )
    second_result = service.assess(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            session_id=first_result.session_id,
            learner_response="They are equivalent fractions because both models cover the same amount.",
        ),
    )
    stored_session = service.get_session(first_result.session_id)

    assert second_result.session_id == first_result.session_id
    assert len(second_result.conversation_history) >= 3
    assert stored_session is not None
    assert len(stored_session.turns) == 2
    assert stored_session.summary.turn_count == 2
    assert stored_session.summary.latest_next_action == "advance"

    third_result = service.assess(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            session_id=first_result.session_id,
        ),
    )

    assert third_result.prompt_style.value == "transfer_check"
    assert stored_session.turns[0].prompt_style.value == "diagnostic"
