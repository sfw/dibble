from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from dibble.models.rollout import EvaluationBucketSummary, EvaluationSummaryResponse
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class RolloutEvaluationService:
    audit_store: AuditStore
    max_events: int = 5000

    def summarize(self) -> EvaluationSummaryResponse:
        events = self.audit_store.list(limit=self.max_events)
        generation_events = {
            event.event_id: event
            for event in events
            if event.event_type == "content.generate"
        }
        bucket_rows: dict[str, dict[str, object]] = {}
        for summary_event in events:
            if summary_event.event_type != "learning.run.summary":
                continue
            generation_event_id = str(
                summary_event.payload.get("source_generation_event_id", "")
            )
            generation_event = generation_events.get(generation_event_id)
            if generation_event is None:
                continue
            bucket_id = str(
                generation_event.payload.get("rollout_evaluation_bucket_id")
                or "unbucketed"
            )
            bucket_label = str(
                generation_event.payload.get("rollout_evaluation_bucket_label")
                or bucket_id
            )
            dimensions = generation_event.payload.get("rollout_evaluation_dimensions") or {}
            if not isinstance(dimensions, dict):
                dimensions = {}
            row = bucket_rows.setdefault(
                bucket_id,
                {
                    "bucket_id": bucket_id,
                    "label": bucket_label,
                    "dimensions": {str(key): str(value) for key, value in dimensions.items()},
                    "sample_count": 0,
                    "learner_ids": set(),
                    "positive_count": 0,
                    "run_score_total": 0.0,
                    "observation_score_total": 0.0,
                    "assessment_score_total": 0.0,
                    "modality_counts": Counter(),
                },
            )
            row["sample_count"] += 1
            if summary_event.student_id is not None:
                row["learner_ids"].add(str(summary_event.student_id))
            run_score = _float_value(summary_event.payload.get("run_summary_score"), 0.0)
            row["run_score_total"] += run_score
            if run_score >= 0.75:
                row["positive_count"] += 1
            row["observation_score_total"] += _float_value(
                summary_event.payload.get("downstream_observation_score"),
                0.0,
            )
            row["assessment_score_total"] += _float_value(
                summary_event.payload.get("downstream_assessment_score"),
                0.0,
            )
            modality = str(generation_event.payload.get("modality_plugin_id") or "text")
            row["modality_counts"][modality] += 1
        buckets = [
            EvaluationBucketSummary(
                bucket_id=row["bucket_id"],
                label=row["label"],
                dimensions=row["dimensions"],
                sample_count=row["sample_count"],
                learner_count=len(row["learner_ids"]),
                positive_run_rate=_average(row["positive_count"], row["sample_count"]),
                average_run_outcome_score=_average(
                    row["run_score_total"], row["sample_count"]
                ),
                average_observation_score=_average(
                    row["observation_score_total"], row["sample_count"]
                ),
                average_assessment_score=_average(
                    row["assessment_score_total"], row["sample_count"]
                ),
                modality_counts=dict(sorted(row["modality_counts"].items())),
            )
            for row in sorted(bucket_rows.values(), key=lambda item: item["bucket_id"])
        ]
        return EvaluationSummaryResponse(
            total_samples=sum(bucket.sample_count for bucket in buckets),
            buckets=buckets,
        )


def _float_value(value: object, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _average(total: float, count: int) -> float:
    if count <= 0:
        return 0.0
    return round(total / count, 2)
