from __future__ import annotations

import re
from dataclasses import dataclass

from dibble.models.curriculum import Outcome
from dibble.services.grounding_context import extract_grounding_excerpt
from dibble.services.retrieval.text import salient_tokens
from dibble.services.retrieval.vectorizer import HashedTextVectorizer


_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class GroundingPassageMatch:
    excerpt: str
    matched_terms: list[str]
    score: float


class GroundingPassageSelector:
    def __init__(
        self,
        *,
        vectorizer: HashedTextVectorizer | None = None,
        minimum_score: float = 0.18,
        max_sentences_per_passage: int = 2,
        max_excerpt_chars: int = 220,
    ) -> None:
        self.vectorizer = vectorizer or HashedTextVectorizer()
        self.minimum_score = minimum_score
        self.max_sentences_per_passage = max(1, max_sentences_per_passage)
        self.max_excerpt_chars = max(60, max_excerpt_chars)

    def select(
        self,
        *,
        query_text: str,
        outcome: Outcome,
        matched_terms: list[str],
    ) -> GroundingPassageMatch | None:
        candidates = self._candidate_passages(outcome.description)
        if not candidates:
            return None

        query_tokens = set(salient_tokens(query_text))
        query_vector = self.vectorizer.vectorize(query_text)
        lowered_terms = [term.lower() for term in matched_terms if term.strip()]
        best: tuple[float, str, list[str]] | None = None

        for passage in candidates:
            passage_tokens = set(salient_tokens(passage))
            matched = sorted(query_tokens & passage_tokens)
            semantic_similarity = self.vectorizer.cosine_similarity(
                query_vector,
                self.vectorizer.vectorize(passage),
            )
            lexical_overlap = (
                len(query_tokens & passage_tokens) / len(query_tokens)
                if query_tokens
                else 0.0
            )
            phrase_hits = sum(1 for term in lowered_terms if term in passage.lower())
            score = (
                (semantic_similarity * 4.5)
                + (lexical_overlap * 3.2)
                + min(0.45, phrase_hits * 0.12)
                + (0.08 if len(passage.split()) >= 10 else 0.0)
            )
            if best is None or score > best[0]:
                best = (score, passage, matched[:6] or matched_terms[:6])

        if best is None or best[0] < self.minimum_score:
            return None

        excerpt = extract_grounding_excerpt(
            best[1],
            matched_terms=best[2],
            max_chars=self.max_excerpt_chars,
        )
        if excerpt is None:
            return None
        return GroundingPassageMatch(
            excerpt=excerpt,
            matched_terms=best[2],
            score=round(best[0], 2),
        )

    def _candidate_passages(self, description: str) -> list[str]:
        normalized = _WHITESPACE_PATTERN.sub(" ", description).strip()
        if not normalized:
            return []
        sentences = [
            sentence.strip()
            for sentence in _SENTENCE_SPLIT_PATTERN.split(normalized)
            if sentence.strip()
        ]
        if not sentences:
            return [normalized]

        candidates: list[str] = []
        max_window = min(self.max_sentences_per_passage, len(sentences))
        for window_size in range(max_window, 0, -1):
            for start in range(0, len(sentences) - window_size + 1):
                candidates.append(" ".join(sentences[start : start + window_size]))
        return candidates
