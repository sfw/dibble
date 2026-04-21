import sqlite3
import json
from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    DeliveryMode,
    CurriculumContentKey,
    CurriculumLibraryEntry,
    CurriculumLibraryStorageScope,
    CurriculumContentRequest,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationModeCalibration,
    GenerationRequest,
    GenerationResponse,
    InterventionType,
)
from dibble.models.profile import LearnerProfile
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.curriculum_content_library_store import (
    SQLiteCurriculumContentLibraryStore,
)
from dibble.services.generation_modes import build_generation_mode_plan
from dibble.services.harness.content_library import (
    GeneratedContentBackedCurriculumLibraryStore,
    LocalCurriculumContentLibrary,
)
from dibble.services.harness.policy import HarnessAuthoringPolicyBuilder
from dibble.services.harness.request_adapter import CurriculumContentRequestAdapter
from dibble.storage import (
    CURRICULUM_CONTENT_LIBRARY_TABLE_SQL,
    GENERATED_CONTENT_TABLE_SQL,
)
from tests.support import build_profile


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


def test_curriculum_content_key_ignores_learner_identity_when_request_is_shared():
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    grounding = [
        {
            "outcome_id": "CURR-1",
            "title": "Equivalent Fractions Foundations",
            "grade_level": "5",
            "score": 1.0,
        }
    ]

    first = CurriculumContentKey(
        request=request,
        route=route,
        grounding=grounding,
    )
    second = CurriculumContentKey(
        request=request.model_copy(),
        route=route.model_copy(),
        grounding=grounding,
    )

    assert first.cache_key() == second.cache_key()


def test_curriculum_content_key_ignores_router_rationale_and_grounding_scores():
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )
    first = CurriculumContentKey(
        request=request,
        route=AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["high frustration and low confidence"],
        ),
        grounding=[
            {
                "outcome_id": "CURR-1",
                "title": "Equivalent Fractions Foundations",
                "grade_level": "5",
                "score": 0.92,
                "excerpt": "first excerpt",
            }
        ],
    )
    second = CurriculumContentKey(
        request=request,
        route=AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["low mastery and help-seeking indicate reteach"],
        ),
        grounding=[
            {
                "outcome_id": "CURR-1",
                "title": "Equivalent Fractions Foundations",
                "grade_level": "5",
                "score": 0.44,
                "excerpt": "different excerpt",
            }
        ],
    )

    assert first.cache_key() == second.cache_key()


def test_curriculum_library_entry_uses_curriculum_key_and_not_learner_identity():
    student_id = uuid4()
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    content_key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-library",
        student_id=student_id,
        content_type="micro_explanation",
        request_context={"selected_content_type": "micro_explanation"},
        response=GenerationResponse(
            student_id=student_id,
            route=route,
            blocks=[
                GeneratedBlock(
                    kind="summary",
                    title="Learning focus",
                    body="Equivalent fractions name the same amount.",
                )
            ],
            curriculum_context=["Equivalent fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(),
    )

    entry = CurriculumLibraryEntry(content_key=content_key, content=content)

    assert entry.cache_key == content_key.cache_key()
    assert entry.source_generation_id == "gen-library"
    assert entry.storage_scope == CurriculumLibraryStorageScope.local_only


def test_local_curriculum_library_uses_explicit_library_store_adapter():
    student_id = uuid4()
    conn = sqlite3.connect(":memory:")
    conn.executescript(CURRICULUM_CONTENT_LIBRARY_TABLE_SQL)
    library = LocalCurriculumContentLibrary(SQLiteCurriculumContentLibraryStore(conn))
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    content_key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-library-store",
        student_id=student_id,
        content_type="micro_explanation",
        request_context={"selected_content_type": "micro_explanation"},
        response=GenerationResponse(
            student_id=student_id,
            route=route,
            blocks=[
                GeneratedBlock(
                    kind="summary",
                    title="Learning focus",
                    body="Equivalent fractions name the same amount.",
                )
            ],
            curriculum_context=["Equivalent fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(),
    )

    stored_entry = library.upsert_entry(
        entry=CurriculumLibraryEntry(content_key=content_key, content=content)
    )
    fetched_entry = library.get_fresh_entry(key=content_key)

    assert stored_entry.cache_key == content_key.cache_key()
    assert fetched_entry is not None
    assert fetched_entry.storage_scope == CurriculumLibraryStorageScope.local_only
    assert fetched_entry.content.generation_id == "gen-library-store"


def test_generated_content_backed_library_store_remains_available_as_transition():
    student_id = uuid4()
    conn = sqlite3.connect(":memory:")
    conn.executescript(GENERATED_CONTENT_TABLE_SQL)
    generated_store = SQLiteGeneratedContentStore(conn)
    library = LocalCurriculumContentLibrary(
        GeneratedContentBackedCurriculumLibraryStore(generated_store)
    )
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    content_key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-transition-library-store",
        student_id=student_id,
        content_type="micro_explanation",
        request_context={"selected_content_type": "micro_explanation"},
        response=GenerationResponse(
            student_id=student_id,
            route=route,
            blocks=[
                GeneratedBlock(
                    kind="summary",
                    title="Learning focus",
                    body="Equivalent fractions name the same amount.",
                )
            ],
            curriculum_context=["Equivalent fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(),
    )

    library.upsert_entry(
        entry=CurriculumLibraryEntry(content_key=content_key, content=content)
    )

    assert library.get_fresh_entry(key=content_key) is not None


def test_authoring_policy_builder_keeps_private_context_out_of_generation_constraints():
    profile = LearnerProfile.model_validate(build_profile(uuid4(), total_load=0.85))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    policy = HarnessAuthoringPolicyBuilder().build(
        profile=profile,
        request=request,
        route=route,
    )

    assert "difficulty_band" in policy.generation_constraints
    assert "target_kc_ids" not in policy.generation_constraints
    assert "mode_calibration" not in policy.generation_constraints
    assert policy.request_context["target_kc_ids"] == ["KC-1"]


def test_curriculum_content_request_adapter_consumes_explicit_policy():
    request = GenerationRequest(
        student_id=uuid4(),
        target_kc_ids=["KC-1"],
        intent="practice",
        learner_prompt="Use a calm tone.",
    )
    policy = HarnessAuthoringPolicyBuilder().build(
        profile=LearnerProfile.model_validate(
            build_profile(uuid4(), kc_mastery={"KC-1": 0.3})
        ),
        request=request,
        route=AdaptiveRouteDecision(
            intervention_type=InterventionType.targeted_practice,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["test"],
        ),
    )

    adapted = CurriculumContentRequestAdapter().adapt(
        grade_level="5",
        request=request,
        policy=policy,
    )

    assert adapted.grade_level == "5"
    assert adapted.content_type == policy.content_type
    assert adapted.generation_constraints == policy.generation_constraints


def test_curriculum_content_request_adapter_drops_private_socratic_prompt_text():
    request = GenerationRequest(
        student_id=uuid4(),
        target_kc_ids=["KC-1"],
        intent="assessment",
        learner_prompt=(
            "learner: I think 3/4 is bigger because 3 is bigger than 2. "
            "Recent conversation: tutor asked about equal space."
        ),
    )
    policy = HarnessAuthoringPolicyBuilder().build(
        profile=LearnerProfile.model_validate(
            build_profile(uuid4(), kc_mastery={"KC-1": 0.3})
        ),
        request=request,
        route=AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["test"],
        ),
    )

    adapted = CurriculumContentRequestAdapter().adapt(
        grade_level="5",
        request=request,
        policy=policy,
    )

    payload = adapted.model_dump_json()
    assert "3/4 is bigger" not in payload
    assert "Recent conversation" not in payload


def test_curriculum_content_request_omits_learner_state_explanations_from_guidance():
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), kc_mastery={"KC-1": 0.42}, total_load=0.62)
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="session_controller",
            confidence=0.79,
            support_bias=-1,
            session_signal="negative",
            session_source="session_controller",
            session_confidence=0.79,
            session_assessment_count=1,
            session_phase="repair",
            session_arc_action="reprobe_new_angle",
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
    adapted = CurriculumContentRequestAdapter().adapt(
        grade_level=profile.grade_level,
        request=request,
        policy=HarnessAuthoringPolicyBuilder().build(
            profile=profile,
            request=request,
            route=route,
        ),
    )

    payload = adapted.model_dump_json()
    assert "support need" not in payload
    assert "recent Socratic turn" not in payload
    assert "recent Socratic follow-up" not in payload


def test_cache_identity_payload_omits_prompt_guidance_and_rationale_strings():
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.practice,
        content_type="practice_problem",
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
        prompt_guidance=(
            "support need is still high. Start from the recent Socratic turn."
        ),
        generation_constraints={
            "practice_distractor_focus": "Use one clean structural contrast.",
            "practice_distractor_rationale": "support need is still high",
            "worked_example_release_rationale": "recent Socratic turn",
        },
        adaptive_variant_hint="guided_reflection",
    )

    payload = json.dumps(
        request.cache_identity_payload(),
        sort_keys=True,
    )

    assert "prompt_guidance" not in payload
    assert "support need" not in payload
    assert "recent Socratic turn" not in payload
    assert "practice_distractor_rationale" not in payload
    assert "worked_example_release_rationale" not in payload


def test_generation_mode_plan_wrapper_matches_harness_authoring_policy():
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), kc_mastery={"KC-1": 0.42}, total_load=0.4)
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )

    policy = HarnessAuthoringPolicyBuilder().build(
        profile=profile,
        request=request,
        route=route,
    )
    plan = build_generation_mode_plan(profile, request, route)

    assert plan.content_type == policy.content_type
    assert plan.prompt_guidance == policy.prompt_guidance
    assert plan.request_context == policy.request_context
