from __future__ import annotations

import sqlite3
from uuid import UUID

from dibble.models.planning import LearnerGoal


class SQLiteLearnerGoalStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, goal: LearnerGoal) -> LearnerGoal:
        self._conn.execute(
            """
            INSERT INTO learner_goals(goal_id, student_id, status, active_trajectory_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(goal_id) DO UPDATE SET
                student_id = excluded.student_id,
                status = excluded.status,
                active_trajectory_id = excluded.active_trajectory_id,
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                goal.goal_id,
                str(goal.student_id),
                goal.status,
                goal.active_trajectory_id,
                goal.model_dump_json(),
                goal.created_at.isoformat(),
                goal.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return goal

    def get(self, goal_id: str) -> LearnerGoal | None:
        row = self._conn.execute(
            "SELECT payload FROM learner_goals WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()
        if row is None:
            return None
        return LearnerGoal.model_validate_json(row[0])

    def list_for_student(self, *, student_id: UUID) -> list[LearnerGoal]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM learner_goals
            WHERE student_id = ?
            ORDER BY updated_at DESC, goal_id DESC
            """,
            (str(student_id),),
        ).fetchall()
        return [LearnerGoal.model_validate_json(row[0]) for row in rows]

    def get_active_for_student(self, *, student_id: UUID) -> LearnerGoal | None:
        for goal in self.list_for_student(student_id=student_id):
            if goal.status == "active":
                return goal
        return None
