from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStartResponse(BaseModel):
    learning_session_id: str
    goal_display: str
    focus_outcome_title: str | None = None
    started_at: datetime = Field(default_factory=utc_now)


class SessionEndRequest(BaseModel):
    learning_session_id: str


class SessionRecap(BaseModel):
    learning_session_id: str
    completed_activity_count: int = 0
    smooth_activity_count: int = 0
    display_recap: str = ""
    ended_at: datetime = Field(default_factory=utc_now)


class DefectReportRequest(BaseModel):
    generation_id: str
    learning_session_id: str | None = None
    note: str | None = Field(default=None, max_length=500)


class DefectReportResponse(BaseModel):
    status: str = "recorded"
    display_message: str = "Thanks for letting us know — we'll take a look."
