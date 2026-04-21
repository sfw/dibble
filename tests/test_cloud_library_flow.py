from __future__ import annotations

import sqlite3
from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    CurriculumContentKey,
    CurriculumContentRequest,
    CurriculumLibraryEntry,
    DeliveryMode,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationResponse,
    InterventionType,
)
from dibble.services.curriculum_content_library_store import (
    SQLiteCurriculumContentLibraryStore,
)
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.operational_trace_store import SQLiteOperationalTraceStore
from dibble.services.harness.content_library import (
    CloudLibraryTransportResponse,
    LibraryFirstCurriculumContentLibrary,
    LocalStubCloudLibraryClient,
    RemoteReadyCloudLibraryClient,
)
from dibble.storage import CURRICULUM_CONTENT_LIBRARY_TABLE_SQL, OPERATIONAL_TRACE_TABLE_SQL


def test_library_first_content_library_writes_only_verified_entries():
    conn = sqlite3.connect(":memory:")
    conn.executescript(CURRICULUM_CONTENT_LIBRARY_TABLE_SQL)
    library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(SQLiteCurriculumContentLibraryStore(conn))
    )
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-verified",
        student_id=uuid4(),
        content_type="micro_explanation",
        request_context={},
        response=GenerationResponse(
            student_id=uuid4(),
            route=route,
            blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
            curriculum_context=["Fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(validation_passed=True),
    )
    invalid = content.model_copy(
        update={
            "generation_id": "gen-invalid",
            "response": content.response.model_copy(update={"validation_issues": ["missing verifier"]}),
            "quality": content.quality.model_copy(update={"validation_passed": False}),
        }
    )

    stored = library.upsert(key=key, content=content)
    skipped = library.upsert(key=key.model_copy(), content=invalid)

    assert stored.generation_id == "gen-verified"
    assert skipped.generation_id == "gen-invalid"
    assert library.get_fresh_entry(key=key) is not None


def test_library_first_content_library_falls_back_to_local_when_remote_publish_fails():
    class _FailingRemoteClient:
        endpoint = "https://library.example.test"

        def lookup(self, *, key):
            return None

        def publish(self, *, entry):
            raise RuntimeError("remote publish unavailable")

    conn = sqlite3.connect(":memory:")
    conn.executescript(CURRICULUM_CONTENT_LIBRARY_TABLE_SQL)
    library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(SQLiteCurriculumContentLibraryStore(conn)),
        remote_client=_FailingRemoteClient(),
    )
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-verified",
        student_id=uuid4(),
        content_type="micro_explanation",
        request_context={},
        response=GenerationResponse(
            student_id=uuid4(),
            route=route,
            blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
            curriculum_context=["Fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(validation_passed=True),
    )

    stored = library.upsert(key=key, content=content)

    assert stored.generation_id == "gen-verified"
    entry = library.get_fresh_entry(key=key)
    assert entry is not None
    assert entry.storage_scope == "local_only"
    assert entry.provenance is not None
    assert entry.provenance.publish_status == "remote_publish_failed_local_only"
    assert entry.provenance.degraded_mode is True
    assert entry.provenance.remote_endpoint == "https://library.example.test"
    assert entry.provenance.degraded_reason == "remote publish unavailable"


def test_library_first_content_library_marks_remote_lookup_failure_on_local_fallback():
    class _FailingRemoteClient:
        endpoint = "https://library.example.test"

        def lookup(self, *, key):
            raise RuntimeError("remote lookup unavailable")

        def publish(self, *, entry):
            return None

    conn = sqlite3.connect(":memory:")
    conn.executescript(CURRICULUM_CONTENT_LIBRARY_TABLE_SQL)
    library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(SQLiteCurriculumContentLibraryStore(conn)),
        remote_client=_FailingRemoteClient(),
    )
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-verified",
        student_id=uuid4(),
        content_type="micro_explanation",
        request_context={},
        response=GenerationResponse(
            student_id=uuid4(),
            route=route,
            blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
            curriculum_context=["Fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(validation_passed=True),
    )
    library.local_client.publish(
        entry=CurriculumLibraryEntry(content_key=key, content=content)
    )

    entry = library.get_fresh_entry(key=key)

    assert entry is not None
    assert entry.provenance is not None
    assert entry.provenance.lookup_status == "remote_lookup_failed_local_fallback"
    assert entry.provenance.degraded_mode is True
    assert entry.provenance.degraded_reason == "remote lookup unavailable"
    assert entry.provenance.remote_endpoint == "https://library.example.test"


def test_library_first_content_library_records_operational_trace_for_remote_publish_failure():
    class _FailingRemoteClient:
        endpoint = "https://library.example.test"

        def lookup(self, *, key):
            return None

        def publish(self, *, entry):
            raise RuntimeError("remote publish unavailable")

    conn = sqlite3.connect(":memory:")
    conn.executescript(CURRICULUM_CONTENT_LIBRARY_TABLE_SQL)
    conn.executescript(OPERATIONAL_TRACE_TABLE_SQL)
    observability = OperationalObservabilityService(
        trace_store=SQLiteOperationalTraceStore(conn)
    )
    library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(SQLiteCurriculumContentLibraryStore(conn)),
        remote_client=_FailingRemoteClient(),
        observability_service=observability,
    )
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-verified",
        student_id=uuid4(),
        content_type="micro_explanation",
        request_context={},
        response=GenerationResponse(
            student_id=uuid4(),
            route=route,
            blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
            curriculum_context=["Fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(validation_passed=True),
    )

    library.upsert(key=key, content=content)

    traces = observability.list_traces(limit=5)
    assert traces[0].harness == "content_library"
    assert traces[0].status == "degraded"
    assert traces[0].reason_code == "remote_publish_failed_local_only"


def test_library_first_content_library_prefers_remote_hit_with_real_remote_adapter():
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route, grounding=[])

    class _Transport:
        def request(self, *, method, url, headers, payload, timeout_seconds):
            assert method == "POST"
            assert url.endswith("/lookup")
            assert payload["cache_key"] == key.cache_key()
            return CloudLibraryTransportResponse(
                status_code=200,
                payload={
                    "entry": CurriculumLibraryEntry(
                        content_key=key,
                        content=GeneratedContent(
                            generation_id="gen-remote",
                            student_id=uuid4(),
                            content_type="micro_explanation",
                            request_context={"selected_content_type": "micro_explanation"},
                            response=GenerationResponse(
                                student_id=uuid4(),
                                route=route,
                                blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
                                curriculum_context=["Fractions"],
                                safety_notes=[],
                            ),
                            quality=GenerationMetadata(validation_passed=True),
                        ),
                        storage_scope="shared_ready",
                    ).model_dump(mode="json")
                },
            )

    library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(
            SQLiteCurriculumContentLibraryStore(sqlite3.connect(":memory:"))
        ),
        remote_client=RemoteReadyCloudLibraryClient(
            endpoint="https://library.example.test",
            enabled=True,
            transport=_Transport(),
        ),
    )

    entry = library.get_fresh_entry(key=key)

    assert entry is not None
    assert entry.provenance is not None
    assert entry.provenance.lookup_status == "remote_hit"
    assert entry.provenance.publish_status == "remote_available"
    assert entry.provenance.remote_endpoint == "https://library.example.test"


def test_real_remote_client_keeps_lookup_miss_local_fallback_path():
    conn = sqlite3.connect(":memory:")
    conn.executescript(CURRICULUM_CONTENT_LIBRARY_TABLE_SQL)
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-local",
        student_id=uuid4(),
        content_type="micro_explanation",
        request_context={},
        response=GenerationResponse(
            student_id=uuid4(),
            route=route,
            blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
            curriculum_context=["Fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(validation_passed=True),
    )

    class _Transport:
        def request(self, *, method, url, headers, payload, timeout_seconds):
            return CloudLibraryTransportResponse(status_code=404, payload={})

    library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(SQLiteCurriculumContentLibraryStore(conn)),
        remote_client=RemoteReadyCloudLibraryClient(
            endpoint="https://library.example.test",
            enabled=True,
            transport=_Transport(),
        ),
    )
    library.local_client.publish(
        entry=CurriculumLibraryEntry(content_key=key, content=content)
    )

    entry = library.get_fresh_entry(key=key)

    assert entry is not None
    assert entry.provenance is not None
    assert entry.provenance.lookup_status == "remote_miss_local_fallback"
    assert entry.provenance.degraded_mode is False


def test_real_remote_client_strips_learner_fields_from_publish_payload():
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type="micro_explanation",
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route, grounding=[])
    learner_id = uuid4()
    response_student_id = uuid4()
    captured_payload = {}

    class _Transport:
        def request(self, *, method, url, headers, payload, timeout_seconds):
            captured_payload.update(payload)
            return CloudLibraryTransportResponse(status_code=201, payload=payload)

    client = RemoteReadyCloudLibraryClient(
        endpoint="https://library.example.test",
        enabled=True,
        transport=_Transport(),
    )
    entry = CurriculumLibraryEntry(
        content_key=key,
        content=GeneratedContent(
            generation_id="gen-privacy",
            student_id=learner_id,
            content_type="micro_explanation",
            request_context={
                "selected_content_type": "micro_explanation",
                "curriculum_cache_key": key.cache_key(),
                "student_id": str(learner_id),
                "learner_name": "Avery",
            },
            response=GenerationResponse(
                student_id=response_student_id,
                route=route,
                blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
                curriculum_context=["Fractions"],
                safety_notes=[],
            ),
            quality=GenerationMetadata(validation_passed=True),
        ),
    )

    client.publish(entry=entry)

    outbound = captured_payload["entry"]["content"]
    assert outbound["student_id"] == "00000000-0000-0000-0000-000000000000"
    assert outbound["response"]["student_id"] == "00000000-0000-0000-0000-000000000000"
    assert "learner_name" not in outbound["request_context"]
    assert "student_id" not in outbound["request_context"]
