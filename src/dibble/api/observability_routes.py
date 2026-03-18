from __future__ import annotations

from fastapi import APIRouter

from dibble.api.common import ApiContext
from dibble.models.telemetry import AuditEvent, TelemetrySnapshot


def build_observability_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.get(
        "/audit/events",
        response_model=list[AuditEvent],
        dependencies=context.deps("admin"),
    )
    def list_audit_events(limit: int = 50) -> list[AuditEvent]:
        safe_limit = max(1, min(limit, 200))
        return services.audit_store.list(limit=safe_limit)

    @router.get(
        "/observability/metrics",
        response_model=TelemetrySnapshot,
        dependencies=context.deps("admin"),
    )
    def get_observability_metrics() -> TelemetrySnapshot:
        return services.telemetry_service.snapshot()

    return router
