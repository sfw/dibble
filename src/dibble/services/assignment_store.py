from __future__ import annotations

import sqlite3

from dibble.models.assignment import Assignment


class SQLiteAssignmentStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, assignment: Assignment) -> Assignment:
        self._conn.execute(
            """
            INSERT INTO assignments(assignment_id, student_id, teacher_id, section_id, status, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(assignment_id) DO UPDATE SET
                student_id = excluded.student_id,
                teacher_id = excluded.teacher_id,
                section_id = excluded.section_id,
                status = excluded.status,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                assignment.assignment_id,
                assignment.student_id,
                assignment.teacher_id,
                assignment.section_id,
                assignment.status.value,
                assignment.model_dump_json(),
                assignment.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return assignment

    def get(self, assignment_id: str) -> Assignment | None:
        row = self._conn.execute(
            "SELECT payload FROM assignments WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()
        if row is None:
            return None
        return Assignment.model_validate_json(row[0])

    def list(self) -> list[Assignment]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM assignments
            ORDER BY updated_at DESC, assignment_id DESC
            """
        ).fetchall()
        return [Assignment.model_validate_json(row[0]) for row in rows]

    def list_for_student(
        self, *, student_id: str, limit: int = 20, offset: int = 0
    ) -> list[Assignment]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM assignments
            WHERE student_id = ?
            ORDER BY updated_at DESC, assignment_id DESC
            LIMIT ? OFFSET ?
            """,
            (student_id, limit, offset),
        ).fetchall()
        return [Assignment.model_validate_json(row[0]) for row in rows]

    def count_for_student(self, *, student_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM assignments WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        return row[0] if row else 0

    def list_for_section(
        self, *, section_id: str, limit: int = 50, offset: int = 0
    ) -> list[Assignment]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM assignments
            WHERE section_id = ?
            ORDER BY updated_at DESC, assignment_id DESC
            LIMIT ? OFFSET ?
            """,
            (section_id, limit, offset),
        ).fetchall()
        return [Assignment.model_validate_json(row[0]) for row in rows]

    def list_for_teacher(
        self, *, teacher_id: str, limit: int = 50, offset: int = 0
    ) -> list[Assignment]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM assignments
            WHERE teacher_id = ?
            ORDER BY updated_at DESC, assignment_id DESC
            LIMIT ? OFFSET ?
            """,
            (teacher_id, limit, offset),
        ).fetchall()
        return [Assignment.model_validate_json(row[0]) for row in rows]
