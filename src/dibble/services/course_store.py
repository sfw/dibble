from __future__ import annotations

import sqlite3

from dibble.models.course import Course, CourseUpsert


class SQLiteCourseStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, course: CourseUpsert) -> Course:
        persisted = Course(**course.model_dump())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
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
            connection.commit()
        return persisted

    def get(self, course_id: str) -> Course | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM courses WHERE course_id = ?",
                (course_id,),
            ).fetchone()
        if row is None:
            return None
        return Course.model_validate_json(row[0])

    def list(self) -> list[Course]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM courses ORDER BY updated_at DESC, course_id ASC"
            ).fetchall()
        return [Course.model_validate_json(row[0]) for row in rows]
