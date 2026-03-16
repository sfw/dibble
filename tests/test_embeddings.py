from uuid import uuid4

from dibble.config import Settings
from dibble.models.curriculum import CurriculumResourceUpsert
from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.retrieval.embedding_store import SQLiteEmbeddingStore
from dibble.services.retrieval.embeddings import LocalHashEmbedder, OpenAICompatibleEmbedder, build_embedder
from dibble.storage import ensure_database
from tests.support import build_curriculum_resource, build_profile


class CountingEmbedder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.local = LocalHashEmbedder(dimensions=32)

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self.local.embed(text)


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
    store = SQLiteCurriculumStore(database_path)
    resource = store.upsert(CurriculumResourceUpsert(**build_curriculum_resource("CURR-1")))
    profile = LearnerProfile.model_validate(build_profile(uuid4(), frustration="low", total_load=0.2))
    request = GenerationRequest(
        student_id=profile.student_id,
        curriculum_context=["Explain equivalent fractions with area models."],
    )
    embedder = CountingEmbedder()
    embedding_store = SQLiteEmbeddingStore(database_path)
    retriever = RAGRetriever(store, embedding_store=embedding_store, embedder=embedder)

    retriever.retrieve(profile, request)
    first_cached = embedding_store.get(resource.resource_id)

    retriever.retrieve(profile, request)

    assert first_cached is not None
    assert len(embedder.calls) == 3


def test_retriever_refreshes_embeddings_after_resource_update(tmp_path):
    database_path = str(tmp_path / "embeddings-refresh.db")
    ensure_database(database_path)
    store = SQLiteCurriculumStore(database_path)
    resource = store.upsert(CurriculumResourceUpsert(**build_curriculum_resource("CURR-1")))
    profile = LearnerProfile.model_validate(build_profile(uuid4(), frustration="low", total_load=0.2))
    request = GenerationRequest(
        student_id=profile.student_id,
        curriculum_context=["Explain equivalent fractions with area models."],
    )
    embedder = CountingEmbedder()
    embedding_store = SQLiteEmbeddingStore(database_path)
    retriever = RAGRetriever(store, embedding_store=embedding_store, embedder=embedder)

    retriever.retrieve(profile, request)
    first_cached = embedding_store.get(resource.resource_id)

    store.upsert(
        CurriculumResourceUpsert(
            **{
                **build_curriculum_resource("CURR-1"),
                "body": "Use strip diagrams and number lines to compare equivalent fractions.",
            }
        )
    )

    retriever.retrieve(profile, request)
    second_cached = embedding_store.get("CURR-1")

    assert first_cached is not None
    assert second_cached is not None
    assert second_cached.source_updated_at != first_cached.source_updated_at
    assert len(embedder.calls) == 4
