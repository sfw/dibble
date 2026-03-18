from uuid import uuid4

from dibble.models.generation import (
    DeliveryMode,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationResponse,
    InterventionType,
    AdaptiveRouteDecision,
)


def test_generation_response_populates_text_artifacts_from_blocks():
    response = GenerationResponse(
        student_id=uuid4(),
        route=AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["test"],
        ),
        blocks=[
            GeneratedBlock(
                kind="summary",
                title="Learning focus",
                body="Equivalent fractions name the same amount.",
            ),
            GeneratedBlock(
                kind="instruction", title="Try it", body="Explain why 1/2 equals 2/4."
            ),
        ],
        curriculum_context=["Equivalent fractions"],
        safety_notes=[],
    )

    assert [
        artifact["artifact_type"]
        for artifact in response.model_dump(mode="json")["artifacts"]
    ] == ["text", "text"]
    assert response.artifacts[0].role == "summary"
    assert response.artifacts[0].text == "Equivalent fractions name the same amount."
    assert response.artifacts[1].sequence_index == 1


def test_generated_content_backfills_text_artifacts_for_legacy_payloads():
    content = GeneratedContent.model_validate(
        {
            "generation_id": "gen-legacy",
            "student_id": str(uuid4()),
            "content_type": "micro_explanation",
            "request_context": {},
            "response": {
                "student_id": str(uuid4()),
                "route": {
                    "intervention_type": "reteach",
                    "delivery_mode": "generated",
                    "scaffolding_level": "medium",
                    "reasons": ["legacy"],
                },
                "blocks": [
                    {
                        "kind": "summary",
                        "title": "Legacy summary",
                        "body": "Older stored payloads only had blocks.",
                    }
                ],
                "curriculum_context": ["Equivalent fractions"],
                "grounding": [],
                "safety_notes": [],
                "validation_issues": [],
                "generation_id": "gen-legacy",
            },
            "quality": GenerationMetadata().model_dump(mode="json"),
        }
    )

    assert len(content.response.artifacts) == 1
    assert content.response.artifacts[0].artifact_type == "text"
    assert content.response.artifacts[0].title == "Legacy summary"
    assert (
        content.response.artifacts[0].text == "Older stored payloads only had blocks."
    )
