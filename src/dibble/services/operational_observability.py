from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from dibble.models.observability import (
    CloudLibraryReadiness,
    HarnessBoundary,
    HarnessFallbackCount,
    OperationalTrace,
    OperationalTraceStatus,
    PendingReviewQueue,
    ReleaseReadinessSnapshot,
    StaleAutonomousSuggestionDiagnostic,
    StuckMigrationPlanDiagnostic,
)
from dibble.services.operational_trace_store import SQLiteOperationalTraceStore
from dibble.services.protocols import (
    CurriculumMigrationPlanStore,
    LearnerRelationshipStateStore,
    ProviderHealthStore,
    UserStore,
)
from dibble.services.runtime_telemetry import current_request_id, current_session_id

_SUGGESTION_STALE_AFTER = timedelta(hours=48)
_MIGRATION_STUCK_AFTER = timedelta(hours=24)


@dataclass(slots=True)
class OperationalObservabilityService:
    trace_store: SQLiteOperationalTraceStore
    provider_health_store: ProviderHealthStore | None = None
    curriculum_migration_plan_store: CurriculumMigrationPlanStore | None = None
    learner_relationship_state_store: LearnerRelationshipStateStore | None = None
    user_store: UserStore | None = None
    content_library: Any | None = None

    def record_trace(
        self,
        *,
        harness: HarnessBoundary,
        operation: str,
        status: OperationalTraceStatus,
        summary: str,
        request_id: str | None = None,
        session_id: str | None = None,
        student_id: str | None = None,
        household_id: str | None = None,
        entity_kind: str | None = None,
        entity_id: str | None = None,
        degraded_mode: bool = False,
        degraded_reason: str | None = None,
        fallback_kind: str | None = None,
        fallback_provenance: str | None = None,
        reason_code: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> OperationalTrace:
        return self.trace_store.append(
            harness=harness,
            operation=operation,
            status=status,
            summary=summary,
            request_id=request_id or current_request_id(),
            session_id=session_id or current_session_id(),
            student_id=student_id,
            household_id=household_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            degraded_mode=degraded_mode,
            degraded_reason=degraded_reason,
            fallback_kind=fallback_kind,
            fallback_provenance=fallback_provenance,
            reason_code=reason_code,
            payload=payload,
        )

    def list_traces(
        self,
        *,
        limit: int = 100,
        harness: HarnessBoundary | None = None,
        degraded_only: bool = False,
        request_id: str | None = None,
        session_id: str | None = None,
    ) -> list[OperationalTrace]:
        return self.trace_store.list(
            limit=limit,
            harness=harness,
            degraded_only=degraded_only,
            request_id=request_id,
            session_id=session_id,
        )

    def release_readiness_snapshot(self) -> ReleaseReadinessSnapshot:
        recent_traces = self.trace_store.list(limit=500)
        degraded_traces = [trace for trace in recent_traces if trace.degraded_mode]
        fallback_counts = self._fallback_counts(recent_traces)
        return ReleaseReadinessSnapshot(
            total_recent_traces=len(recent_traces),
            degraded_trace_count=len(degraded_traces),
            provider_statuses=(
                self.provider_health_store.latest_statuses()
                if self.provider_health_store is not None
                else []
            ),
            fallback_counts=fallback_counts,
            pending_review_queues=self._pending_review_queues(),
            stuck_migration_plans=self._stuck_migration_plans(),
            stale_autonomous_suggestions=self._stale_autonomous_suggestions(),
            cloud_library=self._cloud_library_readiness(recent_traces),
            recent_degraded_operations=degraded_traces[:20],
        )

    def _fallback_counts(
        self, traces: list[OperationalTrace]
    ) -> list[HarnessFallbackCount]:
        counts = Counter(
            (
                trace.harness,
                trace.fallback_kind or trace.reason_code or "degraded_without_fallback",
            )
            for trace in traces
            if trace.degraded_mode or trace.fallback_kind
        )
        return [
            HarnessFallbackCount(
                harness=harness,
                fallback_kind=fallback_kind,
                count=count,
            )
            for (harness, fallback_kind), count in sorted(
                counts.items(),
                key=lambda item: (item[0][0].value, item[0][1]),
            )
        ]

    def _pending_review_queues(self) -> list[PendingReviewQueue]:
        queues: list[PendingReviewQueue] = []
        if self.curriculum_migration_plan_store is not None:
            plans = self.curriculum_migration_plan_store.list()
            migration_review_count = sum(len(plan.review_items) for plan in plans)
            if migration_review_count:
                queues.append(
                    PendingReviewQueue(
                        queue_key="curriculum_migration_review",
                        count=migration_review_count,
                        summary="Migration review items are still awaiting operator review.",
                    )
                )
            failed_action_count = sum(
                1
                for plan in plans
                for action in plan.actions
                if action.status == "execution_failed"
            )
            if failed_action_count:
                queues.append(
                    PendingReviewQueue(
                        queue_key="curriculum_migration_failures",
                        count=failed_action_count,
                        summary="Some approved migration actions failed during execution.",
                    )
                )
        pending_approvals = len(self._pending_approvals())
        if pending_approvals:
            queues.append(
                PendingReviewQueue(
                    queue_key="parent_approvals",
                    count=pending_approvals,
                    summary="Parent approval gates are blocking autonomous teaching changes.",
                )
            )
        return queues

    def _stuck_migration_plans(self) -> list[StuckMigrationPlanDiagnostic]:
        if self.curriculum_migration_plan_store is None:
            return []
        now = datetime.now(timezone.utc)
        stuck: list[StuckMigrationPlanDiagnostic] = []
        for plan in self.curriculum_migration_plan_store.list():
            failed_action_count = sum(
                1 for action in plan.actions if action.status == "execution_failed"
            )
            approved_action_count = sum(
                1 for action in plan.actions if action.status == "approved"
            )
            should_include = (
                failed_action_count > 0
                or (
                    plan.status in {"draft", "ready", "partial_failure"}
                    and now - plan.updated_at >= _MIGRATION_STUCK_AFTER
                )
            )
            if not should_include:
                continue
            stuck.append(
                StuckMigrationPlanDiagnostic(
                    plan_id=plan.plan_id,
                    status=plan.status.value if hasattr(plan.status, "value") else str(plan.status),
                    approved_action_count=approved_action_count,
                    failed_action_count=failed_action_count,
                    review_item_count=len(plan.review_items),
                    updated_at=plan.updated_at,
                )
            )
        stuck.sort(key=lambda item: item.updated_at)
        return stuck[:20]

    def _stale_autonomous_suggestions(self) -> list[StaleAutonomousSuggestionDiagnostic]:
        if self.learner_relationship_state_store is None or self.user_store is None:
            return []
        now = datetime.now(timezone.utc)
        stale: list[StaleAutonomousSuggestionDiagnostic] = []
        household_ids = {
            user.household_id
            for user in self.user_store.list()
            if user.household_id is not None
        }
        for household_id in sorted(household_ids):
            for state in self.learner_relationship_state_store.list_for_household(
                household_id=household_id
            ):
                updated_at = state.session_suggestion_updated_at or state.updated_at
                if now - updated_at < _SUGGESTION_STALE_AFTER:
                    continue
                if state.session_suggestion_status in {"completed", "dismissed"}:
                    continue
                stale.append(
                    StaleAutonomousSuggestionDiagnostic(
                        household_id=household_id,
                        learner_id=state.learner_id,
                        status=state.session_suggestion_status,
                        pending_approval_count=len(
                            [
                                approval
                                for approval in state.approval_requests
                                if approval.status == "pending"
                            ]
                        ),
                        updated_at=updated_at,
                        hours_stale=int((now - updated_at).total_seconds() // 3600),
                    )
                )
        stale.sort(key=lambda item: item.updated_at)
        return stale[:20]

    def _cloud_library_readiness(
        self, traces: list[OperationalTrace]
    ) -> CloudLibraryReadiness:
        remote_enabled = False
        remote_endpoint: str | None = None
        if self.content_library is not None:
            remote_client = getattr(self.content_library, "remote_client", None)
            remote_enabled = remote_client is not None
            remote_endpoint = getattr(remote_client, "endpoint", None)
        library_traces = [
            trace for trace in traces if trace.harness == HarnessBoundary.content_library
        ]
        degraded = [trace for trace in library_traces if trace.degraded_mode]
        return CloudLibraryReadiness(
            remote_enabled=remote_enabled,
            degraded=bool(degraded),
            recent_lookup_failures=sum(
                1
                for trace in degraded
                if trace.reason_code == "remote_lookup_failed_local_fallback"
            ),
            recent_publish_failures=sum(
                1
                for trace in degraded
                if trace.reason_code == "remote_publish_failed_local_only"
            ),
            remote_endpoint=remote_endpoint,
            last_degraded_at=degraded[0].created_at if degraded else None,
            last_degraded_reason=degraded[0].degraded_reason if degraded else None,
        )

    def _pending_approvals(self) -> list[tuple[str, str]]:
        if self.learner_relationship_state_store is None or self.user_store is None:
            return []
        pending: list[tuple[str, str]] = []
        household_ids = {
            user.household_id
            for user in self.user_store.list()
            if user.household_id is not None
        }
        for household_id in household_ids:
            for state in self.learner_relationship_state_store.list_for_household(
                household_id=household_id
            ):
                for approval in state.approval_requests:
                    if approval.status == "pending":
                        pending.append((household_id, approval.approval_id))
        return pending
