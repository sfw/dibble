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
from dibble.services.harness.content_library import (
    LibraryFirstCurriculumContentLibrary,
    LocalStubCloudLibraryClient,
)
from dibble.storage import CURRICULUM_CONTENT_LIBRARY_TABLE_SQL


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
