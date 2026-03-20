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
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get(self, session_id: str) -> StoredAuthSession | None:
        row = self._conn.execute(
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
        self._conn.execute(
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
        self._conn.commit()
        return session

    def revoke(self, session_id: str, *, revoked_at: str) -> None:
        self._conn.execute(
            "UPDATE auth_sessions SET revoked_at = ? WHERE session_id = ?",
            (revoked_at, session_id),
        )
        self._conn.commit()
