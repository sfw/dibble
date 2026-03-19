from __future__ import annotations

from dataclasses import dataclass

from dibble.models.curriculum import Outcome
from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.services.retrieval.text import salient_tokens
from dibble.services.retrieval.vectorizer import HashedTextVectorizer


@dataclass(frozen=True, slots=True)
class RetrievalScore:
    score: float
    matched_terms: list[str]
    semantic_similarity: float = 0.0


def build_query_text(profile: LearnerProfile, request: GenerationRequest) -> str:
    parts = [
        request.intent.value,
        *request.target_kc_ids,
        *request.target_lo_ids,
        *request.curriculum_context,
        *profile.learning_preferences.example_domain_preferences,
    ]
    return " ".join(part for part in parts if part)


def build_outcome_text(outcome: Outcome) -> str:
    parts = [
        outcome.title,
        outcome.subject,
        outcome.description,
        *outcome.knowledge_component_ids,
        *outcome.tags,
    ]
    return " ".join(part for part in parts if part)


class HybridRetrievalScorer:
    def __init__(
        self,
        *,
        vectorizer: HashedTextVectorizer | None = None,
        minimum_similarity: float = 0.12,
    ) -> None:
        self.vectorizer = vectorizer or HashedTextVectorizer()
        self.minimum_similarity = minimum_similarity

    def score(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        outcome: Outcome,
    ) -> RetrievalScore | None:
        query_text = self.build_query_text(profile, request)
        outcome_text = self.build_outcome_text(outcome)

        query_tokens = set(salient_tokens(query_text))
        outcome_tokens = set(salient_tokens(outcome_text))
        matched_terms = sorted(query_tokens & outcome_tokens)

        semantic_similarity = self.vectorizer.cosine_similarity(
            self.vectorizer.vectorize(query_text),
            self.vectorizer.vectorize(outcome_text),
        )
        lexical_overlap = self._lexical_overlap(query_tokens, outcome_tokens)
        metadata_bonus = self._metadata_bonus(profile, request, outcome)
        score = (semantic_similarity * 6.0) + (lexical_overlap * 3.0) + metadata_bonus

        if (
            not matched_terms
            and semantic_similarity < self.minimum_similarity
            and metadata_bonus <= 0.0
        ):
            return None

        return RetrievalScore(
            score=score,
            matched_terms=matched_terms[:6],
            semantic_similarity=semantic_similarity,
        )

    def build_query_text(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> str:
        return build_query_text(profile, request)

    def build_outcome_text(self, outcome: Outcome) -> str:
        return build_outcome_text(outcome)

    def _lexical_overlap(
        self, query_tokens: set[str], outcome_tokens: set[str]
    ) -> float:
        if not query_tokens:
            return 0.0
        overlap = len(query_tokens & outcome_tokens)
        return overlap / len(query_tokens)

    def _metadata_bonus(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        outcome: Outcome,
    ) -> float:
        bonus = 0.0

        if outcome.grade_level == profile.grade_level:
            bonus += 2.0
        elif outcome.grade_level in {"K-2", "3-5", "6-8", "9-12"}:
            bonus += 0.5

        kc_matches = set(request.target_kc_ids) & set(outcome.knowledge_component_ids)
        bonus += 1.5 * len(kc_matches)

        return bonus
