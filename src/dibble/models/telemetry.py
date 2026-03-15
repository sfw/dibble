from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(BaseModel):
    event_id: str
    event_type: str
    status: str
    student_id: UUID | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ProviderHealthEvent(BaseModel):
    event_id: str
    provider_name: str
    status: str
    detail: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ProviderStatusSnapshot(BaseModel):
    provider_name: str
    status: str
    detail: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime


class TelemetrySnapshot(BaseModel):
    total_events: int = 0
    decision_events: int = 0
    generation_events: int = 0
    fallback_generations: int = 0
    validation_issue_events: int = 0
    provider_failure_events: int = 0
    provider_circuit_open_events: int = 0
    provider_statuses: list[ProviderStatusSnapshot] = Field(default_factory=list)
    last_event_at: datetime | None = None
