from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from dibble.config import Settings
from dibble.services.llm_client import LLMClientError, post_json
from dibble.services.retrieval.text import char_ngrams, salient_tokens

_STRICT_EMBEDDER_DEPLOYMENT_MODES = frozenset(
    {"household_container", "managed", "production"}
)


class EmbeddingError(RuntimeError):
    """Raised when embedding generation fails."""


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class LocalHashEmbedder:
    def __init__(self, *, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = salient_tokens(text)

        for token in tokens:
            vector[self._bucket(f"tok:{token}")] += 1.0

        for left, right in zip(tokens, tokens[1:]):
            vector[self._bucket(f"bigram:{left}:{right}")] += 1.25

        for gram in char_ngrams(text):
            vector[self._bucket(f"gram:{gram}")] += 0.15

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def _bucket(self, feature: str) -> int:
        return sum(ord(char) for char in feature) % self.dimensions


@dataclass(slots=True)
class UnavailableEmbedder:
    reason: str

    def embed(self, text: str) -> list[float]:
        raise EmbeddingError(self.reason)


@dataclass(slots=True)
class OpenAICompatibleEmbedder:
    api_base: str
    api_key: str
    model: str
    timeout_seconds: float = 15.0

    def embed(self, text: str) -> list[float]:
        try:
            response = post_json(
                f"{self.api_base.rstrip('/')}/embeddings",
                payload={"model": self.model, "input": text},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout_seconds,
            )
        except LLMClientError as exc:
            raise EmbeddingError(str(exc)) from exc

        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise EmbeddingError("Embedding response did not include any vectors.")

        embedding = data[0].get("embedding")
        if not isinstance(embedding, list) or not all(
            isinstance(value, (int, float)) for value in embedding
        ):
            raise EmbeddingError(
                "Embedding response did not include a valid numeric vector."
            )

        return [float(value) for value in embedding]


def has_real_embedder_config(settings: Settings) -> bool:
    return bool(settings.embedding_api_key and settings.embedding_model)


def has_real_llm_config(settings: Settings) -> bool:
    return bool(
        (settings.llm_api_key and settings.llm_model)
        or (settings.llm_secondary_api_key and settings.llm_secondary_model)
    )


def embedder_kind(settings: Settings) -> str:
    if has_real_embedder_config(settings):
        return "openai_compatible"
    if settings.embedding_allow_local_fallback:
        return "local_hash"
    return "unconfigured"


def embedder_detail(settings: Settings) -> str:
    kind = embedder_kind(settings)
    if kind == "openai_compatible":
        return settings.embedding_model or "configured"
    if kind == "local_hash":
        return f"{settings.embedding_dimensions}-dimension local hash fallback"
    return "No embedding provider is configured."


def local_hash_embedder_disallowed(settings: Settings) -> bool:
    return (
        embedder_kind(settings) == "local_hash"
        and settings.deployment_mode in _STRICT_EMBEDDER_DEPLOYMENT_MODES
        and has_real_llm_config(settings)
    )


def build_embedder(settings: Settings) -> Embedder:
    if has_real_embedder_config(settings):
        return OpenAICompatibleEmbedder(
            api_base=settings.embedding_api_base,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            timeout_seconds=settings.embedding_timeout_seconds,
        )

    if settings.embedding_allow_local_fallback:
        if local_hash_embedder_disallowed(settings):
            return UnavailableEmbedder(
                "Local hash embeddings are not allowed for a real-provider "
                f"{settings.deployment_mode} runtime. Configure "
                "DIBBLE_EMBEDDING_API_KEY and DIBBLE_EMBEDDING_MODEL."
            )
        return LocalHashEmbedder(dimensions=settings.embedding_dimensions)

    raise EmbeddingError(
        "No embedding provider is configured and local fallback is disabled."
    )
