from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from dibble.models.telemetry import ProviderHealthEvent, ProviderStatusSnapshot


@dataclass(slots=True)
class ProviderRoutingSnapshot:
    provider_name: str
    latest_status: str | None = None
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    average_latency_ms: float | None = None
    open_until: float | None = None


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

    def routing_snapshots(
        self, *, provider_names: list[str] | None = None, limit: int = 500
    ) -> list[ProviderRoutingSnapshot]:
        events = self.list(limit=limit)
        allowed = set(provider_names) if provider_names is not None else None
        snapshots: dict[str, ProviderRoutingSnapshot] = {}

        for event in events:
            if allowed is not None and event.provider_name not in allowed:
                continue

            snapshot = snapshots.setdefault(
                event.provider_name,
                ProviderRoutingSnapshot(provider_name=event.provider_name),
            )
            if snapshot.latest_status is None:
                snapshot.latest_status = event.status

            if event.status in {"success", "circuit_recovered"}:
                snapshot.successful_requests += 1
            if event.status == "failure":
                snapshot.failed_requests += 1

            average_latency = event.detail.get("average_latency_ms")
            if snapshot.average_latency_ms is None and isinstance(
                average_latency, (int, float)
            ):
                snapshot.average_latency_ms = float(average_latency)

            if (
                snapshot.latest_status in {"circuit_open", "circuit_skip"}
                and snapshot.open_until is None
                and event.status == "circuit_open"
            ):
                open_until = event.detail.get("open_until")
                if isinstance(open_until, (int, float)):
                    snapshot.open_until = float(open_until)

        for provider_name, snapshot in snapshots.items():
            recent_events = [
                event
                for event in events
                if event.provider_name == provider_name
                and (allowed is None or provider_name in allowed)
            ]
            for event in recent_events:
                if event.status in {"success", "circuit_recovered"}:
                    break
                if event.status == "failure":
                    snapshot.consecutive_failures += 1
            if snapshot.open_until is not None:
                snapshot.consecutive_failures = max(snapshot.consecutive_failures, 1)

        return sorted(snapshots.values(), key=lambda item: item.provider_name)
