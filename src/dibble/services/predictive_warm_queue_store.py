from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from dibble.models.generation import (
    GenerationRequest,
    PredictiveWarmSweepResult,
    PredictiveWarmTask,
    RequestedContentType,
)


class SQLitePredictiveWarmQueueStore:
    def __init__(
        self,
        database_path: str,
        *,
        stale_after_minutes: int = 30,
        claim_scan_limit: int = 100,
        max_retry_attempts: int = 3,
        retry_backoff_seconds: int = 30,
        processing_timeout_seconds: int = 120,
        routine_starvation_minutes: int = 5,
    ) -> None:
        self.database_path = database_path
        self.stale_after_minutes = stale_after_minutes
        self.claim_scan_limit = claim_scan_limit
        self.max_retry_attempts = max(1, max_retry_attempts)
        self.retry_backoff_seconds = max(5, retry_backoff_seconds)
        self.processing_timeout_seconds = max(30, processing_timeout_seconds)
        self.routine_starvation_minutes = max(1, routine_starvation_minutes)

    def enqueue(self, *, request: GenerationRequest) -> PredictiveWarmTask | None:
        fingerprint = _request_fingerprint(request)
        now = datetime.now(timezone.utc)
        priority_score = _priority_for_request(request)
        priority_class = _priority_class_for_request(request, priority_score=priority_score)
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
                priority_class=priority_class,
                attempt_count=0,
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
                next_attempt_at=None,
            )
            connection.execute(
                """
                INSERT INTO predictive_warm_queue(
                    task_id,
                    student_id,
                    request_payload,
                    request_fingerprint,
                    status,
                    priority_class,
                    attempt_count,
                    created_at,
                    updated_at,
                    next_attempt_at,
                    last_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    str(task.student_id),
                    task.request.model_dump_json(),
                    task.request_fingerprint,
                    task.status,
                    task.priority_class,
                    task.attempt_count,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    None,
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
                SELECT task_id, student_id, request_payload, request_fingerprint, status, priority_class, attempt_count,
                       created_at, updated_at, next_attempt_at, last_error
                FROM predictive_warm_queue
                WHERE status IN ('pending', 'deferred')
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
            candidates = [
                task
                for task in tasks
                if task.task_id not in stale_ids and (task.next_attempt_at is None or task.next_attempt_at <= now)
            ]
            task_ids = [task.task_id for task in _select_task_batch(candidates, limit=limit)]
            if not task_ids:
                connection.commit()
                return []
            _mark_processing(connection, task_ids=task_ids)
            connection.commit()
        task_by_id = {task.task_id: task for task in candidates}
        return [
            task_by_id[task_id].model_copy(
                update={
                    "status": "processing",
                    "updated_at": now,
                    "attempt_count": task_by_id[task_id].attempt_count + 1,
                    "next_attempt_at": None,
                }
            )
            for task_id in task_ids
        ]

    def sweep(self, *, limit: int = 200) -> PredictiveWarmSweepResult:
        now = datetime.now(timezone.utc)
        processing_cutoff = now - timedelta(seconds=self.processing_timeout_seconds)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT task_id, student_id, request_payload, request_fingerprint, status, priority_class, attempt_count,
                       created_at, updated_at, next_attempt_at, last_error
                FROM predictive_warm_queue
                WHERE status IN ('pending', 'deferred', 'processing')
                ORDER BY updated_at ASC, task_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            if not rows:
                return PredictiveWarmSweepResult()
            tasks = [_task_from_row(row, stale_after_minutes=self.stale_after_minutes) for row in rows]
            expired_ids = [task.task_id for task in tasks if task.expires_at is not None and task.expires_at <= now]
            if expired_ids:
                _mark_canceled(connection, task_ids=expired_ids, last_error="Predictive warm task expired before processing.")

            requeued = 0
            for task in tasks:
                if task.task_id in expired_ids:
                    continue
                if task.status != "processing" or task.updated_at > processing_cutoff:
                    continue
                if task.attempt_count >= self._max_retry_attempts_for(task.priority_class):
                    connection.execute(
                        """
                        UPDATE predictive_warm_queue
                        SET status = 'failed', updated_at = ?, next_attempt_at = NULL, last_error = ?
                        WHERE task_id = ?
                        """,
                        (
                            now.isoformat(),
                            "Predictive warm task exceeded retry budget after a stale processing recovery.",
                            task.task_id,
                        ),
                    )
                    continue
                next_attempt_at = now + timedelta(
                    seconds=self.retry_backoff_seconds * (2 ** max(0, task.attempt_count - 1))
                )
                connection.execute(
                    """
                    UPDATE predictive_warm_queue
                    SET status = 'deferred', updated_at = ?, next_attempt_at = ?, last_error = ?
                    WHERE task_id = ?
                    """,
                    (
                        now.isoformat(),
                        next_attempt_at.isoformat(),
                        "Recovered stale processing task after processing timeout.",
                        task.task_id,
                    ),
                )
                requeued += 1
            connection.commit()
        return PredictiveWarmSweepResult(requeued_tasks=requeued, expired_tasks=len(expired_ids))

    def claim_tasks(self, *, task_ids: list[str]) -> list[PredictiveWarmTask]:
        if not task_ids:
            return []
        placeholders = ", ".join("?" for _ in task_ids)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT task_id, student_id, request_payload, request_fingerprint, status, priority_class, attempt_count,
                       created_at, updated_at, next_attempt_at, last_error
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
            _task_from_row(
                (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    "processing",
                    row[5],
                    int(row[6]) + 1,
                    row[7],
                    datetime.now(timezone.utc).isoformat(),
                    None,
                    row[10],
                ),
                stale_after_minutes=self.stale_after_minutes,
            )
            for row in rows
        ]

    def mark_completed(self, *, task_id: str) -> None:
        self._update_status(task_id=task_id, status="completed", last_error=None, next_attempt_at=None)

    def mark_failed(self, *, task_id: str, error: str) -> None:
        self._update_status(task_id=task_id, status="failed", last_error=error, next_attempt_at=None)

    def defer_retry(self, *, task_id: str, error: str) -> PredictiveWarmTask | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT task_id, student_id, request_payload, request_fingerprint, status, priority_class, attempt_count,
                       created_at, updated_at, next_attempt_at, last_error
                FROM predictive_warm_queue
                WHERE task_id = ?
                LIMIT 1
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            task = _task_from_row(row, stale_after_minutes=self.stale_after_minutes)
            if task.attempt_count >= self._max_retry_attempts_for(task.priority_class):
                self._update_status(task_id=task_id, status="failed", last_error=error, next_attempt_at=None)
                return None
            delay_seconds = self.retry_backoff_seconds * (2 ** max(0, task.attempt_count - 1))
            next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            connection.execute(
                """
                UPDATE predictive_warm_queue
                SET status = 'deferred', updated_at = ?, next_attempt_at = ?, last_error = ?
                WHERE task_id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    next_attempt_at.isoformat(),
                    error,
                    task_id,
                ),
            )
            connection.commit()
        return task.model_copy(
            update={
                "status": "deferred",
                "updated_at": datetime.now(timezone.utc),
                "next_attempt_at": next_attempt_at,
                "last_error": error,
            }
        )

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
                SET status = 'canceled', updated_at = ?, next_attempt_at = NULL, last_error = NULL
                WHERE task_id IN ({placeholders})
                """,
                (datetime.now(timezone.utc).isoformat(), *canceled_ids),
            )
            connection.commit()
        return len(canceled_ids)

    def stats(self) -> dict[str, int]:
        counts = {
            "pending": 0,
            "processing": 0,
            "deferred": 0,
            "completed": 0,
            "failed": 0,
            "canceled": 0,
            "aged_routine": 0,
        }
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT status, count(*)
                FROM predictive_warm_queue
                GROUP BY status
                """
            ).fetchall()
            aged_routine_row = connection.execute(
                """
                SELECT count(*)
                FROM predictive_warm_queue
                WHERE priority_class = 'routine'
                  AND status IN ('pending', 'deferred')
                  AND created_at <= ?
                """,
                (
                    (datetime.now(timezone.utc) - timedelta(minutes=self.routine_starvation_minutes)).isoformat(),
                ),
            ).fetchone()
        for status, count in rows:
            counts[str(status)] = int(count)
        counts["aged_routine"] = int(aged_routine_row[0]) if aged_routine_row is not None else 0
        return counts

    def _update_status(
        self,
        *,
        task_id: str,
        status: str,
        last_error: str | None,
        next_attempt_at: str | None,
    ) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE predictive_warm_queue
                SET status = ?, updated_at = ?, next_attempt_at = ?, last_error = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    datetime.now(timezone.utc).isoformat(),
                    next_attempt_at,
                    last_error,
                    task_id,
                ),
            )
            connection.commit()

    def _max_retry_attempts_for(self, priority_class: str) -> int:
        class_caps = {
            "urgent": self.max_retry_attempts + 1,
            "high": self.max_retry_attempts,
            "routine": max(1, self.max_retry_attempts - 1),
        }
        return class_caps.get(priority_class, self.max_retry_attempts)


def _mark_processing(connection: sqlite3.Connection, *, task_ids: list[str]) -> None:
    placeholders = ", ".join("?" for _ in task_ids)
    connection.execute(
        f"""
        UPDATE predictive_warm_queue
        SET status = 'processing', updated_at = ?, next_attempt_at = NULL, last_error = NULL, attempt_count = attempt_count + 1
        WHERE task_id IN ({placeholders})
        """,
        (datetime.now(timezone.utc).isoformat(), *task_ids),
    )


def _mark_canceled(connection: sqlite3.Connection, *, task_ids: list[str], last_error: str | None) -> None:
    placeholders = ", ".join("?" for _ in task_ids)
    connection.execute(
        f"""
        UPDATE predictive_warm_queue
        SET status = 'canceled', updated_at = ?, next_attempt_at = NULL, last_error = ?
        WHERE task_id IN ({placeholders})
        """,
        (datetime.now(timezone.utc).isoformat(), last_error, *task_ids),
    )


def _task_from_row(row, *, stale_after_minutes: int) -> PredictiveWarmTask:
    (
        task_id,
        student_id,
        request_payload,
        request_fingerprint,
        status,
        priority_class,
        attempt_count,
        created_at,
        updated_at,
        next_attempt_at,
        last_error,
    ) = row
    request = GenerationRequest.model_validate(json.loads(request_payload))
    created = datetime.fromisoformat(created_at)
    priority_score = _priority_for_request(request)
    return PredictiveWarmTask(
        task_id=str(task_id),
        student_id=student_id,
        request=request,
        request_fingerprint=str(request_fingerprint),
        status=str(status),
        priority_score=priority_score,
        priority_class=str(priority_class) if priority_class is not None else _priority_class_for_request(request, priority_score=priority_score),
        attempt_count=int(attempt_count or 0),
        created_at=created,
        updated_at=datetime.fromisoformat(updated_at),
        expires_at=created + timedelta(minutes=max(1, stale_after_minutes)),
        next_attempt_at=datetime.fromisoformat(next_attempt_at) if next_attempt_at is not None else None,
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


def _priority_class_for_request(request: GenerationRequest, *, priority_score: float) -> str:
    if priority_score >= 0.84 or request.requested_content_type in {
        RequestedContentType.remedial_micro_module,
        RequestedContentType.assessment_probe,
    }:
        return "urgent"
    if priority_score >= 0.68:
        return "high"
    return "routine"


def _select_task_batch(tasks: list[PredictiveWarmTask], *, limit: int) -> list[PredictiveWarmTask]:
    if limit <= 0 or not tasks:
        return []
    ordered = sorted(tasks, key=lambda task: (-task.priority_score, task.created_at, task.task_id))
    groups = {
        "urgent": [task for task in ordered if task.priority_class == "urgent"],
        "high": [task for task in ordered if task.priority_class == "high"],
        "routine": [task for task in ordered if task.priority_class == "routine"],
    }
    selected: list[PredictiveWarmTask] = []
    if limit >= 3:
        for priority_class in ("urgent", "high", "routine"):
            if groups[priority_class]:
                selected.append(groups[priority_class].pop(0))
                if len(selected) >= limit:
                    return selected
    remaining_ids = {task.task_id for task in selected}
    for task in ordered:
        if task.task_id in remaining_ids:
            continue
        selected.append(task)
        if len(selected) >= limit:
            break
    return selected[:limit]
