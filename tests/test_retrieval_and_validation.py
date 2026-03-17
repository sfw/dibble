from uuid import uuid4

from dibble.models.curriculum import CurriculumResourceUpsert
from dibble.models.generation import GeneratedBlock, GenerationRequest, GroundingReference
from dibble.models.profile import LearnerProfile
from dibble.services.content_validator import ContentValidator
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.validation.text import curriculum_alignment_score, grounding_coverage_score
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


def test_retriever_adds_deterministic_excerpt_from_matching_sentence(tmp_path):
    database_path = str(tmp_path / "retrieval-excerpt.db")
    ensure_database(database_path)
    store = SQLiteCurriculumStore(database_path)
    store.upsert(
        CurriculumResourceUpsert(
            **{
                **build_curriculum_resource("CURR-EXCERPT"),
                "body": (
                    "Students review denominators with simple shapes. "
                    "Use visual fraction models to explain why equivalent fractions name the same amount. "
                    "Then connect the model to the symbolic form."
                ),
            }
        )
    )
    retriever = RAGRetriever(store)
    profile = LearnerProfile.model_validate(build_profile(uuid4(), frustration="low", total_load=0.2))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        curriculum_context=["Use fraction models to show equivalent fractions have the same value."],
    )

    results = retriever.retrieve(profile, request)

    assert results[0].excerpt is not None
    assert "visual fraction models" in results[0].excerpt.lower()
    assert "equivalent fractions" in results[0].excerpt.lower()


def test_retriever_prefers_semantically_relevant_passage_over_leading_noise(tmp_path):
    database_path = str(tmp_path / "retrieval-passage-focus.db")
    ensure_database(database_path)
    store = SQLiteCurriculumStore(database_path)
    store.upsert(
        CurriculumResourceUpsert(
            **{
                **build_curriculum_resource("CURR-PASSAGE"),
                "body": (
                    "Warm up by naming different classroom manipulatives. "
                    "Learners should compare equal partitions and justify that both shapes cover the same region. "
                    "Then connect that area model to symbolic notation for equivalent fractions."
                ),
            }
        )
    )
    retriever = RAGRetriever(store)
    profile = LearnerProfile.model_validate(build_profile(uuid4(), frustration="low", total_load=0.2))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        curriculum_context=["Use area models and equal partitions to show fractions with the same value."],
    )

    results = retriever.retrieve(profile, request)

    assert results[0].excerpt is not None
    assert "same region" in results[0].excerpt.lower() or "area model" in results[0].excerpt.lower()
    assert "warm up by naming different classroom manipulatives" not in results[0].excerpt.lower()


def test_retriever_uses_passage_signal_to_prefer_more_grounded_resource(tmp_path):
    database_path = str(tmp_path / "retrieval-passage-ranking.db")
    ensure_database(database_path)
    store = SQLiteCurriculumStore(database_path)
    store.upsert(
        CurriculumResourceUpsert(
            **{
                **build_curriculum_resource("CURR-NOISY"),
                "body": (
                    "This unit surveys fraction vocabulary, classroom routines, and several unrelated extensions. "
                    "Much later, learners compare equal partitions to show why two shapes still cover the same region. "
                    "The final note reconnects that area model to equivalent fractions."
                ),
            }
        )
    )
    store.upsert(
        CurriculumResourceUpsert(
            **{
                **build_curriculum_resource("CURR-GENERIC"),
                "knowledge_component_ids": ["KC-9"],
                "body": "Review fraction words and identify numerators and denominators in simple examples.",
            }
        )
    )
    retriever = RAGRetriever(store)
    profile = LearnerProfile.model_validate(build_profile(uuid4(), frustration="low", total_load=0.2))
    request = GenerationRequest(
        student_id=profile.student_id,
        curriculum_context=["Use equal partitions and area models to explain why fractions can name the same value."],
    )

    results = retriever.retrieve(profile, request)

    assert results[0].resource_id == "CURR-NOISY"
    assert results[0].excerpt is not None
    assert "equal partitions" in results[0].excerpt.lower() or "same region" in results[0].excerpt.lower()


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


def test_curriculum_alignment_score_prefers_grounded_language():
    grounding = [
        GroundingReference(
            resource_id="CURR-1",
            title="Equivalent Fractions Foundations",
            grade_level="5",
            score=2.0,
            matched_terms=["equivalent fractions", "fraction models"],
        )
    ]

    strong_score = curriculum_alignment_score(
        "Use fraction models to show why equivalent fractions name the same value.",
        grounding,
    )
    weak_score = curriculum_alignment_score(
        "Talk about weather systems and write a short paragraph about clouds.",
        grounding,
    )

    assert strong_score > weak_score
    assert strong_score >= 0.3


def test_grounding_coverage_score_tracks_instruction_language():
    grounding = [
        GroundingReference(
            resource_id="CURR-1",
            title="Equivalent Fractions Foundations",
            grade_level="5",
            score=2.0,
            matched_terms=["equivalent fractions", "fraction models"],
        )
    ]

    strong_score = grounding_coverage_score(
        "Use fraction models to show why equivalent fractions name the same value.",
        grounding,
    )
    weak_score = grounding_coverage_score(
        "Explain the example from above and try one more problem.",
        grounding,
    )

    assert strong_score > weak_score
    assert strong_score >= 0.2


def test_validator_reports_instruction_grounding_gap_when_only_summary_is_grounded():
    issues = ContentValidator().validate(
        blocks=[
            GeneratedBlock(
                kind="summary",
                title="Equivalent fractions",
                body="Equivalent fractions name the same value when fraction models line up.",
            ),
            GeneratedBlock(
                kind="instruction",
                title="Try this",
                body="Look at the example above and explain what you notice.",
            ),
        ],
        grounding=[
            GroundingReference(
                resource_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=2.0,
                matched_terms=["equivalent fractions", "fraction models"],
            )
        ],
    )

    assert issues == ["Instruction blocks do not clearly carry forward the retrieved curriculum language."]


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
