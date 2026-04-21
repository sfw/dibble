from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import CurriculumSnapshotDiff


class SQLiteCurriculumSnapshotDiffStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, diff: CurriculumSnapshotDiff) -> CurriculumSnapshotDiff:
        self._conn.execute(
            """
            INSERT INTO curriculum_snapshot_diffs(
                diff_id,
                source_snapshot_id,
                target_snapshot_id,
                payload,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(diff_id) DO UPDATE SET
                source_snapshot_id = excluded.source_snapshot_id,
                target_snapshot_id = excluded.target_snapshot_id,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                diff.diff_id,
                diff.source_snapshot_id,
                diff.target_snapshot_id,
                diff.model_dump_json(),
                diff.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return diff

    def get(self, diff_id: str) -> CurriculumSnapshotDiff | None:
        row = self._conn.execute(
            "SELECT payload FROM curriculum_snapshot_diffs WHERE diff_id = ?",
            (diff_id,),
        ).fetchone()
        if row is None:
            return None
        return CurriculumSnapshotDiff.model_validate_json(row[0])

    def list(self) -> list[CurriculumSnapshotDiff]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM curriculum_snapshot_diffs
            ORDER BY updated_at DESC, diff_id ASC
            """
        ).fetchall()
        return [CurriculumSnapshotDiff.model_validate_json(row[0]) for row in rows]

    def get_for_snapshots(
        self, *, source_snapshot_id: str, target_snapshot_id: str
    ) -> CurriculumSnapshotDiff | None:
        row = self._conn.execute(
            """
            SELECT payload
            FROM curriculum_snapshot_diffs
            WHERE source_snapshot_id = ? AND target_snapshot_id = ?
            LIMIT 1
            """,
            (source_snapshot_id, target_snapshot_id),
        ).fetchone()
        if row is None:
            return None
        return CurriculumSnapshotDiff.model_validate_json(row[0])
