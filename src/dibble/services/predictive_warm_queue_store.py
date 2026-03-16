from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from dibble.models.generation import GenerationRequest, PredictiveWarmTask


class SQLitePredictiveWarmQueueStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def enqueue(self, *, request: GenerationRequest) -> PredictiveWarmTask | None:
        fingerprint = _request_fingerprint(request)
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT task_id
                FROM predictive_warm_queue
                WHERE student_id = ? AND request_fingerprint = ? AND status IN ('pending', 'processing')
                LIMIT 1
                """,
                (str(request.student_id), fingerprint),
            ).fetchone()
            if row is not None:
                return None
            task = PredictiveWarmTask(
                task_id=str(uuid4()),
                student_id=request.student_id,
                request=request,
                request_fingerprint=fingerprint,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            connection.execute(
                """
                INSERT INTO predictive_warm_queue(
                    task_id,
                    student_id,
                    request_payload,
                    request_fingerprint,
                    status,
                    created_at,
                    updated_at,
                    last_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    str(task.student_id),
                    task.request.model_dump_json(),
                    task.request_fingerprint,
                    task.status,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.last_error,
                ),
            )
            connection.commit()
        return task

    def claim_pending(self, *, limit: int = 10) -> list[PredictiveWarmTask]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT task_id, student_id, request_payload, request_fingerprint, status, created_at, updated_at, last_error
                FROM predictive_warm_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC, task_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            if not rows:
                return []
            task_ids = [str(row[0]) for row in rows]
            _mark_processing(connection, task_ids=task_ids)
            connection.commit()
        return [_task_from_row((*row[:4], "processing", *row[5:])) for row in rows]

    def claim_tasks(self, *, task_ids: list[str]) -> list[PredictiveWarmTask]:
        if not task_ids:
            return []
        placeholders = ", ".join("?" for _ in task_ids)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT task_id, student_id, request_payload, request_fingerprint, status, created_at, updated_at, last_error
                FROM predictive_warm_queue
                WHERE task_id IN ({placeholders}) AND status = 'pending'
                ORDER BY created_at ASC, task_id ASC
                """,
                tuple(task_ids),
            ).fetchall()
            if not rows:
                return []
            claimed_ids = [str(row[0]) for row in rows]
            _mark_processing(connection, task_ids=claimed_ids)
            connection.commit()
        return [_task_from_row((*row[:4], "processing", *row[5:])) for row in rows]

    def mark_completed(self, *, task_id: str) -> None:
        self._update_status(task_id=task_id, status="completed", last_error=None)

    def mark_failed(self, *, task_id: str, error: str) -> None:
        self._update_status(task_id=task_id, status="failed", last_error=error)

    def cancel_pending(
        self,
        *,
        student_id: str | None,
        target_kc_ids: list[str],
        target_lo_ids: list[str],
        learning_session_id: str | None = None,
        limit: int = 200,
    ) -> int:
        if student_id is None:
            return 0
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT task_id, request_payload
                FROM predictive_warm_queue
                WHERE student_id = ? AND status = 'pending'
                ORDER BY created_at DESC, task_id DESC
                LIMIT ?
                """,
                (student_id, limit),
            ).fetchall()
            canceled_ids = [
                str(task_id)
                for task_id, request_payload in rows
                if _matches_invalidation(
                    request_payload=request_payload,
                    target_kc_ids=target_kc_ids,
                    target_lo_ids=target_lo_ids,
                    learning_session_id=learning_session_id,
                )
            ]
            if not canceled_ids:
                return 0
            placeholders = ", ".join("?" for _ in canceled_ids)
            connection.execute(
                f"""
                UPDATE predictive_warm_queue
                SET status = 'canceled', updated_at = ?, last_error = NULL
                WHERE task_id IN ({placeholders})
                """,
                (datetime.now(timezone.utc).isoformat(), *canceled_ids),
            )
            connection.commit()
        return len(canceled_ids)

    def stats(self) -> dict[str, int]:
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "canceled": 0}
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT status, count(*)
                FROM predictive_warm_queue
                GROUP BY status
                """
            ).fetchall()
        for status, count in rows:
            counts[str(status)] = int(count)
        return counts

    def _update_status(self, *, task_id: str, status: str, last_error: str | None) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE predictive_warm_queue
                SET status = ?, updated_at = ?, last_error = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    datetime.now(timezone.utc).isoformat(),
                    last_error,
                    task_id,
                ),
            )
            connection.commit()


def _mark_processing(connection: sqlite3.Connection, *, task_ids: list[str]) -> None:
    placeholders = ", ".join("?" for _ in task_ids)
    connection.execute(
        f"""
        UPDATE predictive_warm_queue
        SET status = 'processing', updated_at = ?, last_error = NULL
        WHERE task_id IN ({placeholders})
        """,
        (datetime.now(timezone.utc).isoformat(), *task_ids),
    )


def _task_from_row(row) -> PredictiveWarmTask:
    task_id, student_id, request_payload, request_fingerprint, status, created_at, updated_at, last_error = row
    return PredictiveWarmTask(
        task_id=str(task_id),
        student_id=student_id,
        request=GenerationRequest.model_validate(json.loads(request_payload)),
        request_fingerprint=str(request_fingerprint),
        status=str(status),
        created_at=created_at,
        updated_at=updated_at,
        last_error=str(last_error) if last_error is not None else None,
    )


def _request_fingerprint(request: GenerationRequest) -> str:
    payload = request.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _matches_invalidation(
    *,
    request_payload: str,
    target_kc_ids: list[str],
    target_lo_ids: list[str],
    learning_session_id: str | None,
) -> bool:
    request = GenerationRequest.model_validate(json.loads(request_payload))
    if learning_session_id is not None and request.learning_session_id != learning_session_id:
        return False
    if not target_kc_ids and not target_lo_ids:
        return True
    if set(request.target_kc_ids).intersection(target_kc_ids):
        return True
    if set(request.target_lo_ids).intersection(target_lo_ids):
        return True
    return False
