from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import CurriculumMigrationPlan


class SQLiteCurriculumMigrationPlanStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, plan: CurriculumMigrationPlan) -> CurriculumMigrationPlan:
        self._conn.execute(
            """
            INSERT INTO curriculum_migration_plans(
                plan_id,
                diff_id,
                status,
                payload,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                diff_id = excluded.diff_id,
                status = excluded.status,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                plan.plan_id,
                plan.diff_id,
                plan.status.value,
                plan.model_dump_json(),
                plan.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return plan

    def get(self, plan_id: str) -> CurriculumMigrationPlan | None:
        row = self._conn.execute(
            "SELECT payload FROM curriculum_migration_plans WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        if row is None:
            return None
        return CurriculumMigrationPlan.model_validate_json(row[0])

    def list(self) -> list[CurriculumMigrationPlan]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM curriculum_migration_plans
            ORDER BY updated_at DESC, plan_id ASC
            """
        ).fetchall()
        return [CurriculumMigrationPlan.model_validate_json(row[0]) for row in rows]

    def get_for_diff(self, diff_id: str) -> CurriculumMigrationPlan | None:
        row = self._conn.execute(
            """
            SELECT payload
            FROM curriculum_migration_plans
            WHERE diff_id = ?
            LIMIT 1
            """,
            (diff_id,),
        ).fetchone()
        if row is None:
            return None
        return CurriculumMigrationPlan.model_validate_json(row[0])
