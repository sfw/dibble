from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RetentionReviewReason(str, Enum):
    strengthened_kc_writeback = "strengthened_kc_writeback"
    outcome_mastered = "outcome_mastered"
    outcome_near_mastered = "outcome_near_mastered"
    recovery_after_stall = "recovery_after_stall"
    concept_cluster_risk = "concept_cluster_risk"


class RetentionStrengthTier(str, Enum):
    light = "light"
    standard = "standard"
    urgent = "urgent"


class RetentionReviewStatus(str, Enum):
    scheduled = "scheduled"
    due = "due"
    completed = "completed"
    expired = "expired"
    suppressed = "suppressed"


class RetentionReviewCandidate(BaseModel):
    candidate_id: str
    learner_id: UUID
    kc_ids: list[str] = Field(default_factory=list)
    cluster_key: str | None = None
    outcome_id: str | None = None
    review_reason: RetentionReviewReason
    retention_strength_tier: RetentionStrengthTier = RetentionStrengthTier.standard
    due_at: datetime
    last_reviewed_at: datetime | None = None
    last_successful_review_at: datetime | None = None
    review_count: int = Field(default=0, ge=0)
    last_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    status: RetentionReviewStatus = RetentionReviewStatus.scheduled
    suppression_reason: str | None = None
    rationale: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _stabilize_cluster_key(self) -> "RetentionReviewCandidate":
        if self.cluster_key is None:
            self.cluster_key = retention_cluster_key(
                kc_ids=self.kc_ids,
                outcome_id=self.outcome_id,
            )
        self.kc_ids = sorted(dict.fromkeys(self.kc_ids))
        return self


class RetentionSuppressionContext(BaseModel):
    active_repair_kc_ids: list[str] = Field(default_factory=list)
    blocked_prerequisite_kc_ids: list[str] = Field(default_factory=list)
    active_target_kc_ids: list[str] = Field(default_factory=list)
    fragile_kc_ids: list[str] = Field(default_factory=list)
    support_dependent_kc_ids: list[str] = Field(default_factory=list)
    overload_risk: float = Field(default=0.0, ge=0.0, le=1.0)


def retention_cluster_key(
    *, kc_ids: list[str], outcome_id: str | None = None, cluster_key: str | None = None
) -> str:
    if cluster_key:
        return cluster_key
    if outcome_id:
        return f"outcome:{outcome_id}"
    normalized = sorted(dict.fromkeys(kc_ids))
    return "kc:" + ",".join(normalized)
