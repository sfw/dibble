from __future__ import annotations

import sqlite3

from dibble.models.assessment import SocraticAssessmentSession


class SQLiteSocraticSessionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, session: SocraticAssessmentSession) -> SocraticAssessmentSession:
        self._conn.execute(
            """
            INSERT INTO socratic_assessment_sessions(session_id, student_id, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                student_id = excluded.student_id,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                session.session_id,
                str(session.student_id),
                session.model_dump_json(),
                session.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return session

    def get(self, session_id: str) -> SocraticAssessmentSession | None:
        row = self._conn.execute(
            "SELECT payload FROM socratic_assessment_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return SocraticAssessmentSession.model_validate_json(row[0])

    def list_recent_for_student(
        self, *, student_id: str, limit: int = 20, offset: int = 0
    ) -> list[SocraticAssessmentSession]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM socratic_assessment_sessions
            WHERE student_id = ?
            ORDER BY updated_at DESC, session_id DESC
            LIMIT ? OFFSET ?
            """,
            (student_id, limit, offset),
        ).fetchall()
        return [SocraticAssessmentSession.model_validate_json(row[0]) for row in rows]
