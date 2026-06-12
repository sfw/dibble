"""Pilot metrics read model.

Aggregates the audit trail, mastery snapshots, and baseline shadow events into
the per-learner and cohort numbers the weekly pilot review needs, so the
review requires zero ad-hoc SQL. (POC roadmap 0.2)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from dibble.models.pilot_metrics import (
    CohortPilotMetrics,
    LearnerGenerationMetrics,
    LearnerMasteryMetrics,
    LearnerPilotMetrics,
    LearnerSessionMetrics,
    PilotMetricsResponse,
)
from dibble.models.telemetry import AuditEvent
from dibble.services.baseline_policy import (
    BASELINE_DECISION_EVENT_TYPE,
    BaselinePolicyService,
)
from dibble.services.mastery_snapshot_service import MasterySnapshotService
from dibble.services.protocols import AuditStore, ProfileStore

from dibble.services.math_verification import VERIFICATION_FAILED_EVENT_TYPE

SESSION_STARTED_EVENT_TYPE = "learning.session.started"
SESSION_COMPLETED_EVENT_TYPE = "learning.session.completed"
DEFECT_REPORT_EVENT_TYPE = "content.defect.report"
INTERVENTION_DECISION_EVENT_TYPE = "teacher.intervention.decision"
GENERATION_EVENT_TYPE = "content.generate"


@dataclass(slots=True)
class PilotMetricsService:
    audit_store: AuditStore
    profile_store: ProfileStore
    mastery_snapshot_service: MasterySnapshotService
    baseline_policy_service: BaselinePolicyService

    def summarize(self, *, days: int = 90, limit: int = 10000) -> PilotMetricsResponse:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        events = [
            event
            for event in self.audit_store.list(limit=limit)
            if event.created_at >= cutoff
        ]
        events_by_student: dict[str, list[AuditEvent]] = {}
        for event in events:
            if event.student_id is None:
                continue
            events_by_student.setdefault(str(event.student_id), []).append(event)

        learner_ids = set(self.profile_store.list_ids()) | set(events_by_student)
        learners = [
            self._learner_metrics(
                student_id=student_id,
                events=events_by_student.get(student_id, []),
                days=days,
            )
            for student_id in sorted(learner_ids)
        ]
        return PilotMetricsResponse(
            days=days,
            learners=learners,
            cohort=self._cohort_metrics(learners),
            baseline=self.baseline_policy_service.agreement_summary(limit=limit),
        )

    def _learner_metrics(
        self, *, student_id: str, events: list[AuditEvent], days: int
    ) -> LearnerPilotMetrics:
        sessions = self._session_metrics(events)
        mastery = self._mastery_metrics(student_id=student_id, days=days)
        defect_count = sum(
            1 for event in events if event.event_type == DEFECT_REPORT_EVENT_TYPE
        )
        intervention_counts = Counter(
            str(event.payload.get("decision", "unknown"))
            for event in events
            if event.event_type == INTERVENTION_DECISION_EVENT_TYPE
        )
        baseline_events = [
            event
            for event in events
            if event.event_type == BASELINE_DECISION_EVENT_TYPE
        ]
        baseline_agreed = sum(
            1 for event in baseline_events if event.status == "agreed"
        )
        return LearnerPilotMetrics(
            student_id=student_id,
            sessions=sessions,
            mastery=mastery,
            defect_report_count=defect_count,
            intervention_decision_counts=dict(intervention_counts),
            baseline_decision_count=len(baseline_events),
            baseline_agreement_rate=(
                round(baseline_agreed / len(baseline_events), 4)
                if baseline_events
                else None
            ),
            generation=self._generation_metrics(events),
        )

    def _session_metrics(self, events: list[AuditEvent]) -> LearnerSessionMetrics:
        started = [
            event for event in events if event.event_type == SESSION_STARTED_EVENT_TYPE
        ]
        completed = [
            event
            for event in events
            if event.event_type == SESSION_COMPLETED_EVENT_TYPE
        ]
        active_days = sorted({event.created_at.date() for event in started})
        return LearnerSessionMetrics(
            sessions_started=len(started),
            sessions_completed=len(completed),
            completion_rate=(
                round(min(len(completed) / len(started), 1.0), 4) if started else None
            ),
            active_days=len(active_days),
            day_over_day_return_rate=self._consecutive_rate(active_days, step_days=1),
            week_over_week_return_rate=self._consecutive_rate(
                sorted({day - timedelta(days=day.weekday()) for day in active_days}),
                step_days=7,
            ),
        )

    def _consecutive_rate(
        self, ordered_days: list[date], *, step_days: int
    ) -> float | None:
        if len(ordered_days) < 2:
            return None
        step = timedelta(days=step_days)
        consecutive = sum(
            1
            for previous, current in zip(ordered_days, ordered_days[1:])
            if current - previous == step
        )
        return round(consecutive / (len(ordered_days) - 1), 4)

    def _mastery_metrics(self, *, student_id: str, days: int) -> LearnerMasteryMetrics:
        try:
            history = self.mastery_snapshot_service.get_learner_history(
                student_id=UUID(student_id), days=days
            )
        except ValueError:
            return LearnerMasteryMetrics()
        snapshots = sorted(history.snapshots, key=lambda item: item.created_at)
        if not snapshots:
            return LearnerMasteryMetrics()
        earliest, latest = snapshots[0], snapshots[-1]
        return LearnerMasteryMetrics(
            snapshot_count=len(snapshots),
            earliest_overall_kc_mastery=earliest.overall_kc_mastery,
            latest_overall_kc_mastery=latest.overall_kc_mastery,
            kc_mastery_delta=round(
                latest.overall_kc_mastery - earliest.overall_kc_mastery, 4
            ),
            earliest_overall_lo_mastery=earliest.overall_lo_mastery,
            latest_overall_lo_mastery=latest.overall_lo_mastery,
            lo_mastery_delta=round(
                latest.overall_lo_mastery - earliest.overall_lo_mastery, 4
            ),
        )

    def _generation_metrics(self, events: list[AuditEvent]) -> LearnerGenerationMetrics:
        generation_events = [
            event for event in events if event.event_type == GENERATION_EVENT_TYPE
        ]
        latencies = [
            float(event.payload.get("generation_latency_ms", 0) or 0)
            for event in generation_events
        ]
        return LearnerGenerationMetrics(
            generation_count=len(generation_events),
            cache_hits=sum(
                1
                for event in generation_events
                if bool(event.payload.get("cache_hit", False))
            ),
            average_latency_ms=(
                round(sum(latencies) / len(latencies), 2) if latencies else None
            ),
            total_prompt_tokens=sum(
                int(event.payload.get("prompt_tokens", 0) or 0)
                for event in generation_events
            ),
            total_completion_tokens=sum(
                int(event.payload.get("completion_tokens", 0) or 0)
                for event in generation_events
            ),
            verification_failed_count=sum(
                1
                for event in events
                if event.event_type == VERIFICATION_FAILED_EVENT_TYPE
            ),
        )

    def _cohort_metrics(
        self, learners: list[LearnerPilotMetrics]
    ) -> CohortPilotMetrics:
        intervention_counts: Counter[str] = Counter()
        for learner in learners:
            intervention_counts.update(learner.intervention_decision_counts)
        sessions_started = sum(item.sessions.sessions_started for item in learners)
        sessions_completed = sum(item.sessions.sessions_completed for item in learners)
        mastery_deltas = [
            item.mastery.kc_mastery_delta
            for item in learners
            if item.mastery.kc_mastery_delta is not None
        ]
        latencies = [
            item.generation.average_latency_ms
            for item in learners
            if item.generation.average_latency_ms is not None
        ]
        return CohortPilotMetrics(
            learner_count=len(learners),
            sessions_started=sessions_started,
            sessions_completed=sessions_completed,
            completion_rate=(
                round(min(sessions_completed / sessions_started, 1.0), 4)
                if sessions_started
                else None
            ),
            average_kc_mastery_delta=(
                round(sum(mastery_deltas) / len(mastery_deltas), 4)
                if mastery_deltas
                else None
            ),
            defect_report_count=sum(item.defect_report_count for item in learners),
            intervention_decision_counts=dict(intervention_counts),
            generation_count=sum(item.generation.generation_count for item in learners),
            cache_hits=sum(item.generation.cache_hits for item in learners),
            average_latency_ms=(
                round(sum(latencies) / len(latencies), 2) if latencies else None
            ),
            total_prompt_tokens=sum(
                item.generation.total_prompt_tokens for item in learners
            ),
            total_completion_tokens=sum(
                item.generation.total_completion_tokens for item in learners
            ),
            verification_failed_count=sum(
                item.generation.verification_failed_count for item in learners
            ),
        )
