from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import FrameworkImportArtifact


class SQLiteFrameworkImportArtifactStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, artifact: FrameworkImportArtifact) -> FrameworkImportArtifact:
        self._conn.execute(
            """
            INSERT INTO framework_import_artifacts(
                artifact_id,
                import_id,
                artifact_kind,
                artifact_key,
                payload,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(import_id, artifact_kind, artifact_key) DO UPDATE SET
                artifact_id = excluded.artifact_id,
                payload = excluded.payload,
                created_at = excluded.created_at
            """,
            (
                artifact.artifact_id,
                artifact.import_id,
                artifact.artifact_kind.value,
                artifact.artifact_key,
                artifact.model_dump_json(),
                artifact.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return artifact

    def get(self, artifact_id: str) -> FrameworkImportArtifact | None:
        row = self._conn.execute(
            "SELECT payload FROM framework_import_artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if row is None:
            return None
        return FrameworkImportArtifact.model_validate_json(row[0])

    def list_for_import(self, import_id: str) -> list[FrameworkImportArtifact]:
        rows = self._conn.execute(
            """
            SELECT payload FROM framework_import_artifacts
            WHERE import_id = ?
            ORDER BY artifact_kind ASC, artifact_key ASC
            """,
            (import_id,),
        ).fetchall()
        return [FrameworkImportArtifact.model_validate_json(row[0]) for row in rows]
