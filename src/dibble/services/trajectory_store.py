from __future__ import annotations

import sqlite3
from uuid import UUID

from dibble.models.planning import TrajectoryPlan


class SQLiteTrajectoryStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, trajectory: TrajectoryPlan) -> TrajectoryPlan:
        self._conn.execute(
            """
            INSERT INTO learner_trajectories(trajectory_id, goal_id, student_id, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trajectory_id) DO UPDATE SET
                goal_id = excluded.goal_id,
                student_id = excluded.student_id,
                status = excluded.status,
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                trajectory.trajectory_id,
                trajectory.goal_id,
                str(trajectory.student_id),
                trajectory.status,
                trajectory.model_dump_json(),
                trajectory.created_at.isoformat(),
                trajectory.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return trajectory

    def get(self, trajectory_id: str) -> TrajectoryPlan | None:
        row = self._conn.execute(
            "SELECT payload FROM learner_trajectories WHERE trajectory_id = ?",
            (trajectory_id,),
        ).fetchone()
        if row is None:
            return None
        return TrajectoryPlan.model_validate_json(row[0])

    def list_for_goal(self, *, goal_id: str) -> list[TrajectoryPlan]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM learner_trajectories
            WHERE goal_id = ?
            ORDER BY updated_at DESC, trajectory_id DESC
            """,
            (goal_id,),
        ).fetchall()
        return [TrajectoryPlan.model_validate_json(row[0]) for row in rows]

    def get_active_for_student(self, *, student_id: UUID) -> TrajectoryPlan | None:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM learner_trajectories
            WHERE student_id = ?
            ORDER BY updated_at DESC, trajectory_id DESC
            """,
            (str(student_id),),
        ).fetchall()
        for row in rows:
            trajectory = TrajectoryPlan.model_validate_json(row[0])
            if trajectory.status == "active":
                return trajectory
        return None
