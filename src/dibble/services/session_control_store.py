from __future__ import annotations

import sqlite3
from uuid import UUID

from dibble.models.session_control import SessionControlState


class SQLiteSessionControlStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, session: SessionControlState) -> SessionControlState:
        self._conn.execute(
            """
            INSERT INTO session_control_states(learning_session_id, student_id, goal_id, trajectory_id, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(learning_session_id) DO UPDATE SET
                student_id = excluded.student_id,
                goal_id = excluded.goal_id,
                trajectory_id = excluded.trajectory_id,
                status = excluded.status,
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                session.learning_session_id,
                str(session.student_id),
                session.goal_id,
                session.trajectory_id,
                session.status,
                session.model_dump_json(),
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return session

    def get(self, learning_session_id: str) -> SessionControlState | None:
        row = self._conn.execute(
            "SELECT payload FROM session_control_states WHERE learning_session_id = ?",
            (learning_session_id,),
        ).fetchone()
        if row is None:
            return None
        return SessionControlState.model_validate_json(row[0])

    def get_active_for_student(self, *, student_id: UUID) -> SessionControlState | None:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM session_control_states
            WHERE student_id = ?
            ORDER BY updated_at DESC, learning_session_id DESC
            """,
            (str(student_id),),
        ).fetchall()
        for row in rows:
            session = SessionControlState.model_validate_json(row[0])
            if session.status not in {"completed", "archived"}:
                return session
        return None
