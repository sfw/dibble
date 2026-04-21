from __future__ import annotations

import sqlite3

from dibble.models.rollout import RolloutPolicy


class SQLiteRolloutPolicyStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, policy: RolloutPolicy) -> RolloutPolicy:
        self._conn.execute(
            """
            INSERT INTO rollout_policies(policy_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(policy_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                policy.policy_id,
                policy.model_dump_json(),
                policy.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return policy

    def get(self, policy_id: str = "default") -> RolloutPolicy | None:
        row = self._conn.execute(
            "SELECT payload FROM rollout_policies WHERE policy_id = ?",
            (policy_id,),
        ).fetchone()
        if row is None:
            return None
        return RolloutPolicy.model_validate_json(row[0])
