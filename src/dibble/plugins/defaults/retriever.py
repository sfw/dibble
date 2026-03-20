from __future__ import annotations

import sqlite3

from dibble.config import Settings
from dibble.services.protocols import OutcomeStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.retrieval.embedding_store import SQLiteEmbeddingStore
from dibble.services.retrieval.embeddings import build_embedder


def build(
    *, outcome_store: OutcomeStore, settings: Settings, connection: sqlite3.Connection
) -> RAGRetriever:
    return RAGRetriever(
        outcome_store,
        embedding_store=SQLiteEmbeddingStore(connection),
        embedder=build_embedder(settings),
    )
