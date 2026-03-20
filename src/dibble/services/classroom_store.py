from __future__ import annotations

import sqlite3

from dibble.models.classroom import Classroom, ClassroomUpsert


class SQLiteClassroomStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, classroom: ClassroomUpsert) -> Classroom:
        persisted = Classroom(**classroom.model_dump())
        self._conn.execute(
            """
            INSERT INTO classrooms(classroom_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(classroom_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                persisted.classroom_id,
                persisted.model_dump_json(),
                persisted.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return persisted

    def get(self, classroom_id: str) -> Classroom | None:
        row = self._conn.execute(
            "SELECT payload FROM classrooms WHERE classroom_id = ?",
            (classroom_id,),
        ).fetchone()
        if row is None:
            return None
        return Classroom.model_validate_json(row[0])

    def list(self) -> list[Classroom]:
        rows = self._conn.execute(
            "SELECT payload FROM classrooms ORDER BY updated_at DESC, classroom_id ASC"
        ).fetchall()
        return [Classroom.model_validate_json(row[0]) for row in rows]
