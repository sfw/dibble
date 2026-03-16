from __future__ import annotations

import sqlite3

from dibble.models.remediation import RemediationWorkflowSession


class SQLiteRemediationSessionStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, session: RemediationWorkflowSession) -> RemediationWorkflowSession:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO remediation_workflow_sessions(session_id, student_id, payload, updated_at)
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
            connection.commit()
        return session

    def get(self, session_id: str) -> RemediationWorkflowSession | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM remediation_workflow_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return RemediationWorkflowSession.model_validate_json(row[0])
