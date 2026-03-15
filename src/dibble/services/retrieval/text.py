from __future__ import annotations

import re


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "explain",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "lesson",
    "of",
    "on",
    "or",
    "show",
    "student",
    "students",
    "teach",
    "that",
    "the",
    "their",
    "them",
    "to",
    "use",
    "why",
    "with",
}


def normalize_tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


def salient_tokens(text: str) -> list[str]:
    return [token for token in normalize_tokens(text) if len(token) >= 2 and token not in _STOPWORDS]


def char_ngrams(text: str, *, size: int = 3) -> list[str]:
    collapsed = "".join(ch for ch in text.lower() if ch.isalnum())
    if len(collapsed) < size:
        return [collapsed] if collapsed else []
    return [collapsed[index : index + size] for index in range(len(collapsed) - size + 1)]
