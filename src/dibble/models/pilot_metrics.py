from __future__ import annotations

from pydantic import BaseModel, Field

from dibble.models.baseline import BaselineAgreementSummary


class LearnerSessionMetrics(BaseModel):
    sessions_started: int = 0
    sessions_completed: int = 0
    completion_rate: float | None = None
    active_days: int = 0
    day_over_day_return_rate: float | None = None
    week_over_week_return_rate: float | None = None


class LearnerMasteryMetrics(BaseModel):
    snapshot_count: int = 0
    earliest_overall_kc_mastery: float | None = None
    latest_overall_kc_mastery: float | None = None
    kc_mastery_delta: float | None = None
    earliest_overall_lo_mastery: float | None = None
    latest_overall_lo_mastery: float | None = None
    lo_mastery_delta: float | None = None


class LearnerGenerationMetrics(BaseModel):
    generation_count: int = 0
    cache_hits: int = 0
    average_latency_ms: float | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    verification_failed_count: int = 0


class LearnerPilotMetrics(BaseModel):
    student_id: str
    sessions: LearnerSessionMetrics = Field(default_factory=LearnerSessionMetrics)
    mastery: LearnerMasteryMetrics = Field(default_factory=LearnerMasteryMetrics)
    defect_report_count: int = 0
    intervention_decision_counts: dict[str, int] = Field(default_factory=dict)
    baseline_agreement_rate: float | None = None
    baseline_decision_count: int = 0
    generation: LearnerGenerationMetrics = Field(
        default_factory=LearnerGenerationMetrics
    )


class CohortPilotMetrics(BaseModel):
    learner_count: int = 0
    sessions_started: int = 0
    sessions_completed: int = 0
    completion_rate: float | None = None
    average_kc_mastery_delta: float | None = None
    defect_report_count: int = 0
    intervention_decision_counts: dict[str, int] = Field(default_factory=dict)
    generation_count: int = 0
    cache_hits: int = 0
    average_latency_ms: float | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    verification_failed_count: int = 0


class PilotMetricsResponse(BaseModel):
    days: int
    learners: list[LearnerPilotMetrics] = Field(default_factory=list)
    cohort: CohortPilotMetrics = Field(default_factory=CohortPilotMetrics)
    baseline: BaselineAgreementSummary = Field(default_factory=BaselineAgreementSummary)
