from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from dibble.models.generation import GeneratedBlock


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlacementProbe(BaseModel):
    kc_id: str
    kc_name: str
    generation_id: str | None = None
    block: GeneratedBlock | None = None
    correct: bool | None = None
    responded_at: datetime | None = None


class PlacementSession(BaseModel):
    session_id: str
    student_id: str
    grade_band: str
    status: str = "active"  # active | completed
    question_budget: int = 15
    probes: list[PlacementProbe] = Field(default_factory=list)
    queued_kc_ids: list[str] = Field(default_factory=list)
    probed_kc_ids: list[str] = Field(default_factory=list)
    demonstrated_kc_ids: list[str] = Field(default_factory=list)
    gap_kc_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlacementStartRequest(BaseModel):
    grade_band: str
    question_budget: int = Field(default=15, ge=4, le=25)


class PlacementRespondRequest(BaseModel):
    selected_option_id: str | None = None
    # Fallback for probes whose item carries no multiple-choice interaction
    # (e.g. deterministic fallback content); graded server-side otherwise.
    correct: bool | None = None


class PlacementKcSummary(BaseModel):
    kc_id: str
    name: str


class PlacementReport(BaseModel):
    """Parent-readable placement summary, rendered from backend-owned fields."""

    grade_band: str
    probed_count: int = 0
    strong_kcs: list[PlacementKcSummary] = Field(default_factory=list)
    gap_kcs: list[PlacementKcSummary] = Field(default_factory=list)
    starting_kcs: list[PlacementKcSummary] = Field(default_factory=list)
    display_summary: str = ""


class PlacementItemView(BaseModel):
    kc_id: str
    block: GeneratedBlock


class PlacementStateResponse(BaseModel):
    session_id: str
    student_id: str
    status: str
    grade_band: str
    probe_index: int = 0
    question_budget: int = 15
    current_item: PlacementItemView | None = None
    report: PlacementReport | None = None
