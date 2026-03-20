from __future__ import annotations

import sqlite3

from dibble.models.session_adaptation import WithinSessionControllerState


class SQLiteWithinSessionControllerStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(
        self, session: WithinSessionControllerState
    ) -> WithinSessionControllerState:
        self._conn.execute(
            """
            INSERT INTO within_session_controller_states(learning_session_id, student_id, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(learning_session_id) DO UPDATE SET
                student_id = excluded.student_id,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                session.learning_session_id,
                str(session.student_id),
                session.model_dump_json(),
                session.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return session

    def get(self, learning_session_id: str) -> WithinSessionControllerState | None:
        row = self._conn.execute(
            "SELECT payload FROM within_session_controller_states WHERE learning_session_id = ?",
            (learning_session_id,),
        ).fetchone()
        if row is None:
            return None
        return WithinSessionControllerState.model_validate_json(row[0])
