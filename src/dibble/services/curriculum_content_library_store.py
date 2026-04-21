from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from dibble.models.generation import CurriculumContentKey, CurriculumLibraryEntry


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class SQLiteCurriculumContentLibraryStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
        now: datetime | None = None,
    ) -> CurriculumLibraryEntry | None:
        row = self._conn.execute(
            """
            SELECT cache_key, content_key_payload, content_payload, storage_scope, source_generation_id, created_at, expires_at
            FROM curriculum_content_library
            WHERE cache_key = ?
            """,
            (key.cache_key(),),
        ).fetchone()
        if row is None:
            return None
        entry = self._entry_from_row(row)
        comparison_time = now or datetime.now(timezone.utc)
        expires_at = entry.content.expires_at
        if expires_at is not None and expires_at <= comparison_time:
            return None
        return entry

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry:
        self._conn.execute(
            """
            INSERT INTO curriculum_content_library(
                cache_key,
                content_key_payload,
                content_payload,
                storage_scope,
                source_generation_id,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                content_key_payload = excluded.content_key_payload,
                content_payload = excluded.content_payload,
                storage_scope = excluded.storage_scope,
                source_generation_id = excluded.source_generation_id,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at
            """,
            (
                entry.cache_key,
                entry.content_key.model_dump_json(),
                entry.content.model_dump_json(),
                entry.storage_scope.value,
                entry.source_generation_id,
                entry.content.created_at.isoformat(),
                entry.content.expires_at.isoformat()
                if entry.content.expires_at is not None
                else None,
            ),
        )
        self._conn.commit()
        return entry

    def _entry_from_row(self, row: tuple[object, ...]) -> CurriculumLibraryEntry:
        (
            cache_key,
            content_key_payload,
            content_payload,
            storage_scope,
            source_generation_id,
            _created_at,
            _expires_at,
        ) = row
        return CurriculumLibraryEntry.model_validate(
            {
                "cache_key": cache_key,
                "content_key": json.loads(str(content_key_payload)),
                "content": json.loads(str(content_payload)),
                "storage_scope": storage_scope,
                "source_generation_id": source_generation_id,
            }
        )
