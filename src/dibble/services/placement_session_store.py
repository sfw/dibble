from __future__ import annotations

import sqlite3

from dibble.models.placement import PlacementSession


class SQLitePlacementSessionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, session: PlacementSession) -> PlacementSession:
        self._conn.execute(
            """
            INSERT INTO placement_sessions(session_id, student_id, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                student_id = excluded.student_id,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                session.session_id,
                session.student_id,
                session.model_dump_json(),
                session.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return session

    def get(self, session_id: str) -> PlacementSession | None:
        row = self._conn.execute(
            "SELECT payload FROM placement_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return PlacementSession.model_validate_json(row[0])

    def list_for_student(
        self, *, student_id: str, limit: int = 20
    ) -> list[PlacementSession]:
        rows = self._conn.execute(
            """
            SELECT payload FROM placement_sessions
            WHERE student_id = ?
            ORDER BY updated_at DESC, session_id DESC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
        return [PlacementSession.model_validate_json(row[0]) for row in rows]
