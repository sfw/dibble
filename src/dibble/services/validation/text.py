from __future__ import annotations

import re

from dibble.models.generation import GroundingReference


_WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")
_STOPWORDS = {
    "about",
    "after",
    "before",
    "foundations",
    "grade",
    "lesson",
    "learn",
    "name",
    "same",
    "show",
    "that",
    "the",
    "their",
    "then",
    "these",
    "this",
    "with",
}


def normalize_words(text: str) -> list[str]:
    return [word.lower() for word in _WORD_PATTERN.findall(text)]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?]+\s*", text.strip())
    return [part for part in parts if part]


def average_word_length(text: str) -> float:
    words = normalize_words(text)
    if not words:
        return 0.0
    return sum(len(word) for word in words) / len(words)


def longest_sentence_word_count(text: str) -> int:
    sentences = split_sentences(text)
    if not sentences:
        return 0
    return max(len(normalize_words(sentence)) for sentence in sentences)


def salient_grounding_terms(grounding: list[GroundingReference]) -> set[str]:
    terms: set[str] = set()

    for reference in grounding:
        terms.update(term.lower() for term in reference.matched_terms if len(term.strip()) >= 3)
        terms.update(_salient_title_words(reference.title))
        if reference.excerpt:
            terms.update(_salient_excerpt_words(reference.excerpt))

    return {term for term in terms if term and term not in _STOPWORDS}


def contains_grounding_language(text: str, grounding: list[GroundingReference]) -> bool:
    normalized_text = text.lower()
    return any(term in normalized_text for term in salient_grounding_terms(grounding))


def curriculum_alignment_score(text: str, grounding: list[GroundingReference]) -> float:
    if not grounding:
        return 0.0

    normalized_text = text.lower()
    text_words = set(normalize_words(text))
    terms = salient_grounding_terms(grounding)
    if not terms:
        return 0.0

    exact_hits = 0
    token_hits = 0
    token_total = 0
    for term in terms:
        if term in normalized_text:
            exact_hits += 1

        term_words = [word for word in normalize_words(term) if word not in _STOPWORDS]
        if not term_words:
            continue
        token_total += len(term_words)
        token_hits += sum(1 for word in term_words if word in text_words)

    exact_score = exact_hits / len(terms)
    token_score = (token_hits / token_total) if token_total else 0.0

    matched_phrase_bonus = 0.0
    matched_terms = [term.lower() for reference in grounding for term in reference.matched_terms]
    if matched_terms:
        matched_hits = sum(1 for term in matched_terms if term and term in normalized_text)
        matched_phrase_bonus = matched_hits / len(matched_terms)

    score = (exact_score * 0.5) + (token_score * 0.35) + (matched_phrase_bonus * 0.15)
    return min(score, 1.0)


def grounding_coverage_score(text: str, grounding: list[GroundingReference]) -> float:
    terms = salient_grounding_terms(grounding)
    if not terms:
        return 0.0

    normalized_text = text.lower()
    covered_terms = sum(1 for term in terms if term in normalized_text)
    return covered_terms / len(terms)


def infer_target_grade(grounding: list[GroundingReference]) -> int | None:
    for reference in grounding:
        grade = _parse_grade_value(reference.grade_level)
        if grade is not None:
            return grade
    return None


def _salient_title_words(title: str) -> set[str]:
    return {word for word in normalize_words(title) if len(word) >= 4}


def _salient_excerpt_words(excerpt: str) -> set[str]:
    return {
        word
        for word in normalize_words(excerpt)
        if len(word) >= 5 and word not in _STOPWORDS
    }


def _parse_grade_value(value: str) -> int | None:
    normalized = value.strip().upper()
    if normalized == "K":
        return 0
    if normalized.startswith("K-"):
        return 2
    if "-" in normalized:
        _, _, upper = normalized.partition("-")
        return int(upper) if upper.isdigit() else None
    return int(normalized) if normalized.isdigit() else None
