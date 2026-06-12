"""Data-rights tooling: full learner export and hard delete.

Makes the pilot consent document honest — a guardian can receive everything
the system holds about a learner (profile, generated-content history,
sessions, observations, audit trail), and withdrawal can be honored with a
hard delete that removes the learner across every table. (POC roadmap 3.2)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearnerDataExport(BaseModel):
    student_id: str
    exported_at: datetime = Field(default_factory=utc_now)
    profile: dict | None = None
    mastery_snapshots: list[dict] = Field(default_factory=list)
    observations: list[dict] = Field(default_factory=list)
    generated_content: list[dict] = Field(default_factory=list)
    socratic_sessions: list[dict] = Field(default_factory=list)
    remediation_sessions: list[dict] = Field(default_factory=list)
    placement_sessions: list[dict] = Field(default_factory=list)
    audit_events: list[dict] = Field(default_factory=list)


class LearnerDeletionReport(BaseModel):
    student_id: str
    deleted_at: datetime = Field(default_factory=utc_now)
    deleted_rows_by_table: dict[str, int] = Field(default_factory=dict)
    deleted_user_ids: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class LearnerDataRightsService:
    connection: sqlite3.Connection

    def export(self, *, student_id: UUID) -> LearnerDataExport:
        import json

        sid = str(student_id)
        export = LearnerDataExport(student_id=sid)

        def payloads(table: str, column: str = "student_id") -> list[dict]:
            try:
                rows = self.connection.execute(
                    f"SELECT payload FROM {table} WHERE {column} = ?", (sid,)
                ).fetchall()
            except sqlite3.OperationalError:
                return []
            results: list[dict] = []
            for row in rows:
                try:
                    results.append(json.loads(row[0]))
                except (TypeError, ValueError):
                    continue
            return results

        profile_rows = payloads("learner_profiles")
        export.profile = profile_rows[0] if profile_rows else None
        export.mastery_snapshots = payloads("mastery_snapshots")
        export.observations = payloads("learner_observations")
        export.generated_content = payloads("generated_content")
        export.socratic_sessions = payloads("socratic_assessment_sessions")
        export.remediation_sessions = payloads("remediation_workflow_sessions")
        export.placement_sessions = payloads("placement_sessions")
        export.audit_events = [
            {
                "event_id": row[0],
                "event_type": row[1],
                "status": row[2],
                "payload": self._safe_json(row[3]),
                "created_at": row[4],
            }
            for row in self.connection.execute(
                """
                SELECT event_id, event_type, status, payload, created_at
                FROM audit_events WHERE student_id = ?
                ORDER BY created_at
                """,
                (sid,),
            ).fetchall()
        ]
        return export

    def hard_delete(self, *, student_id: UUID) -> LearnerDeletionReport:
        sid = str(student_id)
        report = LearnerDeletionReport(student_id=sid)

        # Every table that carries a student_id column, discovered by
        # introspection so new stores are covered automatically.
        for table in self._tables_with_column("student_id"):
            cursor = self.connection.execute(
                f"DELETE FROM {table} WHERE student_id = ?", (sid,)
            )
            if cursor.rowcount:
                report.deleted_rows_by_table[table] = cursor.rowcount

        # Learner login accounts and their section memberships.
        user_rows = self.connection.execute(
            "SELECT user_id FROM users WHERE learner_id = ?", (sid,)
        ).fetchall()
        report.deleted_user_ids = [row[0] for row in user_rows]
        for user_id in report.deleted_user_ids:
            for table, column in (
                ("classroom_memberships", "user_id"),
                ("users", "user_id"),
            ):
                try:
                    cursor = self.connection.execute(
                        f"DELETE FROM {table} WHERE {column} = ?", (user_id,)
                    )
                    if cursor.rowcount:
                        report.deleted_rows_by_table[table] = (
                            report.deleted_rows_by_table.get(table, 0) + cursor.rowcount
                        )
                except sqlite3.OperationalError:
                    continue

        self.connection.commit()
        return report

    def _tables_with_column(self, column: str) -> list[str]:
        tables = [
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        matching: list[str] = []
        for table in tables:
            columns = {
                row[1]
                for row in self.connection.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }
            if column in columns:
                matching.append(table)
        return matching

    @staticmethod
    def _safe_json(value: object) -> object:
        import json

        try:
            return json.loads(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return value
