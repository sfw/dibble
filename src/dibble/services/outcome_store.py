from __future__ import annotations

import sqlite3

from dibble.models.curriculum import Outcome, OutcomeUpsert


class SQLiteOutcomeStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, outcome: OutcomeUpsert) -> Outcome:
        persisted = Outcome(**outcome.model_dump())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
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
            connection.commit()
        return persisted

    def get(self, outcome_id: str) -> Outcome | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM outcomes WHERE outcome_id = ?",
                (outcome_id,),
            ).fetchone()
        if row is None:
            return None
        return Outcome.model_validate_json(row[0])

    def list(self) -> list[Outcome]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM outcomes ORDER BY updated_at DESC, outcome_id ASC"
            ).fetchall()

        return [Outcome.model_validate_json(row[0]) for row in rows]
