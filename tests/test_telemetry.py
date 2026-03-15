from uuid import uuid4

from dibble.models.generation import AdaptiveRouteDecision, DeliveryMode, GenerationRequest, InterventionType
from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.llm_client import LLMClientError
from dibble.services.llm_provider import LLMOrchestrationProvider
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.provider_health import SQLiteProviderHealthStore
from dibble.services.telemetry import TelemetryService
from dibble.storage import ensure_database
from tests.support import build_profile


class AlwaysFailsClient:
    def complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        raise LLMClientError("boom")

    def stream_complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        raise LLMClientError("boom")


class SucceedsClient:
    def complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        class Result:
            content = (
                '{"blocks":['
                '{"kind":"summary","title":"Backup","body":"Recovered output."},'
                '{"kind":"instruction","title":"Try it","body":"Use the backup provider."}'
                "]}"
            )

        return Result()

    def stream_complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        yield '{"block_index":0,"kind":"summary","title":"Backup","body_delta":"Recovered output.","done":true}\n'


def test_telemetry_snapshot_includes_provider_health(tmp_path):
    database_path = str(tmp_path / "provider-health.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    generated_content_store = SQLiteGeneratedContentStore(database_path)
    health_store = SQLiteProviderHealthStore(database_path)
    provider = LLMOrchestrationProvider(
        clients=[("primary", AlwaysFailsClient()), ("secondary", SucceedsClient())],
        health_store=health_store,
        circuit_breaker_threshold=1,
        circuit_breaker_cooldown_seconds=30.0,
        fallback_provider=None,
    )
    telemetry = TelemetryService(audit_store, generated_content_store, health_store)
    profile = LearnerProfile.model_validate(build_profile(uuid4()))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="remediation",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.step_back,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="high",
        reasons=["test"],
    )

    provider.generate(profile, request, route, ["Equivalent Fractions Foundations"])

    snapshot = telemetry.snapshot()

    assert snapshot.provider_failure_events >= 1
    assert snapshot.provider_circuit_open_events >= 1
    assert snapshot.provider_statuses[0].provider_name == "primary"


def test_telemetry_snapshot_includes_cache_metrics(tmp_path):
    database_path = str(tmp_path / "cache-metrics.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    generated_content_store = SQLiteGeneratedContentStore(database_path)
    telemetry = TelemetryService(audit_store, generated_content_store)

    audit_store.append(
        event_type="content.generate",
        status="success",
        payload={"cache_hit": True, "delivery_mode": "generated", "validation_issue_count": 0},
    )
    audit_store.append(
        event_type="content.warm",
        status="success",
        payload={"total_requests": 2, "cache_hits": 1, "cache_misses": 1},
    )

    snapshot = telemetry.snapshot()

    assert snapshot.cache_hit_generations == 1
    assert snapshot.warm_requests == 2
    assert snapshot.generated_content_entries == 0
