from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from dibble.models.guardian import GuardianInvite


class SQLiteGuardianInviteStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, invite: GuardianInvite) -> GuardianInvite:
        self._conn.execute(
            """
            INSERT INTO guardian_invites(code, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                invite.code,
                invite.model_dump_json(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()
        return invite

    def get(self, code: str) -> GuardianInvite | None:
        row = self._conn.execute(
            "SELECT payload FROM guardian_invites WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return None
        return GuardianInvite.model_validate_json(row[0])

    def list(self) -> list[GuardianInvite]:
        rows = self._conn.execute(
            "SELECT payload FROM guardian_invites ORDER BY updated_at DESC"
        ).fetchall()
        return [GuardianInvite.model_validate_json(row[0]) for row in rows]
