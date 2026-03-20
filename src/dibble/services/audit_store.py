from __future__ import annotations

import json
import sqlite3
from uuid import uuid4

from dibble.models.telemetry import AuditEvent


class SQLiteAuditStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def append(
        self,
        *,
        event_type: str,
        status: str,
        payload: dict[str, object],
        student_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            status=status,
            student_id=student_id,
            payload=payload,
        )
        self._conn.execute(
            """
            INSERT INTO audit_events(event_id, event_type, status, student_id, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.status,
                str(event.student_id) if event.student_id is not None else None,
                json.dumps(event.payload),
                event.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return event

    def list(self, *, limit: int = 50) -> list[AuditEvent]:
        rows = self._conn.execute(
            """
            SELECT event_id, event_type, status, student_id, payload, created_at
            FROM audit_events
            ORDER BY created_at DESC, event_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        events: list[AuditEvent] = []
        for event_id, event_type, status, student_id, payload_json, created_at in rows:
            payload = json.loads(payload_json)
            events.append(
                AuditEvent(
                    event_id=event_id,
                    event_type=event_type,
                    status=status,
                    student_id=student_id,
                    payload=payload,
                    created_at=created_at,
                )
            )
        return events
