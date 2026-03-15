from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SignalLevel(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class PacePreference(str, Enum):
    slower = "slower_than_average"
    average = "average"
    faster = "faster_than_average"


class ScaffoldingLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CognitiveTraitScore(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    assessed_at: datetime = Field(default_factory=utc_now)


class AffectiveState(BaseModel):
    engagement: SignalLevel = SignalLevel.medium
    frustration: SignalLevel = SignalLevel.none
    confusion: SignalLevel = SignalLevel.low
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    inferred_at: datetime = Field(default_factory=utc_now)


class CognitiveLoadState(BaseModel):
    intrinsic_load: float = Field(default=0.3, ge=0.0, le=1.0)
    extraneous_load: float = Field(default=0.2, ge=0.0, le=1.0)
    germane_load: float = Field(default=0.4, ge=0.0, le=1.0)
    total_load: float = Field(default=0.4, ge=0.0, le=1.0)
    capacity_utilization: float = Field(default=0.4, ge=0.0, le=1.0)
    inferred_at: datetime = Field(default_factory=utc_now)


class LearningPreferences(BaseModel):
    modality_affinity: dict[str, float] = Field(
        default_factory=lambda: {
            "textual": 0.8,
            "interactive": 0.7,
            "visual": 0.6,
            "video": 0.5,
        }
    )
    example_domain_preferences: list[str] = Field(default_factory=list)
    scaffolding_preference: ScaffoldingLevel = ScaffoldingLevel.medium
    pace_preference: PacePreference = PacePreference.average


class KnowledgeState(BaseModel):
    lo_mastery: dict[str, float] = Field(default_factory=dict)
    kc_mastery: dict[str, float] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=utc_now)


class LearnerProfile(BaseModel):
    student_id: UUID
    grade_level: str
    profile_version: str = "2.0"
    cognitive_traits: dict[str, CognitiveTraitScore] = Field(default_factory=dict)
    knowledge_state: KnowledgeState = Field(default_factory=KnowledgeState)
    affective_state: AffectiveState = Field(default_factory=AffectiveState)
    cognitive_load: CognitiveLoadState = Field(default_factory=CognitiveLoadState)
    learning_preferences: LearningPreferences = Field(default_factory=LearningPreferences)
    accommodations: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileSummary(BaseModel):
    student_id: UUID
    grade_level: str
    profile_version: str
    kc_count: int
    lo_count: int
    frustration: SignalLevel
    total_load: float
    updated_at: datetime

    @classmethod
    def from_profile(cls, profile: LearnerProfile) -> "ProfileSummary":
        return cls(
            student_id=profile.student_id,
            grade_level=profile.grade_level,
            profile_version=profile.profile_version,
            kc_count=len(profile.knowledge_state.kc_mastery),
            lo_count=len(profile.knowledge_state.lo_mastery),
            frustration=profile.affective_state.frustration,
            total_load=profile.cognitive_load.total_load,
            updated_at=profile.updated_at,
        )
