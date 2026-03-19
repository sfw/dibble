from __future__ import annotations

import json
import sqlite3

from dibble.models.auth import User


class SQLiteUserStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def _row_to_user(self, row: tuple[str, ...]) -> User:
        return User(
            user_id=row[0],
            display_name=row[1],
            role=row[2],
            api_key_hash=row[3],
            passphrase_hash=row[4],
            learner_id=row[5],
            classroom_ids=json.loads(row[6]),
            created_at=row[7],
            updated_at=row[8],
        )

    def create(self, user: User) -> User:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO users(
                    user_id, display_name, role, api_key_hash, passphrase_hash,
                    learner_id, classroom_ids, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.display_name,
                    user.role,
                    user.api_key_hash,
                    user.passphrase_hash,
                    user.learner_id,
                    json.dumps(user.classroom_ids),
                    user.created_at,
                    user.updated_at,
                ),
            )
            connection.commit()
        return user

    def get(self, user_id: str) -> User | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
                " learner_id, classroom_ids, created_at, updated_at"
                " FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_api_key_hash(self, api_key_hash: str) -> User | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
                " learner_id, classroom_ids, created_at, updated_at"
                " FROM users WHERE api_key_hash = ?",
                (api_key_hash,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_passphrase_hash(self, passphrase_hash: str) -> User | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
                " learner_id, classroom_ids, created_at, updated_at"
                " FROM users WHERE passphrase_hash = ?",
                (passphrase_hash,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def list(self) -> list[User]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT user_id, display_name, role, api_key_hash, passphrase_hash,"
                " learner_id, classroom_ids, created_at, updated_at"
                " FROM users ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def update(self, user: User) -> User:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE users SET
                    display_name = ?,
                    role = ?,
                    api_key_hash = ?,
                    passphrase_hash = ?,
                    learner_id = ?,
                    classroom_ids = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    user.display_name,
                    user.role,
                    user.api_key_hash,
                    user.passphrase_hash,
                    user.learner_id,
                    json.dumps(user.classroom_ids),
                    user.updated_at,
                    user.user_id,
                ),
            )
            connection.commit()
        return user

    def delete(self, user_id: str) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM users WHERE user_id = ?",
                (user_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0
