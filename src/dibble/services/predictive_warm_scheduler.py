from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.models.generation import (
    PredictiveWarmClaimDetail,
    PredictiveWarmProcessResult,
)
from dibble.services.content_warmer import ContentWarmer
from dibble.services.predictive_content_warming import PredictiveWarmPlan
from dibble.services.protocols import PredictiveWarmTaskStore


@dataclass(frozen=True, slots=True)
class PredictiveWarmEnqueueResult:
    enqueued_count: int = 0
    duplicate_count: int = 0
    task_ids: list[str] | None = None
    pending_tasks: int = 0


@dataclass(slots=True)
class PredictiveWarmScheduler:
    queue_store: PredictiveWarmTaskStore
    content_warmer: ContentWarmer
    inline_process_limit: int = 2

    def enqueue_plan(self, *, plan: PredictiveWarmPlan) -> PredictiveWarmEnqueueResult:
        task_ids: list[str] = []
        enqueued_count = 0
        duplicate_count = 0
        for request in plan.requests:
            task = self.queue_store.enqueue(request=request)
            if task is None:
                duplicate_count += 1
                continue
            task_ids.append(task.task_id)
            enqueued_count += 1
        pending_tasks = self.queue_store.stats().get("pending", 0)
        return PredictiveWarmEnqueueResult(
            enqueued_count=enqueued_count,
            duplicate_count=duplicate_count,
            task_ids=task_ids,
            pending_tasks=pending_tasks,
        )

    def process_inline(self, *, task_ids: list[str]) -> PredictiveWarmProcessResult:
        if self.inline_process_limit <= 0:
            return self._idle_result(
                worker_id="inline_scheduler", execution_mode="inline"
            )
        sweep_result = self.queue_store.sweep()
        claimed = (
            self.queue_store.claim_tasks(
                task_ids=task_ids[: self.inline_process_limit],
                claim_owner="inline_scheduler",
                claim_mode="inline_targeted",
                claim_reason="fresh predictive follow-up from the current generation request",
                stale_recovered_task_ids=sweep_result.requeued_task_ids,
            )
            if task_ids
            else []
        )
        remaining_capacity = max(0, self.inline_process_limit - len(claimed))
        supplemental = (
            self.queue_store.claim_pending(
                limit=remaining_capacity,
                claim_owner="inline_scheduler",
                claim_mode="inline_autonomous",
                claim_reason="spare inline scheduler capacity drained other eligible backlog work",
                stale_recovered_task_ids=sweep_result.requeued_task_ids,
            )
            if remaining_capacity > 0
            else []
        )
        return self._process_tasks(
            [*claimed, *supplemental],
            worker_id="inline_scheduler",
            execution_mode="inline",
            targeted_tasks=len(claimed),
            supplemental_tasks=len(supplemental),
            requeued_tasks=sweep_result.requeued_tasks,
            expired_tasks=sweep_result.expired_tasks,
        )

    def process_pending(self, *, limit: int = 10) -> PredictiveWarmProcessResult:
        sweep_result = self.queue_store.sweep()
        return self._process_tasks(
            self.queue_store.claim_pending(
                limit=limit,
                claim_owner="queue_processor",
                claim_mode="background_drain",
                claim_reason="explicit predictive warm queue processing request",
                stale_recovered_task_ids=sweep_result.requeued_task_ids,
            ),
            worker_id="queue_processor",
            execution_mode="background",
            requeued_tasks=sweep_result.requeued_tasks,
            expired_tasks=sweep_result.expired_tasks,
        )

    def _process_tasks(
        self,
        tasks,
        *,
        worker_id: str,
        execution_mode: str,
        targeted_tasks: int = 0,
        supplemental_tasks: int = 0,
        requeued_tasks: int = 0,
        expired_tasks: int = 0,
    ) -> PredictiveWarmProcessResult:
        if not tasks:
            return self._idle_result(
                worker_id=worker_id,
                execution_mode=execution_mode,
                targeted_tasks=targeted_tasks,
                supplemental_tasks=supplemental_tasks,
                requeued_tasks=requeued_tasks,
                expired_tasks=expired_tasks,
            )

        completed = 0
        failed = 0
        retried = 0
        deferred = 0
        dropped = 0
        skipped = 0
        cache_hits = 0
        cache_misses = 0
        generation_ids: list[str] = []
        claim_details = [self._claim_detail(task) for task in tasks]
        stale_recovered_tasks = sum(1 for task in tasks if task.stale_recovered)

        for task in tasks:
            profile = self.content_warmer.profile_store.get(task.student_id)
            if profile is None:
                self.queue_store.mark_failed(
                    task_id=task.task_id, error="Learner profile not found."
                )
                failed += 1
                continue
            try:
                result = self.content_warmer.warm([task.request])
            except Exception as exc:  # pragma: no cover - defensive fallback around provider/runtime failures
                if (
                    self.queue_store.defer_retry(task_id=task.task_id, error=str(exc))
                    is not None
                ):
                    retried += 1
                    deferred += 1
                else:
                    failed += 1
                continue
            if result.total_requests <= 0:
                self.queue_store.mark_failed(
                    task_id=task.task_id, error="Predictive warm task was skipped."
                )
                dropped += 1
                skipped += 1
                continue
            self.queue_store.mark_completed(task_id=task.task_id)
            completed += 1
            cache_hits += result.cache_hits
            cache_misses += result.cache_misses
            generation_ids.extend(result.generation_ids)

        queue_health = self._queue_health()
        return PredictiveWarmProcessResult(
            attempted_tasks=len(tasks),
            claimed_tasks=len(tasks),
            worker_id=worker_id,
            execution_mode=execution_mode,
            targeted_tasks=max(0, targeted_tasks),
            autonomous_tasks=max(0, len(tasks) - targeted_tasks),
            supplemental_tasks=max(0, supplemental_tasks),
            stale_recovered_tasks=stale_recovered_tasks,
            completed_tasks=completed,
            failed_tasks=failed,
            retried_tasks=retried,
            requeued_tasks=requeued_tasks,
            expired_tasks=expired_tasks,
            deferred_tasks=deferred,
            dropped_tasks=dropped,
            skipped_tasks=skipped,
            pending_tasks=queue_health["pending_tasks"],
            eligible_tasks=queue_health["eligible_tasks"],
            blocked_tasks=queue_health["blocked_tasks"],
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            generation_ids=generation_ids,
            claim_details=claim_details,
        )

    def _idle_result(
        self,
        *,
        worker_id: str,
        execution_mode: str,
        targeted_tasks: int = 0,
        supplemental_tasks: int = 0,
        requeued_tasks: int = 0,
        expired_tasks: int = 0,
    ) -> PredictiveWarmProcessResult:
        queue_health = self._queue_health()
        return PredictiveWarmProcessResult(
            worker_id=worker_id,
            execution_mode=execution_mode,
            targeted_tasks=max(0, targeted_tasks),
            autonomous_tasks=0,
            supplemental_tasks=max(0, supplemental_tasks),
            requeued_tasks=requeued_tasks,
            expired_tasks=expired_tasks,
            pending_tasks=queue_health["pending_tasks"],
            eligible_tasks=queue_health["eligible_tasks"],
            blocked_tasks=queue_health["blocked_tasks"],
        )

    def _queue_health(self) -> dict[str, int]:
        stats = self.queue_store.stats()
        return {
            "pending_tasks": self._backlog_count_from_stats(stats=stats),
            "eligible_tasks": int(stats.get("eligible_now", 0) or 0),
            "blocked_tasks": int(stats.get("blocked_deferred", 0) or 0),
        }

    def _backlog_count(self) -> int:
        stats = self.queue_store.stats()
        return self._backlog_count_from_stats(stats=stats)

    def _backlog_count_from_stats(self, *, stats: dict[str, int | None]) -> int:
        return int(stats.get("pending", 0) or 0) + int(stats.get("deferred", 0) or 0)

    def _claim_detail(self, task) -> PredictiveWarmClaimDetail:
        wait_seconds = max(
            0, int((datetime.now(timezone.utc) - task.created_at).total_seconds())
        )
        return PredictiveWarmClaimDetail(
            task_id=task.task_id,
            requested_content_type=(
                task.request.requested_content_type.value
                if task.request.requested_content_type is not None
                else None
            ),
            priority_class=task.priority_class,
            claim_owner=task.claim_owner,
            claim_mode=task.claim_mode,
            claim_reason=task.claim_reason,
            source_generation_id=task.request.source_generation_id,
            stale_recovered=task.stale_recovered,
            wait_seconds=wait_seconds,
        )
