from __future__ import annotations

import sqlite3

from dibble.models.session_adaptation import WithinSessionControllerState


class SQLiteWithinSessionControllerStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, session: WithinSessionControllerState) -> WithinSessionControllerState:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
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
            connection.commit()
        return session

    def get(self, learning_session_id: str) -> WithinSessionControllerState | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM within_session_controller_states WHERE learning_session_id = ?",
                (learning_session_id,),
            ).fetchone()
        if row is None:
            return None
        return WithinSessionControllerState.model_validate_json(row[0])
