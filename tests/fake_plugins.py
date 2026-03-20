from __future__ import annotations

import sqlite3

from dibble.config import Settings
from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
)
from dibble.models.profile import LearnerProfile
from dibble.services.content_provider import MockLLMProvider
from dibble.services.content_validator import ContentValidator
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.retrieval.embedding_store import SQLiteEmbeddingStore
from dibble.services.retrieval.embeddings import LocalHashEmbedder


class AlwaysReteachRouter:
    def route(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> AdaptiveRouteDecision:
        return AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["Test plugin forced reteach."],
        )


def build_router():
    return AlwaysReteachRouter()


def build_retriever(
    *, outcome_store, settings: Settings | None = None, connection: sqlite3.Connection
):
    return RAGRetriever(
        outcome_store,
        embedding_store=SQLiteEmbeddingStore(connection),
        embedder=LocalHashEmbedder(),
    )


def build_provider(**kwargs):
    return MockLLMProvider()


def build_validator():
    return ContentValidator()
