from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(slots=True)
class StoredAuthSession:
    session_id: str
    principal_id: str
    role: str
    refresh_token_hash: str
    created_at: str
    access_expires_at: str
    refresh_expires_at: str
    revoked_at: str | None = None


class SQLiteAuthSessionStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def get(self, session_id: str) -> StoredAuthSession | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT session_id, principal_id, role, refresh_token_hash, created_at,
                       access_expires_at, refresh_expires_at, revoked_at
                FROM auth_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            return None

        return StoredAuthSession(*row)

    def upsert(self, session: StoredAuthSession) -> StoredAuthSession:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions(
                    session_id, principal_id, role, refresh_token_hash, created_at,
                    access_expires_at, refresh_expires_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    principal_id = excluded.principal_id,
                    role = excluded.role,
                    refresh_token_hash = excluded.refresh_token_hash,
                    access_expires_at = excluded.access_expires_at,
                    refresh_expires_at = excluded.refresh_expires_at,
                    revoked_at = excluded.revoked_at
                """,
                (
                    session.session_id,
                    session.principal_id,
                    session.role,
                    session.refresh_token_hash,
                    session.created_at,
                    session.access_expires_at,
                    session.refresh_expires_at,
                    session.revoked_at,
                ),
            )
            connection.commit()
        return session

    def revoke(self, session_id: str, *, revoked_at: str) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE session_id = ?",
                (revoked_at, session_id),
            )
            connection.commit()
