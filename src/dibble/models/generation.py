from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContentIntent(str, Enum):
    explanation = "explanation"
    practice = "practice"
    remediation = "remediation"
    assessment = "assessment"


class InterventionType(str, Enum):
    step_back = "step_back"
    targeted_practice = "targeted_practice"
    reteach = "reteach"
    stretch = "stretch"


class DeliveryMode(str, Enum):
    generated = "generated"
    blended = "blended"
    static_fallback = "static_fallback"


class GenerationRequest(BaseModel):
    student_id: UUID
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    intent: ContentIntent = ContentIntent.explanation
    learner_prompt: str | None = None
    curriculum_context: list[str] = Field(default_factory=list)


class AdaptiveRouteDecision(BaseModel):
    intervention_type: InterventionType
    delivery_mode: DeliveryMode
    scaffolding_level: str
    reasons: list[str]


class GroundingReference(BaseModel):
    resource_id: str
    title: str
    grade_level: str
    score: float = Field(ge=0.0)
    matched_terms: list[str] = Field(default_factory=list)


class GeneratedBlock(BaseModel):
    kind: str
    title: str
    body: str


class GenerationResponse(BaseModel):
    student_id: UUID
    generated_at: datetime = Field(default_factory=utc_now)
    route: AdaptiveRouteDecision
    blocks: list[GeneratedBlock]
    curriculum_context: list[str]
    grounding: list[GroundingReference] = Field(default_factory=list)
    safety_notes: list[str]
    validation_issues: list[str] = Field(default_factory=list)
