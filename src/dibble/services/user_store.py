from __future__ import annotations

import json
import sqlite3

from dibble.models.auth import User


class SQLiteUserStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def _row_to_user(self, row: tuple[str, ...]) -> User:
        return User(
            user_id=row[0],
            display_name=row[1],
            role=row[2],
            api_key_hash=row[3],
            passphrase_hash=row[4],
            learner_id=row[5],
            household_id=row[6],
            section_ids=json.loads(row[7]),
            created_at=row[8],
            updated_at=row[9],
        )

    def create(self, user: User) -> User:
        self._conn.execute(
            """
            INSERT INTO users(
                user_id, display_name, role, api_key_hash, passphrase_hash,
                learner_id, household_id, section_ids, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.user_id,
                user.display_name,
                user.role,
                user.api_key_hash,
                user.passphrase_hash,
                user.learner_id,
                user.household_id,
                json.dumps(user.section_ids),
                user.created_at,
                user.updated_at,
            ),
        )
        self._conn.commit()
        return user

    def get(self, user_id: str) -> User | None:
        row = self._conn.execute(
            "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
            " learner_id, household_id, section_ids, created_at, updated_at"
            " FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_api_key_hash(self, api_key_hash: str) -> User | None:
        row = self._conn.execute(
            "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
            " learner_id, household_id, section_ids, created_at, updated_at"
            " FROM users WHERE api_key_hash = ?",
            (api_key_hash,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_passphrase_hash(self, passphrase_hash: str) -> User | None:
        row = self._conn.execute(
            "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
            " learner_id, household_id, section_ids, created_at, updated_at"
            " FROM users WHERE passphrase_hash = ?",
            (passphrase_hash,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def list(self) -> list[User]:
        rows = self._conn.execute(
            "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
            " learner_id, household_id, section_ids, created_at, updated_at"
            " FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def update(self, user: User) -> User:
        self._conn.execute(
            """
            UPDATE users SET
                display_name = ?,
                role = ?,
                api_key_hash = ?,
                passphrase_hash = ?,
                learner_id = ?,
                household_id = ?,
                section_ids = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                user.display_name,
                user.role,
                user.api_key_hash,
                user.passphrase_hash,
                user.learner_id,
                user.household_id,
                json.dumps(user.section_ids),
                user.updated_at,
                user.user_id,
            ),
        )
        self._conn.commit()
        return user

    def delete(self, user_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0
