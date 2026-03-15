from __future__ import annotations

import sqlite3
from uuid import uuid4

from dibble.models.observations import LearnerObservation, LearnerObservationCreate


class SQLiteObservationStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def append(self, *, student_id: str, observation: LearnerObservationCreate) -> LearnerObservation:
        persisted = LearnerObservation(
            observation_id=str(uuid4()),
            student_id=student_id,
            **observation.model_dump(),
        )
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO learner_observations(observation_id, student_id, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    persisted.observation_id,
                    str(persisted.student_id),
                    persisted.model_dump_json(),
                    persisted.created_at.isoformat(),
                ),
            )
            connection.commit()
        return persisted

    def list_recent(self, *, student_id: str, limit: int = 20) -> list[LearnerObservation]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT payload FROM learner_observations
                WHERE student_id = ?
                ORDER BY created_at DESC, observation_id DESC
                LIMIT ?
                """,
                (student_id, limit),
            ).fetchall()

        return [LearnerObservation.model_validate_json(row[0]) for row in rows]
