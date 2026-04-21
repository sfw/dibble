from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import CurriculumFramework


class SQLiteCurriculumFrameworkStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, framework: CurriculumFramework) -> CurriculumFramework:
        self._conn.execute(
            """
            INSERT INTO curriculum_frameworks(framework_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(framework_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                framework.framework_id,
                framework.model_dump_json(),
                framework.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return framework

    def get(self, framework_id: str) -> CurriculumFramework | None:
        row = self._conn.execute(
            "SELECT payload FROM curriculum_frameworks WHERE framework_id = ?",
            (framework_id,),
        ).fetchone()
        if row is None:
            return None
        return CurriculumFramework.model_validate_json(row[0])

    def list(self) -> list[CurriculumFramework]:
        rows = self._conn.execute(
            "SELECT payload FROM curriculum_frameworks ORDER BY updated_at DESC, framework_id ASC"
        ).fetchall()
        return [CurriculumFramework.model_validate_json(row[0]) for row in rows]
