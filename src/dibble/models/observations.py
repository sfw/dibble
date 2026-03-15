from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from dibble.models.profile import AffectiveState, CognitiveLoadState, MetacognitiveState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ObservationTaskType(str, Enum):
    generic = "generic"
    explanation = "explanation"
    practice = "practice"
    worked_example = "worked_example"
    assessment = "assessment"
    remediation = "remediation"


class ObservationSupportLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class LearnerObservationCreate(BaseModel):
    response_time_ms: int = Field(ge=0)
    hints_used: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    pause_count: int = Field(default=0, ge=0)
    modality_switches: int = Field(default=0, ge=0)
    completed: bool = True
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    task_type: ObservationTaskType = ObservationTaskType.generic
    support_level: ObservationSupportLevel = ObservationSupportLevel.medium
    expected_duration_ms: int | None = Field(default=None, ge=1)


class LearnerObservation(LearnerObservationCreate):
    observation_id: str
    student_id: UUID
    created_at: datetime = Field(default_factory=utc_now)


class InferredLearnerState(BaseModel):
    student_id: UUID
    affective_state: AffectiveState
    cognitive_load: CognitiveLoadState
    metacognitive_state: MetacognitiveState
    observation_count: int = Field(default=0, ge=0)
    last_observation_at: datetime | None = None
