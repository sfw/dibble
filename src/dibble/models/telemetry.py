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


class TelemetrySnapshot(BaseModel):
    total_events: int = 0
    decision_events: int = 0
    generation_events: int = 0
    fallback_generations: int = 0
    validation_issue_events: int = 0
    last_event_at: datetime | None = None
