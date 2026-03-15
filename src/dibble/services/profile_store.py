from __future__ import annotations

import sqlite3
from uuid import UUID

from dibble.models.profile import LearnerProfile


class InMemoryProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[UUID, LearnerProfile] = {}

    def upsert(self, profile: LearnerProfile) -> LearnerProfile:
        self._profiles[profile.student_id] = profile
        return profile

    def get(self, student_id: UUID) -> LearnerProfile | None:
        return self._profiles.get(student_id)


class SQLiteProfileStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, profile: LearnerProfile) -> LearnerProfile:
        payload = profile.model_dump_json()
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO learner_profiles(student_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    str(profile.student_id),
                    payload,
                    profile.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return profile

    def get(self, student_id: UUID) -> LearnerProfile | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM learner_profiles WHERE student_id = ?",
                (str(student_id),),
            ).fetchone()

        if row is None:
            return None
        return LearnerProfile.model_validate_json(row[0])

    def list_ids(self) -> list[str]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT student_id FROM learner_profiles ORDER BY updated_at DESC"
            ).fetchall()

        return [row[0] for row in rows]
