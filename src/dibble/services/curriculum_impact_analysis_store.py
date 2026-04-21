from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import CurriculumImpactAnalysis


class SQLiteCurriculumImpactAnalysisStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, analysis: CurriculumImpactAnalysis) -> CurriculumImpactAnalysis:
        self._conn.execute(
            """
            INSERT INTO curriculum_impact_analyses(
                analysis_id,
                diff_id,
                payload,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(analysis_id) DO UPDATE SET
                diff_id = excluded.diff_id,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                analysis.analysis_id,
                analysis.diff_id,
                analysis.model_dump_json(),
                analysis.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return analysis

    def get(self, analysis_id: str) -> CurriculumImpactAnalysis | None:
        row = self._conn.execute(
            "SELECT payload FROM curriculum_impact_analyses WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()
        if row is None:
            return None
        return CurriculumImpactAnalysis.model_validate_json(row[0])

    def list(self) -> list[CurriculumImpactAnalysis]:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM curriculum_impact_analyses
            ORDER BY updated_at DESC, analysis_id ASC
            """
        ).fetchall()
        return [CurriculumImpactAnalysis.model_validate_json(row[0]) for row in rows]

    def get_for_diff(self, diff_id: str) -> CurriculumImpactAnalysis | None:
        row = self._conn.execute(
            """
            SELECT payload
            FROM curriculum_impact_analyses
            WHERE diff_id = ?
            LIMIT 1
            """,
            (diff_id,),
        ).fetchone()
        if row is None:
            return None
        return CurriculumImpactAnalysis.model_validate_json(row[0])
