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
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def get(self, resource_id: str) -> StoredEmbedding | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
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

    def upsert(self, *, resource_id: str, vector: list[float], source_updated_at: str) -> StoredEmbedding:
        stored = StoredEmbedding(
            resource_id=resource_id,
            vector=vector,
            dimensions=len(vector),
            source_updated_at=source_updated_at,
            indexed_at=utc_now_iso(),
        )
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
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
            connection.commit()
        return stored
