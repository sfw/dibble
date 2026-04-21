from __future__ import annotations

import json
import sqlite3
from uuid import uuid4

from dibble.models.observability import (
    HarnessBoundary,
    OperationalTrace,
    OperationalTraceStatus,
)


class SQLiteOperationalTraceStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def append(
        self,
        *,
        harness: HarnessBoundary,
        operation: str,
        status: OperationalTraceStatus,
        summary: str,
        request_id: str | None = None,
        session_id: str | None = None,
        student_id: str | None = None,
        household_id: str | None = None,
        entity_kind: str | None = None,
        entity_id: str | None = None,
        degraded_mode: bool = False,
        degraded_reason: str | None = None,
        fallback_kind: str | None = None,
        fallback_provenance: str | None = None,
        reason_code: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> OperationalTrace:
        trace = OperationalTrace(
            trace_id=str(uuid4()),
            harness=harness,
            operation=operation,
            status=status,
            summary=summary,
            request_id=request_id,
            session_id=session_id,
            student_id=student_id,
            household_id=household_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            degraded_mode=degraded_mode,
            degraded_reason=degraded_reason,
            fallback_kind=fallback_kind,
            fallback_provenance=fallback_provenance,
            reason_code=reason_code,
            payload=payload or {},
        )
        self._conn.execute(
            """
            INSERT INTO operational_traces(
                trace_id,
                harness,
                operation,
                status,
                request_id,
                session_id,
                student_id,
                household_id,
                entity_kind,
                entity_id,
                degraded_mode,
                degraded_reason,
                fallback_kind,
                fallback_provenance,
                reason_code,
                summary,
                payload,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace.trace_id,
                trace.harness.value,
                trace.operation,
                trace.status.value,
                trace.request_id,
                trace.session_id,
                trace.student_id,
                trace.household_id,
                trace.entity_kind,
                trace.entity_id,
                1 if trace.degraded_mode else 0,
                trace.degraded_reason,
                trace.fallback_kind,
                trace.fallback_provenance,
                trace.reason_code,
                trace.summary,
                json.dumps(trace.payload),
                trace.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return trace

    def list(
        self,
        *,
        limit: int = 100,
        harness: HarnessBoundary | None = None,
        degraded_only: bool = False,
        request_id: str | None = None,
        session_id: str | None = None,
    ) -> list[OperationalTrace]:
        clauses: list[str] = []
        params: list[object] = []
        if harness is not None:
            clauses.append("harness = ?")
            params.append(harness.value)
        if degraded_only:
            clauses.append("degraded_mode = 1")
        if request_id is not None:
            clauses.append("request_id = ?")
            params.append(request_id)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"""
            SELECT
                trace_id,
                harness,
                operation,
                status,
                request_id,
                session_id,
                student_id,
                household_id,
                entity_kind,
                entity_id,
                degraded_mode,
                degraded_reason,
                fallback_kind,
                fallback_provenance,
                reason_code,
                summary,
                payload,
                created_at
            FROM operational_traces
            {where_clause}
            ORDER BY created_at DESC, trace_id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        traces: list[OperationalTrace] = []
        for row in rows:
            traces.append(
                OperationalTrace(
                    trace_id=row[0],
                    harness=row[1],
                    operation=row[2],
                    status=row[3],
                    request_id=row[4],
                    session_id=row[5],
                    student_id=row[6],
                    household_id=row[7],
                    entity_kind=row[8],
                    entity_id=row[9],
                    degraded_mode=bool(row[10]),
                    degraded_reason=row[11],
                    fallback_kind=row[12],
                    fallback_provenance=row[13],
                    reason_code=row[14],
                    summary=row[15],
                    payload=json.loads(row[16]),
                    created_at=row[17],
                )
            )
        return traces
