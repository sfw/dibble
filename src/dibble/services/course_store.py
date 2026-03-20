from __future__ import annotations

import sqlite3

from dibble.models.course import Course, CourseUpsert


class SQLiteCourseStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, course: CourseUpsert) -> Course:
        persisted = Course(**course.model_dump())
        self._conn.execute(
            """
            INSERT INTO courses(course_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                persisted.course_id,
                persisted.model_dump_json(),
                persisted.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return persisted

    def get(self, course_id: str) -> Course | None:
        row = self._conn.execute(
            "SELECT payload FROM courses WHERE course_id = ?",
            (course_id,),
        ).fetchone()
        if row is None:
            return None
        return Course.model_validate_json(row[0])

    def list(self) -> list[Course]:
        rows = self._conn.execute(
            "SELECT payload FROM courses ORDER BY updated_at DESC, course_id ASC"
        ).fetchall()
        return [Course.model_validate_json(row[0]) for row in rows]
