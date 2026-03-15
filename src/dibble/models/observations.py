from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field

from dibble.models.profile import AffectiveState, CognitiveLoadState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearnerObservationCreate(BaseModel):
    response_time_ms: int = Field(ge=0)
    hints_used: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    pause_count: int = Field(default=0, ge=0)
    modality_switches: int = Field(default=0, ge=0)
    completed: bool = True
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class LearnerObservation(LearnerObservationCreate):
    observation_id: str
    student_id: UUID
    created_at: datetime = Field(default_factory=utc_now)


class InferredLearnerState(BaseModel):
    student_id: UUID
    affective_state: AffectiveState
    cognitive_load: CognitiveLoadState
    observation_count: int = Field(default=0, ge=0)
    last_observation_at: datetime | None = None
