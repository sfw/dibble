from __future__ import annotations

from dataclasses import dataclass

from dibble.models.telemetry import AuditEvent
from dibble.services.protocols import AuditStore, GeneratedContentStore, PredictiveWarmTaskStore


@dataclass(slots=True)
class PredictiveContentInvalidator:
    generated_content_store: GeneratedContentStore
    audit_store: AuditStore
    predictive_warm_task_store: PredictiveWarmTaskStore | None = None

    def invalidate_from_trigger_event(self, trigger_event: AuditEvent) -> AuditEvent:
        expired_entries = self.generated_content_store.expire_predictive_content(
            student_id=str(trigger_event.student_id) if trigger_event.student_id is not None else None,
            learning_session_id=_string_or_none(trigger_event.payload.get("learning_session_id")),
            target_kc_ids=_string_list(trigger_event.payload.get("target_kc_ids")),
            target_lo_ids=_string_list(trigger_event.payload.get("target_lo_ids")),
        )
        canceled_queue_tasks = (
            self.predictive_warm_task_store.cancel_pending(
                student_id=str(trigger_event.student_id) if trigger_event.student_id is not None else None,
                learning_session_id=_string_or_none(trigger_event.payload.get("learning_session_id")),
                target_kc_ids=_string_list(trigger_event.payload.get("target_kc_ids")),
                target_lo_ids=_string_list(trigger_event.payload.get("target_lo_ids")),
            )
            if self.predictive_warm_task_store is not None
            else 0
        )
        return self.audit_store.append(
            event_type="content.cache.invalidate",
            status="success",
            student_id=str(trigger_event.student_id) if trigger_event.student_id is not None else None,
            payload={
                "trigger_event_id": trigger_event.event_id,
                "trigger_event_type": trigger_event.event_type,
                "learning_session_id": trigger_event.payload.get("learning_session_id"),
                "target_kc_ids": _string_list(trigger_event.payload.get("target_kc_ids")),
                "target_lo_ids": _string_list(trigger_event.payload.get("target_lo_ids")),
                "expired_entries": expired_entries,
                "canceled_queue_tasks": canceled_queue_tasks,
            },
        )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
