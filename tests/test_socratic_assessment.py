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
from tests.support import build_profile


@dataclass
class FakeCurriculumResource:
    resource_id: str
    title: str
    body: str
    tags: list[str]


class FakeCurriculumStore:
    def get(self, resource_id: str):
        if resource_id != "CURR-1":
            return None
        return FakeCurriculumResource(
            resource_id="CURR-1",
            title="Equivalent Fractions Foundations",
            body="Equivalent fractions name the same amount with fraction models.",
            tags=["equivalent fractions", "fractions"],
        )


class FakeGenerationEngine:
    def __init__(self, response: GenerationResponse):
        self.response = response

    def generate(self, profile: LearnerProfile, request):
        return self.response


def test_socratic_assessment_requests_probe_without_learner_response():
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
            GeneratedBlock(kind="summary", title="Focus", body="Equivalent fractions matter."),
            GeneratedBlock(kind="instruction", title="Think aloud", body="How do you know 1/2 and 2/4 are equal?"),
        ],
        curriculum_context=["Equivalent fractions"],
        grounding=[
            GroundingReference(
                resource_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=0.9,
                matched_terms=["equivalent", "fractions"],
            )
        ],
        safety_notes=[],
        generation_id="gen-1",
        generation_metadata=GenerationMetadata(prompt_template_name="assessment_probe.baseline"),
    )
    service = SocraticAssessmentService(
        generation_engine=FakeGenerationEngine(response),
        curriculum_store=FakeCurriculumStore(),
    )

    result = service.assess(
        profile,
        SocraticAssessmentRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            curriculum_context=["Equivalent fractions"],
        ),
    )

    assert result.prompt == "How do you know 1/2 and 2/4 are equal?"
    assert result.evaluation.next_action.value == "ask_probe"


def test_socratic_assessment_advances_when_response_is_grounded():
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
            GeneratedBlock(kind="summary", title="Focus", body="Equivalent fractions matter."),
            GeneratedBlock(kind="instruction", title="Think aloud", body="Why are 1/2 and 2/4 the same amount?"),
        ],
        curriculum_context=["Equivalent fractions"],
        grounding=[
            GroundingReference(
                resource_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=0.9,
                matched_terms=["equivalent", "fractions", "same", "amount"],
            )
        ],
        safety_notes=[],
        generation_id="gen-2",
        generation_metadata=GenerationMetadata(prompt_template_name="assessment_probe.baseline"),
    )
    service = SocraticAssessmentService(
        generation_engine=FakeGenerationEngine(response),
        curriculum_store=FakeCurriculumStore(),
    )

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
    assert "equivalent" in result.evaluation.matched_terms
