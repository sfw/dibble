from __future__ import annotations

from dibble.models.curriculum import CurriculumResource
from dibble.models.generation import GenerationRequest, GroundingReference
from dibble.services.grounding_context import extract_grounding_excerpt
from dibble.models.profile import LearnerProfile
from dibble.services.protocols import CurriculumStore, EmbeddingStore
from dibble.services.retrieval.embedding_store import InMemoryEmbeddingStore
from dibble.services.retrieval.embeddings import Embedder, LocalHashEmbedder, cosine_similarity
from dibble.services.retrieval.scoring import HybridRetrievalScorer


class RAGRetriever:
    def __init__(
        self,
        curriculum_store: CurriculumStore,
        *,
        embedding_store: EmbeddingStore | None = None,
        embedder: Embedder | None = None,
        scorer: HybridRetrievalScorer | None = None,
    ) -> None:
        self.curriculum_store = curriculum_store
        self.embedding_store = embedding_store or InMemoryEmbeddingStore()
        self.embedder = embedder or LocalHashEmbedder()
        self.scorer = scorer or HybridRetrievalScorer()

    def retrieve(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        limit: int = 3,
    ) -> list[GroundingReference]:
        resources = self.curriculum_store.list()
        query_embedding = self.embedder.embed(self.scorer.build_query_text(profile, request))
        scored: list[tuple[float, CurriculumResource, list[str]]] = []

        for resource in resources:
            retrieval_score = self.scorer.score(profile, request, resource)
            resource_embedding = self._resource_embedding(resource)
            embedding_similarity = cosine_similarity(query_embedding, resource_embedding)

            if retrieval_score is None and embedding_similarity < self.scorer.minimum_similarity:
                continue

            matched_terms = retrieval_score.matched_terms if retrieval_score is not None else []
            base_score = retrieval_score.score if retrieval_score is not None else 0.0
            score = base_score + (embedding_similarity * 4.0)
            scored.append((score, resource, matched_terms))

        scored.sort(key=lambda item: (-item[0], item[1].resource_id))
        return [
            GroundingReference(
                resource_id=resource.resource_id,
                title=resource.title,
                grade_level=resource.grade_level,
                subject=resource.subject,
                source_type=resource.source_type,
                score=score,
                matched_terms=matched_terms,
                excerpt=extract_grounding_excerpt(
                    resource.body,
                    matched_terms=matched_terms,
                ),
            )
            for score, resource, matched_terms in scored[:limit]
        ]

    def _resource_embedding(self, resource: CurriculumResource) -> list[float]:
        cached = self.embedding_store.get(resource.resource_id)
        if cached is not None and cached.source_updated_at == resource.updated_at.isoformat():
            return cached.vector

        vector = self.embedder.embed(self.scorer.build_resource_text(resource))
        self.embedding_store.upsert(
            resource_id=resource.resource_id,
            vector=vector,
            source_updated_at=resource.updated_at.isoformat(),
        )
        return vector
