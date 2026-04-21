from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from dibble.models.generation import (
    CurriculumContentKey,
    CurriculumLibraryEntry,
    CurriculumLibraryProvenance,
)


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
            SELECT
                cache_key,
                selection_key,
                content_key_payload,
                content_payload,
                provenance_payload,
                storage_scope,
                source_generation_id,
                created_at,
                expires_at
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

    def list_candidate_entries(
        self,
        *,
        key: CurriculumContentKey,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[CurriculumLibraryEntry]:
        rows = self._conn.execute(
            """
            SELECT
                cache_key,
                selection_key,
                content_key_payload,
                content_payload,
                provenance_payload,
                storage_scope,
                source_generation_id,
                created_at,
                expires_at
            FROM curriculum_content_library
            WHERE selection_key = ?
            ORDER BY created_at DESC, cache_key DESC
            LIMIT ?
            """,
            (key.selection_key(), limit),
        ).fetchall()
        comparison_time = now or datetime.now(timezone.utc)
        entries: list[CurriculumLibraryEntry] = []
        for row in rows:
            entry = self._entry_from_row(row)
            expires_at = entry.content.expires_at
            if expires_at is not None and expires_at <= comparison_time:
                continue
            entries.append(entry)
        return entries

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry:
        self._conn.execute(
            """
            INSERT INTO curriculum_content_library(
                cache_key,
                selection_key,
                content_key_payload,
                content_payload,
                provenance_payload,
                storage_scope,
                source_generation_id,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                selection_key = excluded.selection_key,
                content_key_payload = excluded.content_key_payload,
                content_payload = excluded.content_payload,
                provenance_payload = excluded.provenance_payload,
                storage_scope = excluded.storage_scope,
                source_generation_id = excluded.source_generation_id,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at
            """,
            (
                entry.cache_key,
                entry.content_key.selection_key(),
                entry.content_key.model_dump_json(),
                entry.content.model_dump_json(),
                entry.provenance.model_dump_json()
                if entry.provenance is not None
                else None,
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

    def record_outcome(
        self,
        *,
        source_generation_id: str,
        outcome_score: float,
        engagement_score: float | None,
        progress_score: float | None,
    ) -> list[CurriculumLibraryEntry]:
        rows = self._conn.execute(
            """
            SELECT
                cache_key,
                selection_key,
                content_key_payload,
                content_payload,
                provenance_payload,
                storage_scope,
                source_generation_id,
                created_at,
                expires_at
            FROM curriculum_content_library
            WHERE source_generation_id = ?
            """,
            (source_generation_id,),
        ).fetchall()
        updated_entries: list[CurriculumLibraryEntry] = []
        observed_at = datetime.now(timezone.utc)
        for row in rows:
            entry = self._entry_from_row(row)
            provenance = entry.provenance or CurriculumLibraryProvenance(
                source_generation_id=entry.source_generation_id or source_generation_id
            )
            count = provenance.outcome_sample_count
            next_count = count + 1
            next_outcome_average = _rolling_average(
                provenance.average_outcome_score,
                outcome_score,
                count,
            )
            next_engagement_average = _rolling_average(
                provenance.average_engagement_score,
                engagement_score,
                count,
            )
            next_progress_average = _rolling_average(
                provenance.average_progress_score,
                progress_score,
                count,
            )
            positive_count = round(provenance.historical_success_rate * count)
            if outcome_score >= 0.65:
                positive_count += 1
            updated_provenance = provenance.model_copy(
                update={
                    "outcome_sample_count": next_count,
                    "average_outcome_score": next_outcome_average,
                    "average_engagement_score": next_engagement_average,
                    "average_progress_score": next_progress_average,
                    "historical_success_rate": round(positive_count / next_count, 2),
                    "last_outcome_at": observed_at,
                }
            )
            updated_entry = entry.model_copy(update={"provenance": updated_provenance})
            updated_entries.append(self.upsert_entry(entry=updated_entry))
        return updated_entries

    def _entry_from_row(self, row: tuple[object, ...]) -> CurriculumLibraryEntry:
        (
            cache_key,
            _selection_key,
            content_key_payload,
            content_payload,
            provenance_payload,
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
                "provenance": (
                    json.loads(str(provenance_payload))
                    if provenance_payload is not None
                    else None
                ),
                "storage_scope": storage_scope,
                "source_generation_id": source_generation_id,
            }
        )


def _rolling_average(
    current_average: float,
    observed_value: float | None,
    current_count: int,
) -> float:
    if observed_value is None:
        return round(current_average, 2)
    if current_count <= 0:
        return round(observed_value, 2)
    return round(
        ((current_average * current_count) + observed_value) / (current_count + 1),
        2,
    )
