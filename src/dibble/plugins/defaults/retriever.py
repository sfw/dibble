from __future__ import annotations

from dibble.config import Settings
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.retrieval.embedding_store import SQLiteEmbeddingStore
from dibble.services.retrieval.embeddings import build_embedder


def build(*, curriculum_store: SQLiteCurriculumStore, settings: Settings) -> RAGRetriever:
    return RAGRetriever(
        curriculum_store,
        embedding_store=SQLiteEmbeddingStore(settings.database_path),
        embedder=build_embedder(settings),
    )
