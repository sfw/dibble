from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class StoredEmbedding:
    resource_id: str
    vector: list[float]
    dimensions: int
    source_updated_at: str
    indexed_at: str


class SQLiteEmbeddingStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get(self, resource_id: str) -> StoredEmbedding | None:
        row = self._conn.execute(
            """
            SELECT resource_id, vector, dimensions, source_updated_at, indexed_at
            FROM curriculum_resource_embeddings
            WHERE resource_id = ?
            """,
            (resource_id,),
        ).fetchone()

        if row is None:
            return None

        return StoredEmbedding(
            resource_id=row[0],
            vector=json.loads(row[1]),
            dimensions=row[2],
            source_updated_at=row[3],
            indexed_at=row[4],
        )

    def upsert(
        self, *, resource_id: str, vector: list[float], source_updated_at: str
    ) -> StoredEmbedding:
        stored = StoredEmbedding(
            resource_id=resource_id,
            vector=vector,
            dimensions=len(vector),
            source_updated_at=source_updated_at,
            indexed_at=utc_now_iso(),
        )
        self._conn.execute(
            """
            INSERT INTO curriculum_resource_embeddings(resource_id, vector, dimensions, source_updated_at, indexed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(resource_id) DO UPDATE SET
                vector = excluded.vector,
                dimensions = excluded.dimensions,
                source_updated_at = excluded.source_updated_at,
                indexed_at = excluded.indexed_at
            """,
            (
                stored.resource_id,
                json.dumps(stored.vector),
                stored.dimensions,
                stored.source_updated_at,
                stored.indexed_at,
            ),
        )
        self._conn.commit()
        return stored


class InMemoryEmbeddingStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredEmbedding] = {}

    def get(self, resource_id: str) -> StoredEmbedding | None:
        return self._items.get(resource_id)

    def upsert(
        self, *, resource_id: str, vector: list[float], source_updated_at: str
    ) -> StoredEmbedding:
        stored = StoredEmbedding(
            resource_id=resource_id,
            vector=list(vector),
            dimensions=len(vector),
            source_updated_at=source_updated_at,
            indexed_at=utc_now_iso(),
        )
        self._items[resource_id] = stored
        return stored
