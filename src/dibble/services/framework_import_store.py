from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import FrameworkImport


class SQLiteFrameworkImportStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, framework_import: FrameworkImport) -> FrameworkImport:
        self._conn.execute(
            """
            INSERT INTO framework_imports(
                import_id,
                framework_id,
                source_fingerprint,
                payload,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(import_id) DO UPDATE SET
                framework_id = excluded.framework_id,
                source_fingerprint = excluded.source_fingerprint,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                framework_import.import_id,
                framework_import.framework_id,
                framework_import.source_fingerprint,
                framework_import.model_dump_json(),
                framework_import.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return framework_import

    def get(self, import_id: str) -> FrameworkImport | None:
        row = self._conn.execute(
            "SELECT payload FROM framework_imports WHERE import_id = ?",
            (import_id,),
        ).fetchone()
        if row is None:
            return None
        return FrameworkImport.model_validate_json(row[0])

    def list(self) -> list[FrameworkImport]:
        rows = self._conn.execute(
            "SELECT payload FROM framework_imports ORDER BY updated_at DESC, import_id ASC"
        ).fetchall()
        return [FrameworkImport.model_validate_json(row[0]) for row in rows]

    def list_for_framework(self, framework_id: str) -> list[FrameworkImport]:
        rows = self._conn.execute(
            """
            SELECT payload FROM framework_imports
            WHERE framework_id = ?
            ORDER BY updated_at DESC, import_id ASC
            """,
            (framework_id,),
        ).fetchall()
        return [FrameworkImport.model_validate_json(row[0]) for row in rows]

    def find_by_fingerprint(
        self, *, framework_id: str, source_fingerprint: str
    ) -> FrameworkImport | None:
        row = self._conn.execute(
            """
            SELECT payload FROM framework_imports
            WHERE framework_id = ? AND source_fingerprint = ?
            ORDER BY updated_at DESC, import_id ASC
            LIMIT 1
            """,
            (framework_id, source_fingerprint),
        ).fetchone()
        if row is None:
            return None
        return FrameworkImport.model_validate_json(row[0])
