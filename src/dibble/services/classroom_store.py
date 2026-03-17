from __future__ import annotations

import sqlite3

from dibble.models.classroom import Classroom, ClassroomUpsert


class SQLiteClassroomStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, classroom: ClassroomUpsert) -> Classroom:
        persisted = Classroom(**classroom.model_dump())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
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
            connection.commit()
        return persisted

    def get(self, classroom_id: str) -> Classroom | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM classrooms WHERE classroom_id = ?",
                (classroom_id,),
            ).fetchone()
        if row is None:
            return None
        return Classroom.model_validate_json(row[0])

    def list(self) -> list[Classroom]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM classrooms ORDER BY updated_at DESC, classroom_id ASC"
            ).fetchall()
        return [Classroom.model_validate_json(row[0]) for row in rows]
