from uuid import uuid4

from dibble.config import Settings
from dibble.models.curriculum import OutcomeUpsert
from dibble.models.generation import (
    ContentIntent,
    CurriculumContentRequest,
    GenerationRequest,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.retrieval.embedding_store import SQLiteEmbeddingStore
from dibble.services.retrieval.embeddings import (
    LocalHashEmbedder,
    OpenAICompatibleEmbedder,
    build_embedder,
)
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database
from tests.support import build_outcome, build_profile


class CountingEmbedder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.local = LocalHashEmbedder(dimensions=32)

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self.local.embed(text)


def _curriculum_request(
    profile: LearnerProfile, request: GenerationRequest
) -> CurriculumContentRequest:
    return CurriculumContentRequest(
        grade_level=profile.grade_level,
        intent=ContentIntent(request.intent),
        content_type=request.requested_content_type
        or RequestedContentType.micro_explanation,
        target_kc_ids=list(request.target_kc_ids),
        target_lo_ids=list(request.target_lo_ids),
        curriculum_context=list(request.curriculum_context),
    )


def test_build_embedder_uses_local_fallback_by_default():
    embedder = build_embedder(Settings())

    assert isinstance(embedder, LocalHashEmbedder)


def test_build_embedder_uses_openai_compatible_embedder_when_configured():
    embedder = build_embedder(
        Settings(
            embedding_api_key="secret",
            embedding_model="text-embedding-demo",
        )
    )

    assert isinstance(embedder, OpenAICompatibleEmbedder)


def test_retriever_reuses_persisted_resource_embeddings(tmp_path):
    database_path = str(tmp_path / "embeddings-cache.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    store = SQLiteOutcomeStore(conn)
    resource = store.upsert(OutcomeUpsert(**build_outcome("CURR-1")))
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), frustration="low", total_load=0.2)
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        curriculum_context=["Explain equivalent fractions with area models."],
    )
    embedder = CountingEmbedder()
    embedding_store = SQLiteEmbeddingStore(conn)
    retriever = RAGRetriever(store, embedding_store=embedding_store, embedder=embedder)

    curriculum_request = _curriculum_request(profile, request)

    retriever.retrieve(curriculum_request)
    first_cached = embedding_store.get(resource.outcome_id)

    retriever.retrieve(curriculum_request)

    assert first_cached is not None
    assert len(embedder.calls) == 3


def test_retriever_refreshes_embeddings_after_resource_update(tmp_path):
    database_path = str(tmp_path / "embeddings-refresh.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    store = SQLiteOutcomeStore(conn)
    resource = store.upsert(OutcomeUpsert(**build_outcome("CURR-1")))
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), frustration="low", total_load=0.2)
    )
    request = GenerationRequest(
        student_id=profile.student_id,
        curriculum_context=["Explain equivalent fractions with area models."],
    )
    embedder = CountingEmbedder()
    embedding_store = SQLiteEmbeddingStore(conn)
    retriever = RAGRetriever(store, embedding_store=embedding_store, embedder=embedder)

    curriculum_request = _curriculum_request(profile, request)

    retriever.retrieve(curriculum_request)
    first_cached = embedding_store.get(resource.outcome_id)

    store.upsert(
        OutcomeUpsert(
            **{
                **build_outcome("CURR-1"),
                "description": "Use strip diagrams and number lines to compare equivalent fractions.",
            }
        )
    )

    retriever.retrieve(curriculum_request)
    second_cached = embedding_store.get("CURR-1")

    assert first_cached is not None
    assert second_cached is not None
    assert second_cached.source_updated_at != first_cached.source_updated_at
    assert len(embedder.calls) == 4
