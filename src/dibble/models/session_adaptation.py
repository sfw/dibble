from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WithinSessionControllerState(BaseModel):
    learning_session_id: str
    student_id: UUID
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    signal: str = "insufficient"
    source: str = "session_controller"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    support_bias: int = Field(default=0, ge=-1, le=1)
    sequence_action: str = "monitor"
    primary_kc_id: str | None = None
    phase: str = "monitor"
    recovery_intent: str = "monitor"
    support_step_budget: int = Field(default=0, ge=0)
    support_steps_remaining: int = Field(default=0, ge=0)
    stuck_loop_risk: str = "low"
    arc_action: str = "steady"
    observation_count: int = Field(default=0, ge=0)
    assessment_count: int = Field(default=0, ge=0)
    generation_count: int = Field(default=0, ge=0)
    positive_streak: int = Field(default=0, ge=0)
    negative_streak: int = Field(default=0, ge=0)
    mixed_streak: int = Field(default=0, ge=0)
    latest_assessment_prompt_style: str | None = None
    latest_assessment_next_action: str = "monitor"
    latest_assessment_evidence_strength: str = "insufficient"
    socratic_steering_action: str = "steady"
    last_generated_content_type: str | None = None
    last_generation_id: str | None = None
    rationale: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
