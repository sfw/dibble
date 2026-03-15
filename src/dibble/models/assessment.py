from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from dibble.models.generation import (
    AdaptiveRouteDecision,
    GeneratedBlock,
    GenerationMetadata,
    GroundingReference,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SocraticMessageRole(str, Enum):
    tutor = "tutor"
    learner = "learner"


class SocraticEvidenceStrength(str, Enum):
    insufficient = "insufficient"
    emerging = "emerging"
    demonstrated = "demonstrated"


class SocraticNextAction(str, Enum):
    ask_probe = "ask_probe"
    clarify = "clarify"
    step_back = "step_back"
    advance = "advance"


class SocraticMessage(BaseModel):
    role: SocraticMessageRole
    text: str = Field(min_length=1)


class SocraticTurnRecord(BaseModel):
    turn_id: str
    prompt: str
    learner_response: str | None = None
    evaluation: "SocraticAssessmentEvaluation"
    created_at: datetime = Field(default_factory=utc_now)


class SocraticAssessmentSession(BaseModel):
    session_id: str
    student_id: UUID
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    curriculum_context: list[str] = Field(default_factory=list)
    conversation_history: list[SocraticMessage] = Field(default_factory=list)
    turns: list[SocraticTurnRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SocraticAssessmentRequest(BaseModel):
    student_id: UUID
    session_id: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    curriculum_context: list[str] = Field(default_factory=list)
    conversation_history: list[SocraticMessage] = Field(default_factory=list)
    learner_response: str | None = None
    learner_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class SocraticAssessmentEvaluation(BaseModel):
    evidence_strength: SocraticEvidenceStrength
    inferred_mastery: float = Field(ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str
    next_action: SocraticNextAction


class SocraticAssessmentResponse(BaseModel):
    session_id: str
    student_id: UUID
    turn_id: str
    prompt: str
    evaluation: SocraticAssessmentEvaluation
    route: AdaptiveRouteDecision
    grounding: list[GroundingReference] = Field(default_factory=list)
    generated_blocks: list[GeneratedBlock] = Field(default_factory=list)
    conversation_history: list[SocraticMessage] = Field(default_factory=list)
    generation_id: str | None = None
    generation_metadata: GenerationMetadata | None = None
    created_at: datetime = Field(default_factory=utc_now)


SocraticTurnRecord.model_rebuild()
