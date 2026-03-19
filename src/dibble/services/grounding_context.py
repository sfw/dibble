from __future__ import annotations

import re

from dibble.models.generation import GroundingReference


_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_grounding_references(
    grounding: list[GroundingReference | str],
) -> list[GroundingReference]:
    normalized: list[GroundingReference] = []
    for index, item in enumerate(grounding):
        if isinstance(item, GroundingReference):
            normalized.append(item)
            continue
        normalized.append(
            GroundingReference(
                outcome_id=f"legacy-grounding-{index}",
                title=str(item),
                grade_level="unknown",
                score=0.0,
            )
        )
    return normalized


def extract_grounding_excerpt(
    body: str,
    *,
    matched_terms: list[str],
    max_chars: int = 220,
) -> str | None:
    normalized = _normalize_whitespace(body)
    if not normalized:
        return None
    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_PATTERN.split(normalized)
        if sentence.strip()
    ]
    if not sentences:
        return _truncate(normalized, max_chars)

    lowered_terms = [term.lower() for term in matched_terms if term.strip()]
    prioritized = [
        sentence
        for sentence in sentences
        if any(term in sentence.lower() for term in lowered_terms)
    ]
    ordered_sentences = prioritized + [
        sentence for sentence in sentences if sentence not in prioritized
    ]
    excerpt = _join_sentences_with_cap(ordered_sentences, max_chars=max_chars)
    return excerpt or _truncate(normalized, max_chars)


def render_grounding_context(
    grounding: list[GroundingReference | str],
    *,
    max_items: int = 3,
    max_excerpt_chars: int = 180,
) -> str:
    normalized_grounding = normalize_grounding_references(grounding)
    if not normalized_grounding:
        return "No grounding documents were retrieved."

    fragments: list[str] = []
    for reference in normalized_grounding[:max_items]:
        detail: list[str] = [reference.title]
        if reference.subject:
            detail.append(reference.subject)
        detail.append(f"grade {reference.grade_level}")
        if reference.matched_terms:
            detail.append(f"matched={', '.join(reference.matched_terms[:4])}")
        excerpt = _flatten_excerpt(reference.excerpt or "", max_chars=max_excerpt_chars)
        if excerpt:
            detail.append(f"excerpt={excerpt}")
        fragments.append(" | ".join(detail))
    return " || ".join(fragments)


def summarize_grounding_titles(
    grounding: list[GroundingReference | str], *, max_items: int = 2
) -> str:
    normalized_grounding = normalize_grounding_references(grounding)
    if not normalized_grounding:
        return "the current curriculum context"
    titles = [reference.title for reference in normalized_grounding[:max_items]]
    return ", ".join(titles)


def summarize_grounding_excerpts(
    grounding: list[GroundingReference | str],
    *,
    max_items: int = 1,
    max_chars: int = 100,
) -> str:
    normalized_grounding = normalize_grounding_references(grounding)
    excerpts = [
        _flatten_excerpt(reference.excerpt or "", max_chars=max_chars)
        for reference in normalized_grounding[:max_items]
        if reference.excerpt
    ]
    excerpts = [excerpt for excerpt in excerpts if excerpt]
    if excerpts:
        return " / ".join(excerpts)
    return summarize_grounding_titles(normalized_grounding, max_items=max_items)


def _join_sentences_with_cap(sentences: list[str], *, max_chars: int) -> str:
    joined: list[str] = []
    total_length = 0
    for sentence in sentences:
        extra_length = len(sentence) if not joined else len(sentence) + 1
        if joined and total_length + extra_length > max_chars:
            break
        if not joined and len(sentence) > max_chars:
            return _truncate(sentence, max_chars)
        joined.append(sentence)
        total_length += extra_length
    return " ".join(joined)


def _normalize_whitespace(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def _flatten_excerpt(text: str, *, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if not normalized:
        return ""
    flattened = normalized.replace(". ", "; ").replace("! ", "; ").replace("? ", "; ")
    flattened = flattened.rstrip(".!?;:")
    return _truncate(flattened, max_chars)


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
