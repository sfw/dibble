from __future__ import annotations

from dibble.models.curriculum import Outcome
from dibble.models.generation import GenerationRequest, GroundingReference
from dibble.services.grounding_context import extract_grounding_excerpt
from dibble.models.profile import LearnerProfile
from dibble.services.protocols import EmbeddingStore, OutcomeStore
from dibble.services.retrieval.grounding_passages import GroundingPassageSelector
from dibble.services.retrieval.embedding_store import InMemoryEmbeddingStore
from dibble.services.retrieval.embeddings import (
    Embedder,
    LocalHashEmbedder,
    cosine_similarity,
)
from dibble.services.retrieval.scoring import HybridRetrievalScorer


class RAGRetriever:
    def __init__(
        self,
        outcome_store: OutcomeStore,
        *,
        embedding_store: EmbeddingStore | None = None,
        embedder: Embedder | None = None,
        scorer: HybridRetrievalScorer | None = None,
        passage_selector: GroundingPassageSelector | None = None,
    ) -> None:
        self.outcome_store = outcome_store
        self.embedding_store = embedding_store or InMemoryEmbeddingStore()
        self.embedder = embedder or LocalHashEmbedder()
        self.scorer = scorer or HybridRetrievalScorer()
        self.passage_selector = passage_selector or GroundingPassageSelector()

    def retrieve(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        limit: int = 3,
    ) -> list[GroundingReference]:
        outcomes = self.outcome_store.list()
        query_text = self.scorer.build_query_text(profile, request)
        query_embedding = self.embedder.embed(query_text)
        scored: list[tuple[float, Outcome, list[str], str | None]] = []

        for outcome in outcomes:
            retrieval_score = self.scorer.score(profile, request, outcome)
            outcome_embedding = self._outcome_embedding(outcome)
            embedding_similarity = cosine_similarity(query_embedding, outcome_embedding)

            if (
                retrieval_score is None
                and embedding_similarity < self.scorer.minimum_similarity
            ):
                continue

            matched_terms = (
                retrieval_score.matched_terms if retrieval_score is not None else []
            )
            base_score = retrieval_score.score if retrieval_score is not None else 0.0
            passage_match = self.passage_selector.select(
                query_text=query_text,
                outcome=outcome,
                matched_terms=matched_terms,
            )
            score = base_score + (embedding_similarity * 4.0)
            if passage_match is not None:
                score += passage_match.score * 0.45
                matched_terms = passage_match.matched_terms or matched_terms
            scored.append(
                (
                    score,
                    outcome,
                    matched_terms,
                    passage_match.excerpt if passage_match is not None else None,
                )
            )

        scored.sort(key=lambda item: (-item[0], item[1].outcome_id))
        return [
            GroundingReference(
                outcome_id=outcome.outcome_id,
                title=outcome.title,
                grade_level=outcome.grade_level,
                subject=outcome.subject,
                score=score,
                matched_terms=matched_terms,
                excerpt=excerpt
                or extract_grounding_excerpt(
                    outcome.description,
                    matched_terms=matched_terms,
                ),
            )
            for score, outcome, matched_terms, excerpt in scored[:limit]
        ]

    def _outcome_embedding(self, outcome: Outcome) -> list[float]:
        cached = self.embedding_store.get(outcome.outcome_id)
        if (
            cached is not None
            and cached.source_updated_at == outcome.updated_at.isoformat()
        ):
            return cached.vector

        vector = self.embedder.embed(self.scorer.build_outcome_text(outcome))
        self.embedding_store.upsert(
            resource_id=outcome.outcome_id,
            vector=vector,
            source_updated_at=outcome.updated_at.isoformat(),
        )
        return vector
