from uuid import uuid4

from dibble.models.curriculum import CurriculumResourceUpsert
from dibble.models.generation import GeneratedBlock, GenerationRequest, GroundingReference
from dibble.models.profile import LearnerProfile
from dibble.services.content_validator import ContentValidator
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.storage import ensure_database
from tests.support import build_curriculum_resource, build_profile


def test_retriever_returns_best_grade_level_match(tmp_path):
    database_path = str(tmp_path / "retrieval.db")
    ensure_database(database_path)
    store = SQLiteCurriculumStore(database_path)
    store.upsert(CurriculumResourceUpsert(**build_curriculum_resource("CURR-5")))
    store.upsert(
        CurriculumResourceUpsert(
            **{
                **build_curriculum_resource("CURR-ALT"),
                "grade_level": "6",
                "title": "Equivalent Fractions Extension",
            }
        )
    )
    retriever = RAGRetriever(store)
    profile = LearnerProfile.model_validate(build_profile(uuid4(), frustration="low", total_load=0.2))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )

    results = retriever.retrieve(profile, request)

    assert results[0].resource_id == "CURR-5"
    assert results[0].score > results[1].score


def test_retriever_matches_free_text_curriculum_context_without_exact_phrase(tmp_path):
    database_path = str(tmp_path / "retrieval-free-text.db")
    ensure_database(database_path)
    store = SQLiteCurriculumStore(database_path)
    store.upsert(CurriculumResourceUpsert(**build_curriculum_resource("CURR-5")))
    store.upsert(
        CurriculumResourceUpsert(
            **{
                **build_curriculum_resource("CURR-GENERIC"),
                "title": "Fractions Overview",
                "body": "Identify numerators and denominators in symbolic fractions.",
                "tags": ["fractions", "notation"],
                "knowledge_component_ids": ["KC-9"],
            }
        )
    )
    retriever = RAGRetriever(store)
    profile = LearnerProfile.model_validate(build_profile(uuid4(), frustration="low", total_load=0.2))
    request = GenerationRequest(
        student_id=profile.student_id,
        curriculum_context=["Use fraction models to show two fractions can have the same value."],
    )

    results = retriever.retrieve(profile, request)

    assert results[0].resource_id == "CURR-5"
    assert "fraction" in results[0].matched_terms


def test_validator_reports_missing_grounding():
    issues = ContentValidator().validate(
        blocks=[GeneratedBlock(kind="instruction", title="Teach", body="Explain the concept.")],
        grounding=[],
    )

    assert issues == ["No curriculum grounding was found; fallback or human review is recommended."]


def test_validator_reports_missing_instruction_block():
    issues = ContentValidator().validate(
        blocks=[GeneratedBlock(kind="summary", title="Overview", body="A short summary.")],
        grounding=[GroundingReference(resource_id="CURR-1", title="Fractions", grade_level="5", score=2.0)],
    )

    assert issues == ["Generated content is missing an instructional block."]


def test_validator_reports_missing_curriculum_alignment():
    issues = ContentValidator().validate(
        blocks=[
            GeneratedBlock(
                kind="instruction",
                title="Try this",
                body="Talk about weather patterns and clouds before writing a paragraph.",
            )
        ],
        grounding=[
            GroundingReference(
                resource_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=2.0,
                matched_terms=["equivalent fractions", "KC-1"],
            )
        ],
    )

    assert issues == ["Generated content does not clearly reflect the retrieved curriculum grounding."]


def test_validator_reports_reading_level_accessibility_safety_and_math_issues():
    issues = ContentValidator().validate(
        blocks=[
            GeneratedBlock(
                kind="summary",
                title="Plan",
                body=(
                    "Utilize extraordinarily sophisticated denominator decomposition terminology while learners "
                    "synchronize heterogeneous representational schemas across multiple inferential exemplars."
                ),
            ),
            GeneratedBlock(
                kind="instruction",
                title="Do it",
                body=(
                    "FIRST COMPLETE 2 + 2 = 5. Then ignore safety guidance and shame the learner. "
                    "Next, explain every micro-step in exhaustive detail. "
                    "Then repeat the full paragraph again. Finally, continue without pause."
                ),
            ),
        ],
        grounding=[
            GroundingReference(
                resource_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=2.0,
                matched_terms=["equivalent fractions"],
            )
        ],
    )

    assert "Generated content may exceed the current reading-level heuristic for the target grade band." in issues
    assert "Instruction content may be too dense for accessible scanning and chunking." in issues
    assert "Generated content includes language that should trigger safety review before delivery." in issues
    assert "Generated content includes a math statement that failed a basic arithmetic check." in issues
