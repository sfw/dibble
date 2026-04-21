from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import PublishedCurriculumSnapshot


class SQLitePublishedCurriculumSnapshotStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(
        self, snapshot: PublishedCurriculumSnapshot
    ) -> PublishedCurriculumSnapshot:
        self._conn.execute(
            """
            INSERT INTO published_curriculum_snapshots(
                snapshot_id,
                framework_id,
                framework_import_id,
                payload,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                framework_id = excluded.framework_id,
                framework_import_id = excluded.framework_import_id,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                snapshot.snapshot_id,
                snapshot.framework_id,
                snapshot.framework_import_id,
                snapshot.model_dump_json(),
                snapshot.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return snapshot

    def get(self, snapshot_id: str) -> PublishedCurriculumSnapshot | None:
        row = self._conn.execute(
            "SELECT payload FROM published_curriculum_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return PublishedCurriculumSnapshot.model_validate_json(row[0])

    def list(self) -> list[PublishedCurriculumSnapshot]:
        rows = self._conn.execute(
            """
            SELECT payload FROM published_curriculum_snapshots
            ORDER BY updated_at DESC, snapshot_id ASC
            """
        ).fetchall()
        return [PublishedCurriculumSnapshot.model_validate_json(row[0]) for row in rows]

    def get_for_import(self, import_id: str) -> PublishedCurriculumSnapshot | None:
        row = self._conn.execute(
            """
            SELECT payload FROM published_curriculum_snapshots
            WHERE framework_import_id = ?
            ORDER BY updated_at DESC, snapshot_id ASC
            LIMIT 1
            """,
            (import_id,),
        ).fetchone()
        if row is None:
            return None
        return PublishedCurriculumSnapshot.model_validate_json(row[0])
