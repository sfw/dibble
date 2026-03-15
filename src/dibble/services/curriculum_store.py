from __future__ import annotations

import sqlite3

from dibble.models.curriculum import CurriculumResource, CurriculumResourceUpsert


class SQLiteCurriculumStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, resource: CurriculumResourceUpsert) -> CurriculumResource:
        persisted = CurriculumResource(**resource.model_dump())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO curriculum_resources(resource_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(resource_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    persisted.resource_id,
                    persisted.model_dump_json(),
                    persisted.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return persisted

    def list(self) -> list[CurriculumResource]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM curriculum_resources ORDER BY updated_at DESC, resource_id ASC"
            ).fetchall()

        return [CurriculumResource.model_validate_json(row[0]) for row in rows]
