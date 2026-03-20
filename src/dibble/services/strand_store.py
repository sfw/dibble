from __future__ import annotations

import sqlite3

from dibble.models.curriculum import Strand, StrandUpsert


class SQLiteStrandStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, strand: StrandUpsert) -> Strand:
        persisted = Strand(**strand.model_dump())
        self._conn.execute(
            """
            INSERT INTO strands(strand_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(strand_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                persisted.strand_id,
                persisted.model_dump_json(),
                persisted.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return persisted

    def get(self, strand_id: str) -> Strand | None:
        row = self._conn.execute(
            "SELECT payload FROM strands WHERE strand_id = ?",
            (strand_id,),
        ).fetchone()
        if row is None:
            return None
        return Strand.model_validate_json(row[0])

    def list(self) -> list[Strand]:
        rows = self._conn.execute(
            "SELECT payload FROM strands ORDER BY updated_at DESC, strand_id ASC"
        ).fetchall()

        return [Strand.model_validate_json(row[0]) for row in rows]

    def list_for_course(self, course_id: str) -> list[Strand]:
        all_strands = self.list()
        return [strand for strand in all_strands if strand.course_id == course_id]
