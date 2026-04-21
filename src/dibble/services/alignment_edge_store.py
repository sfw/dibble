from __future__ import annotations

import sqlite3

from dibble.models.curriculum_intake import AlignmentEdge, AlignmentReviewDecision


class SQLiteAlignmentEdgeStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, edge: AlignmentEdge) -> AlignmentEdge:
        self._conn.execute(
            """
            INSERT INTO alignment_edges(edge_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(edge_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                edge.edge_id,
                edge.model_dump_json(),
                edge.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return edge

    def get(self, edge_id: str) -> AlignmentEdge | None:
        row = self._conn.execute(
            "SELECT payload FROM alignment_edges WHERE edge_id = ?",
            (edge_id,),
        ).fetchone()
        if row is None:
            return None
        return AlignmentEdge.model_validate_json(row[0])

    def list(self) -> list[AlignmentEdge]:
        rows = self._conn.execute(
            "SELECT payload FROM alignment_edges ORDER BY updated_at DESC, edge_id ASC"
        ).fetchall()
        return [AlignmentEdge.model_validate_json(row[0]) for row in rows]


class SQLiteAlignmentReviewDecisionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def append(self, decision: AlignmentReviewDecision) -> AlignmentReviewDecision:
        self._conn.execute(
            """
            INSERT INTO alignment_review_decisions(
                decision_id,
                edge_id,
                payload,
                decided_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                decision.decision_id,
                decision.edge_id,
                decision.model_dump_json(),
                decision.decided_at.isoformat(),
            ),
        )
        self._conn.commit()
        return decision

    def list_for_edge(self, edge_id: str) -> list[AlignmentReviewDecision]:
        rows = self._conn.execute(
            """
            SELECT payload FROM alignment_review_decisions
            WHERE edge_id = ?
            ORDER BY decided_at DESC, decision_id ASC
            """,
            (edge_id,),
        ).fetchall()
        return [AlignmentReviewDecision.model_validate_json(row[0]) for row in rows]
