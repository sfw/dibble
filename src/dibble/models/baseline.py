from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BaselineDecisionPointSummary(BaseModel):
    decision_point: str
    total_decisions: int = 0
    agreed_decisions: int = 0
    agreement_rate: float | None = None


class BaselineDivergence(BaseModel):
    decision_point: str
    student_id: str | None = None
    production_decision: dict[str, object] = Field(default_factory=dict)
    baseline_decision: dict[str, object] = Field(default_factory=dict)
    inputs_digest: str | None = None
    created_at: datetime | None = None


class BaselineAgreementSummary(BaseModel):
    total_decisions: int = 0
    agreed_decisions: int = 0
    agreement_rate: float | None = None
    decision_points: list[BaselineDecisionPointSummary] = Field(default_factory=list)
    divergences: list[BaselineDivergence] = Field(default_factory=list)
