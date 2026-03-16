from __future__ import annotations

import sqlite3

from dibble.models.curriculum import KnowledgeComponent, KnowledgeComponentUpsert
from dibble.services.knowledge_component_graph import KnowledgeComponentGraph


class SQLiteKnowledgeComponentStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, component: KnowledgeComponentUpsert) -> KnowledgeComponent:
        persisted = KnowledgeComponent(**component.model_dump())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_components(kc_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(kc_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    persisted.kc_id,
                    persisted.model_dump_json(),
                    persisted.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return persisted

    def get(self, kc_id: str) -> KnowledgeComponent | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT payload FROM knowledge_components WHERE kc_id = ?",
                (kc_id,),
            ).fetchone()

        if row is None:
            return None
        return KnowledgeComponent.model_validate_json(row[0])

    def list(self) -> list[KnowledgeComponent]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM knowledge_components ORDER BY updated_at DESC, kc_id ASC"
            ).fetchall()

        return [KnowledgeComponent.model_validate_json(row[0]) for row in rows]

    def list_prerequisites(self, kc_id: str) -> list[KnowledgeComponent]:
        graph = KnowledgeComponentGraph(self.list())
        return [relation.component for relation in graph.prerequisites_for(kc_id)]
