from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from dibble.models.retention import (
    RetentionReviewCandidate,
    RetentionReviewStatus,
)


ACTIVE_STATUSES = {
    RetentionReviewStatus.scheduled,
    RetentionReviewStatus.due,
}


class SQLiteRetentionReviewCandidateStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(
        self, candidate: RetentionReviewCandidate
    ) -> RetentionReviewCandidate:
        self._conn.execute(
            """
            INSERT INTO retention_review_candidates(
                candidate_id,
                learner_id,
                cluster_key,
                outcome_id,
                status,
                due_at,
                updated_at,
                payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                learner_id = excluded.learner_id,
                cluster_key = excluded.cluster_key,
                outcome_id = excluded.outcome_id,
                status = excluded.status,
                due_at = excluded.due_at,
                updated_at = excluded.updated_at,
                payload = excluded.payload
            """,
            (
                candidate.candidate_id,
                str(candidate.learner_id),
                candidate.cluster_key,
                candidate.outcome_id,
                candidate.status.value,
                candidate.due_at.isoformat(),
                candidate.updated_at.isoformat(),
                candidate.model_dump_json(),
            ),
        )
        self._conn.commit()
        return candidate

    def upsert_many(
        self, candidates: list[RetentionReviewCandidate]
    ) -> list[RetentionReviewCandidate]:
        for candidate in candidates:
            self.upsert(candidate)
        return candidates

    def get(self, candidate_id: str) -> RetentionReviewCandidate | None:
        row = self._conn.execute(
            """
            SELECT payload
            FROM retention_review_candidates
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return RetentionReviewCandidate.model_validate_json(row[0])

    def active_for_cluster(
        self, *, learner_id: str, cluster_key: str
    ) -> RetentionReviewCandidate | None:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM retention_review_candidates
            WHERE learner_id = ?
              AND cluster_key = ?
              AND status IN ('scheduled', 'due')
            ORDER BY due_at ASC, updated_at DESC
            LIMIT 1
            """,
            (learner_id, cluster_key),
        ).fetchall()
        if not rows:
            return None
        return RetentionReviewCandidate.model_validate_json(rows[0][0])

    def list_for_student(
        self,
        *,
        learner_id: str,
        statuses: list[RetentionReviewStatus] | None = None,
        limit: int = 50,
    ) -> list[RetentionReviewCandidate]:
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            rows = self._conn.execute(
                f"""
                SELECT payload
                FROM retention_review_candidates
                WHERE learner_id = ?
                  AND status IN ({placeholders})
                ORDER BY due_at ASC, updated_at DESC
                LIMIT ?
                """,
                (
                    learner_id,
                    *[status.value for status in statuses],
                    max(1, limit),
                ),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT payload
                FROM retention_review_candidates
                WHERE learner_id = ?
                ORDER BY due_at ASC, updated_at DESC
                LIMIT ?
                """,
                (learner_id, max(1, limit)),
            ).fetchall()
        return [RetentionReviewCandidate.model_validate_json(row[0]) for row in rows]

    def due_reviews_for_student(
        self,
        *,
        learner_id: str,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[RetentionReviewCandidate]:
        now = now or datetime.now(timezone.utc)
        self._mark_due(learner_id=learner_id, now=now)
        rows = self._conn.execute(
            """
            SELECT payload
            FROM retention_review_candidates
            WHERE learner_id = ?
              AND status = 'due'
              AND due_at <= ?
            ORDER BY due_at ASC, updated_at DESC
            LIMIT ?
            """,
            (learner_id, now.isoformat(), max(1, limit)),
        ).fetchall()
        return [RetentionReviewCandidate.model_validate_json(row[0]) for row in rows]

    def scheduled_reviews_for_student(
        self,
        *,
        learner_id: str,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[RetentionReviewCandidate]:
        now = now or datetime.now(timezone.utc)
        rows = self._conn.execute(
            """
            SELECT payload
            FROM retention_review_candidates
            WHERE learner_id = ?
              AND status = 'scheduled'
              AND due_at > ?
            ORDER BY due_at ASC, updated_at DESC
            LIMIT ?
            """,
            (learner_id, now.isoformat(), max(1, limit)),
        ).fetchall()
        return [RetentionReviewCandidate.model_validate_json(row[0]) for row in rows]

    def record_review(
        self,
        *,
        candidate_id: str,
        reviewed_at: datetime | None = None,
        successful: bool = False,
        outcome_score: float | None = None,
        status: RetentionReviewStatus = RetentionReviewStatus.completed,
    ) -> RetentionReviewCandidate | None:
        candidate = self.get(candidate_id)
        if candidate is None:
            return None
        reviewed_at = reviewed_at or datetime.now(timezone.utc)
        updated = candidate.model_copy(
            update={
                "last_reviewed_at": reviewed_at,
                "last_successful_review_at": (
                    reviewed_at if successful else candidate.last_successful_review_at
                ),
                "review_count": candidate.review_count + 1,
                "last_outcome_score": outcome_score,
                "status": status,
                "updated_at": reviewed_at,
            }
        )
        return self.upsert(updated)

    def _mark_due(self, *, learner_id: str, now: datetime) -> None:
        rows = self._conn.execute(
            """
            SELECT payload
            FROM retention_review_candidates
            WHERE learner_id = ?
              AND status = 'scheduled'
              AND due_at <= ?
            """,
            (learner_id, now.isoformat()),
        ).fetchall()
        if not rows:
            return
        for row in rows:
            candidate = RetentionReviewCandidate.model_validate_json(row[0])
            due_candidate = candidate.model_copy(
                update={
                    "status": RetentionReviewStatus.due,
                    "updated_at": now,
                }
            )
            self._conn.execute(
                """
                UPDATE retention_review_candidates
                SET status = ?, updated_at = ?, payload = ?
                WHERE candidate_id = ?
                """,
                (
                    RetentionReviewStatus.due.value,
                    now.isoformat(),
                    due_candidate.model_dump_json(),
                    candidate.candidate_id,
                ),
            )
        self._conn.commit()
