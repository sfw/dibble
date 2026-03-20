from __future__ import annotations

import sqlite3

from dibble.models.curriculum import Outcome, OutcomeUpsert


class SQLiteOutcomeStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, outcome: OutcomeUpsert) -> Outcome:
        persisted = Outcome(**outcome.model_dump())
        self._conn.execute(
            """
            INSERT INTO outcomes(outcome_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(outcome_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                persisted.outcome_id,
                persisted.model_dump_json(),
                persisted.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return persisted

    def get(self, outcome_id: str) -> Outcome | None:
        row = self._conn.execute(
            "SELECT payload FROM outcomes WHERE outcome_id = ?",
            (outcome_id,),
        ).fetchone()
        if row is None:
            return None
        return Outcome.model_validate_json(row[0])

    def list(self) -> list[Outcome]:
        rows = self._conn.execute(
            "SELECT payload FROM outcomes ORDER BY updated_at DESC, outcome_id ASC"
        ).fetchall()

        return [Outcome.model_validate_json(row[0]) for row in rows]
