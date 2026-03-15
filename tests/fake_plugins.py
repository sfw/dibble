from __future__ import annotations

from dibble.config import Settings
from dibble.models.generation import AdaptiveRouteDecision, DeliveryMode, GenerationRequest, InterventionType
from dibble.models.profile import LearnerProfile
from dibble.services.content_provider import MockLLMProvider
from dibble.services.content_validator import ContentValidator
from dibble.services.rag_retriever import RAGRetriever
from dibble.services.retrieval.embedding_store import SQLiteEmbeddingStore
from dibble.services.retrieval.embeddings import LocalHashEmbedder


class AlwaysReteachRouter:
    def route(self, profile: LearnerProfile, request: GenerationRequest) -> AdaptiveRouteDecision:
        return AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["Test plugin forced reteach."],
        )


def build_router():
    return AlwaysReteachRouter()


def build_retriever(*, curriculum_store, settings: Settings | None = None):
    database_path = settings.database_path if settings is not None else curriculum_store.database_path
    return RAGRetriever(
        curriculum_store,
        embedding_store=SQLiteEmbeddingStore(database_path),
        embedder=LocalHashEmbedder(),
    )


def build_provider():
    return MockLLMProvider()


def build_validator():
    return ContentValidator()
