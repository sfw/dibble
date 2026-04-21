from __future__ import annotations

import json
import sqlite3

from dibble.models.household import LearnerRelationshipState


class SQLiteLearnerRelationshipStateStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, state: LearnerRelationshipState) -> LearnerRelationshipState:
        self._conn.execute(
            """
            INSERT INTO learner_relationship_states(
                household_id, learner_id, payload, updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(household_id, learner_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                state.household_id,
                state.learner_id,
                state.model_dump_json(),
                state.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return state

    def get(
        self, *, household_id: str, learner_id: str
    ) -> LearnerRelationshipState | None:
        row = self._conn.execute(
            """
            SELECT payload FROM learner_relationship_states
            WHERE household_id = ? AND learner_id = ?
            """,
            (household_id, learner_id),
        ).fetchone()
        if row is None:
            return None
        return LearnerRelationshipState.model_validate(json.loads(str(row[0])))

    def list_for_household(
        self, *, household_id: str
    ) -> list[LearnerRelationshipState]:
        rows = self._conn.execute(
            """
            SELECT payload FROM learner_relationship_states
            WHERE household_id = ?
            ORDER BY learner_id
            """,
            (household_id,),
        ).fetchall()
        return [
            LearnerRelationshipState.model_validate(json.loads(str(payload)))
            for (payload,) in rows
        ]
