from __future__ import annotations

import hashlib
import math
from collections import Counter

from dibble.services.retrieval.text import char_ngrams, salient_tokens


SparseVector = Counter[int]


class HashedTextVectorizer:
    def __init__(self, *, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def vectorize(self, text: str) -> SparseVector:
        features: SparseVector = Counter()
        tokens = salient_tokens(text)

        for token in tokens:
            features[self._bucket(f"tok:{token}")] += 1.0

        for left, right in zip(tokens, tokens[1:]):
            features[self._bucket(f"bigram:{left}:{right}")] += 1.25

        for gram in char_ngrams(text):
            features[self._bucket(f"gram:{gram}")] += 0.2

        return features

    def cosine_similarity(self, left: SparseVector, right: SparseVector) -> float:
        if not left or not right:
            return 0.0

        dot = sum(weight * right.get(index, 0.0) for index, weight in left.items())
        left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
        right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _bucket(self, feature: str) -> int:
        digest = hashlib.sha256(feature.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % self.dimensions
