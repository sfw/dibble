from __future__ import annotations

from dibble.config import Settings
from dibble.services.protocols import OutcomeStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.retrieval.embedding_store import SQLiteEmbeddingStore
from dibble.services.retrieval.embeddings import build_embedder


def build(*, outcome_store: OutcomeStore, settings: Settings) -> RAGRetriever:
    return RAGRetriever(
        outcome_store,
        embedding_store=SQLiteEmbeddingStore(settings.database_path),
        embedder=build_embedder(settings),
    )
