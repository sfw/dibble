from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from dibble.models.generation import GenerationRequest, PredictiveWarmTask, RequestedContentType


class SQLitePredictiveWarmQueueStore:
    def __init__(
        self,
        database_path: str,
        *,
        stale_after_minutes: int = 30,
        claim_scan_limit: int = 100,
    ) -> None:
        self.database_path = database_path
        self.stale_after_minutes = stale_after_minutes
        self.claim_scan_limit = claim_scan_limit

    def enqueue(self, *, request: GenerationRequest) -> PredictiveWarmTask | None:
        fingerprint = _request_fingerprint(request)
        now = datetime.now(timezone.utc)
        priority_score = _priority_for_request(request)
        expires_at = now + timedelta(minutes=max(1, self.stale_after_minutes))
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
                priority_score=priority_score,
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
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
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT task_id, student_id, request_payload, request_fingerprint, status, created_at, updated_at, last_error
                FROM predictive_warm_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC, task_id ASC
                LIMIT ?
                """,
                (max(limit, self.claim_scan_limit),),
            ).fetchall()
            if not rows:
                return []
            tasks = [_task_from_row(row, stale_after_minutes=self.stale_after_minutes) for row in rows]
            stale_ids = [task.task_id for task in tasks if task.expires_at is not None and task.expires_at <= now]
            if stale_ids:
                _mark_canceled(connection, task_ids=stale_ids, last_error="Predictive warm task expired before processing.")
            candidates = [task for task in tasks if task.task_id not in stale_ids]
            candidates.sort(key=lambda task: (-task.priority_score, task.created_at, task.task_id))
            task_ids = [task.task_id for task in candidates[:limit]]
            if not task_ids:
                connection.commit()
                return []
            _mark_processing(connection, task_ids=task_ids)
            connection.commit()
        task_by_id = {task.task_id: task for task in candidates}
        return [
            task_by_id[task_id].model_copy(update={"status": "processing", "updated_at": now})
            for task_id in task_ids
        ]

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
        return [
            _task_from_row((*row[:4], "processing", *row[5:]), stale_after_minutes=self.stale_after_minutes)
            for row in rows
        ]

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


def _mark_canceled(connection: sqlite3.Connection, *, task_ids: list[str], last_error: str | None) -> None:
    placeholders = ", ".join("?" for _ in task_ids)
    connection.execute(
        f"""
        UPDATE predictive_warm_queue
        SET status = 'canceled', updated_at = ?, last_error = ?
        WHERE task_id IN ({placeholders})
        """,
        (datetime.now(timezone.utc).isoformat(), last_error, *task_ids),
    )


def _task_from_row(row, *, stale_after_minutes: int) -> PredictiveWarmTask:
    task_id, student_id, request_payload, request_fingerprint, status, created_at, updated_at, last_error = row
    request = GenerationRequest.model_validate(json.loads(request_payload))
    created = datetime.fromisoformat(created_at)
    return PredictiveWarmTask(
        task_id=str(task_id),
        student_id=student_id,
        request=request,
        request_fingerprint=str(request_fingerprint),
        status=str(status),
        priority_score=_priority_for_request(request),
        created_at=created,
        updated_at=datetime.fromisoformat(updated_at),
        expires_at=created + timedelta(minutes=max(1, stale_after_minutes)),
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


def _priority_for_request(request: GenerationRequest) -> float:
    mode = request.mode_calibration
    session_phase = mode.session_phase if mode is not None else "monitor"
    sequence_action = mode.sequence_action if mode is not None else "monitor"
    priority = {
        RequestedContentType.remedial_micro_module: 0.9,
        RequestedContentType.assessment_probe: 0.82,
        RequestedContentType.worked_example: 0.74,
        RequestedContentType.practice_problem: 0.68,
        RequestedContentType.micro_explanation: 0.58,
    }.get(request.requested_content_type or RequestedContentType.micro_explanation, 0.5)
    if session_phase in {"transfer_check", "bridge"}:
        priority += 0.08
    elif session_phase == "consolidate":
        priority += 0.04
    if sequence_action == "attempt_transfer":
        priority += 0.06
    elif sequence_action in {"hold_target", "hold_repair_target"}:
        priority += 0.03
    if request.intent.value == "remediation":
        priority += 0.05
    if request.warm_reason is not None:
        normalized_reason = request.warm_reason.lower()
        if any(term in normalized_reason for term in {"relapse", "repair", "prerequisite"}):
            priority += 0.05
        elif "transfer" in normalized_reason:
            priority += 0.04
    return round(min(1.0, priority), 3)
