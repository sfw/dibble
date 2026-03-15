from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from dibble.models.generation import GeneratedBlock, GeneratedBlockChunk, GenerationStreamEvent


def iter_block_chunks(blocks: Iterable[GeneratedBlock], *, chunk_size: int = 120) -> Iterator[GeneratedBlockChunk]:
    for block_index, block in enumerate(blocks):
        parts = _chunk_text(block.body, chunk_size=chunk_size)
        if not parts:
            yield GeneratedBlockChunk(
                block_index=block_index,
                kind=block.kind,
                title=block.title,
                body_delta="",
                done=True,
            )
            continue

        for part_index, part in enumerate(parts):
            yield GeneratedBlockChunk(
                block_index=block_index,
                kind=block.kind,
                title=block.title,
                body_delta=part,
                done=part_index == len(parts) - 1,
            )


def encode_sse_event(event: GenerationStreamEvent) -> bytes:
    payload = json.dumps(event.model_dump(mode="json", exclude_none=True))
    return f"event: {event.event}\ndata: {payload}\n\n".encode("utf-8")


def _chunk_text(text: str, *, chunk_size: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.append(current)
        current = word

    chunks.append(current)
    return chunks
