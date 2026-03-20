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


class LearnerInteractionEvent(BaseModel):
    event_type: str
    block_id: str
    selected_option_id: str | None = None
    correct: bool | None = None
    response_text: str | None = None


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
    learning_session_id: str | None = None
    generation_id: str | None = None
    observed_content_type: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    interaction_events: list[LearnerInteractionEvent] = Field(default_factory=list)
    response_text: str | None = None


class LearnerObservation(LearnerObservationCreate):
    observation_id: str
    student_id: UUID
    created_at: datetime = Field(default_factory=utc_now)


class CurrentEvidenceSignal(BaseModel):
    signal: str = "steady"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    challenge_exposure: float = Field(default=0.0, ge=0.0, le=1.0)
    productive_struggle_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overload_score: float = Field(default=0.0, ge=0.0, le=1.0)
    disengagement_score: float = Field(default=0.0, ge=0.0, le=1.0)
    support_dependence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str | None = None


class InferredLearnerState(BaseModel):
    student_id: UUID
    affective_state: AffectiveState
    cognitive_load: CognitiveLoadState
    metacognitive_state: MetacognitiveState
    current_evidence: CurrentEvidenceSignal | None = None
    observation_count: int = Field(default=0, ge=0)
    last_observation_at: datetime | None = None
