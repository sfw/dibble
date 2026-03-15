from __future__ import annotations

from dibble.services.content_validator import ContentValidator


def build() -> ContentValidator:
    return ContentValidator()
