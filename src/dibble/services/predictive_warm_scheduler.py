from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import PredictiveWarmProcessResult
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
        if self.inline_process_limit <= 0 or not task_ids:
            return PredictiveWarmProcessResult(pending_tasks=self._backlog_count())
        sweep_result = self.queue_store.sweep()
        return self._process_tasks(
            self.queue_store.claim_tasks(task_ids=task_ids[: self.inline_process_limit]),
            requeued_tasks=sweep_result.requeued_tasks,
        )

    def process_pending(self, *, limit: int = 10) -> PredictiveWarmProcessResult:
        sweep_result = self.queue_store.sweep()
        return self._process_tasks(
            self.queue_store.claim_pending(limit=limit),
            requeued_tasks=sweep_result.requeued_tasks,
        )

    def _process_tasks(self, tasks, *, requeued_tasks: int = 0) -> PredictiveWarmProcessResult:
        if not tasks:
            return PredictiveWarmProcessResult(
                pending_tasks=self._backlog_count(),
                requeued_tasks=requeued_tasks,
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

        for task in tasks:
            profile = self.content_warmer.profile_store.get(task.student_id)
            if profile is None:
                self.queue_store.mark_failed(task_id=task.task_id, error="Learner profile not found.")
                failed += 1
                continue
            try:
                result = self.content_warmer.warm([task.request])
            except Exception as exc:  # pragma: no cover - defensive fallback around provider/runtime failures
                if self.queue_store.defer_retry(task_id=task.task_id, error=str(exc)) is not None:
                    retried += 1
                    deferred += 1
                else:
                    failed += 1
                continue
            if result.total_requests <= 0:
                self.queue_store.mark_failed(task_id=task.task_id, error="Predictive warm task was skipped.")
                dropped += 1
                skipped += 1
                continue
            self.queue_store.mark_completed(task_id=task.task_id)
            completed += 1
            cache_hits += result.cache_hits
            cache_misses += result.cache_misses
            generation_ids.extend(result.generation_ids)

        return PredictiveWarmProcessResult(
            attempted_tasks=len(tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            retried_tasks=retried,
            requeued_tasks=requeued_tasks,
            deferred_tasks=deferred,
            dropped_tasks=dropped,
            skipped_tasks=skipped,
            pending_tasks=self._backlog_count(),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            generation_ids=generation_ids,
        )

    def _backlog_count(self) -> int:
        stats = self.queue_store.stats()
        return stats.get("pending", 0) + stats.get("deferred", 0)
