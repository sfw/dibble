from __future__ import annotations

import json
import sqlite3
from uuid import uuid4

from dibble.models.telemetry import ProviderHealthEvent, ProviderStatusSnapshot


class SQLiteProviderHealthStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def append(
        self,
        *,
        provider_name: str,
        status: str,
        detail: dict[str, object] | None = None,
    ) -> ProviderHealthEvent:
        event = ProviderHealthEvent(
            event_id=str(uuid4()),
            provider_name=provider_name,
            status=status,
            detail=detail or {},
        )
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO provider_health_events(event_id, provider_name, status, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.provider_name,
                    event.status,
                    json.dumps(event.detail),
                    event.created_at.isoformat(),
                ),
            )
            connection.commit()
        return event

    def list(self, *, limit: int = 100) -> list[ProviderHealthEvent]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT event_id, provider_name, status, detail, created_at
                FROM provider_health_events
                ORDER BY created_at DESC, event_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            ProviderHealthEvent(
                event_id=event_id,
                provider_name=provider_name,
                status=status,
                detail=json.loads(detail_json),
                created_at=created_at,
            )
            for event_id, provider_name, status, detail_json, created_at in rows
        ]

    def latest_statuses(self) -> list[ProviderStatusSnapshot]:
        events = self.list(limit=500)
        latest: dict[str, ProviderStatusSnapshot] = {}
        for event in events:
            if event.provider_name in latest:
                continue
            latest[event.provider_name] = ProviderStatusSnapshot(
                provider_name=event.provider_name,
                status=event.status,
                detail=event.detail,
                updated_at=event.created_at,
            )
        return sorted(latest.values(), key=lambda item: item.provider_name)
