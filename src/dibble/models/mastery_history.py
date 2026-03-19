from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MasterySnapshot(BaseModel):
    snapshot_id: str
    student_id: str
    overall_kc_mastery: float = Field(ge=0.0, le=1.0)
    overall_lo_mastery: float = Field(ge=0.0, le=1.0)
    kc_count: int = Field(ge=0)
    lo_count: int = Field(ge=0)
    mastered_kc_count: int = Field(ge=0)
    struggling_kc_count: int = Field(ge=0)
    engagement: str = "medium"
    frustration: str = "none"
    total_load: float = Field(default=0.4, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)


class MasteryHistoryResponse(BaseModel):
    student_id: str
    days: int
    snapshot_count: int = Field(ge=0)
    snapshots: list[MasterySnapshot] = Field(default_factory=list)


class LearnerMasteryTrend(BaseModel):
    student_id: str
    snapshot_count: int = Field(ge=0)
    snapshots: list[MasterySnapshot] = Field(default_factory=list)
    earliest_mastery: float | None = None
    latest_mastery: float | None = None
    mastery_delta: float = 0.0


class SectionMasteryTrendsResponse(BaseModel):
    section_id: str
    days: int
    learner_count: int = Field(ge=0)
    learner_trends: list[LearnerMasteryTrend] = Field(default_factory=list)
    section_average_snapshots: list[SectionAveragePoint] = Field(default_factory=list)


class SectionAveragePoint(BaseModel):
    timestamp: datetime
    average_mastery: float = Field(ge=0.0, le=1.0)
    learner_count: int = Field(ge=0)


# Forward reference fix: SectionMasteryTrendsResponse uses SectionAveragePoint
SectionMasteryTrendsResponse.model_rebuild()
