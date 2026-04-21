from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    CurriculumContentKey,
    CurriculumContentRequest,
    CurriculumLibraryEntry,
    CurriculumLibraryProvenance,
    DeliveryMode,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationRequest,
    GenerationResponse,
    GroundingReference,
    InterventionType,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.loader import build_modality_plugins
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.curriculum_content_library_store import (
    SQLiteCurriculumContentLibraryStore,
)
from dibble.services.harness.content_library import (
    LibraryFirstCurriculumContentLibrary,
    LocalStubCloudLibraryClient,
)
from dibble.services.harness.modality_routing import ModalityRoutingHarness
from dibble.services.modality_routing_prior_store import SQLiteModalityRoutingPriorStore
from dibble.services.outcome_driven_adaptation import OutcomeDrivenAdaptationService
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database
from tests.support import build_profile


class _StubRouter:
    def route(self, profile, request):
        return AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["test"],
        )


def _generated_content(
    *,
    generation_id: str,
    route: AdaptiveRouteDecision,
    created_at: datetime,
    outcome_score: float = 0.5,
) -> GeneratedContent:
    return GeneratedContent(
        generation_id=generation_id,
        student_id=uuid4(),
        content_type="micro_explanation",
        request_context={},
        response=GenerationResponse(
            student_id=uuid4(),
            generated_at=created_at,
            route=route,
            blocks=[GeneratedBlock(kind="summary", title="Focus", body="Fractions")],
            curriculum_context=["Fractions"],
            safety_notes=[],
        ),
        quality=GenerationMetadata(validation_passed=True, quality_score=0.84),
        created_at=created_at,
    )


def test_outcome_history_shifts_modality_routing_toward_successful_plugin(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    audit_store = SQLiteAuditStore(conn)
    prior_store = SQLiteModalityRoutingPriorStore(conn)
    library_store = SQLiteCurriculumContentLibraryStore(conn)
    adaptation_service = OutcomeDrivenAdaptationService(
        audit_store=audit_store,
        prior_store=prior_store,
        curriculum_content_library_store=library_store,
    )
    harness = ModalityRoutingHarness(
        router=_StubRouter(),
        modality_plugins=build_modality_plugins(),
        prior_store=prior_store,
        audit_store=audit_store,
    )
    student_id = uuid4()
    profile = LearnerProfile.model_validate(
        build_profile(student_id, frustration="low", total_load=0.2)
    )
    request = GenerationRequest(
        student_id=student_id,
        target_kc_ids=["KC-1"],
        intent=ContentIntent.explanation,
        requested_content_type=RequestedContentType.micro_explanation,
        curriculum_context=["Equivalent fractions"],
    )
    route = _StubRouter().route(profile, request)
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(student_id),
        payload={
            "generation_id": "gen-1",
            "intent": request.intent.value,
            "content_type": request.requested_content_type.value,
            "target_kc_ids": request.target_kc_ids,
            "target_lo_ids": request.target_lo_ids,
            "modality_plugin_id": "narrative",
            "selected_modalities": ["narrative", "text"],
            "routing_context_key": harness.context_key_for(request=request, route=route),
        },
    )
    summary_event = audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=str(student_id),
        payload={
            "source_generation_event_id": generation_event.event_id,
            "generation_id": "gen-1",
            "run_summary_score": 0.88,
            "downstream_observation_score": 0.81,
            "downstream_assessment_score": 0.84,
        },
    )

    adaptation_service.record_from_summary_events(summary_events=[summary_event])
    inspection = harness.inspect(profile=profile, request=request, route=route)

    assert inspection.selected_plugin_id == "narrative"
    assert not inspection.weak_evidence_fallback_applied
    assert any(
        prior.prior_key == "narrative" and prior.evidence_count == 1
        for prior in inspection.priors
    )
    assert any(
        component.label == "outcome_prior" and component.value > 0
        for score in inspection.candidate_scores
        if score.plugin_id == "narrative"
        for component in score.score_components
    )


def test_library_ranking_prefers_stronger_outcome_history_over_newer_candidate(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    store = SQLiteCurriculumContentLibraryStore(conn)
    library = LibraryFirstCurriculumContentLibrary(
        local_client=LocalStubCloudLibraryClient(store)
    )
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.explanation,
        content_type=RequestedContentType.micro_explanation,
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    stronger_key = CurriculumContentKey(
        request=request,
        route=route,
        grounding=[
            GroundingReference(
                outcome_id="CURR-1",
                title="Equivalent fractions",
                grade_level="5",
                score=0.92,
            )
        ],
    )
    newer_key = CurriculumContentKey(
        request=request,
        route=route,
        grounding=[
            GroundingReference(
                outcome_id="CURR-2",
                title="Equivalent fractions alt",
                grade_level="5",
                score=0.88,
            )
        ],
    )
    older_created_at = datetime.now(timezone.utc) - timedelta(days=7)
    newer_created_at = datetime.now(timezone.utc)
    library.upsert_entry(
        entry=CurriculumLibraryEntry(
            content_key=stronger_key,
            content=_generated_content(
                generation_id="gen-strong",
                route=route,
                created_at=older_created_at,
            ),
            provenance=CurriculumLibraryProvenance(
                source_generation_id="gen-strong",
                quality_score=0.84,
                validator_passed=True,
                modalities=["text"],
                outcome_sample_count=4,
                average_outcome_score=0.89,
                average_engagement_score=0.8,
                average_progress_score=0.83,
                historical_success_rate=0.75,
                last_outcome_at=newer_created_at,
            ),
        )
    )
    library.upsert_entry(
        entry=CurriculumLibraryEntry(
            content_key=newer_key,
            content=_generated_content(
                generation_id="gen-newer",
                route=route,
                created_at=newer_created_at,
            ),
            provenance=CurriculumLibraryProvenance(
                source_generation_id="gen-newer",
                quality_score=0.82,
                validator_passed=True,
                modalities=["text"],
                outcome_sample_count=0,
                average_outcome_score=0.5,
                historical_success_rate=0.0,
            ),
        )
    )

    selected = library.get_fresh_entry(key=newer_key)
    trace = library.inspect_selection(key=newer_key)

    assert selected is not None
    assert selected.source_generation_id == "gen-strong"
    assert trace.selected_cache_key == stronger_key.cache_key()
    stronger_ranking = next(
        candidate
        for candidate in trace.candidates
        if candidate.cache_key == stronger_key.cache_key()
    )
    assert stronger_ranking.selected is True
    assert any(
        component.label == "historical_outcome" and component.value > 0
        for component in stronger_ranking.score_components
    )


def test_library_outcome_contract_promotes_safe_artifact_metadata(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    store = SQLiteCurriculumContentLibraryStore(conn)
    request = CurriculumContentRequest(
        grade_level="5",
        intent=ContentIntent.remediation,
        content_type=RequestedContentType.remedial_micro_module,
        target_kc_ids=["KC-1"],
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    key = CurriculumContentKey(request=request, route=route)
    store.upsert_entry(
        entry=CurriculumLibraryEntry(
            content_key=key,
            content=_generated_content(
                generation_id="gen-safe-contract",
                route=route,
                created_at=datetime.now(timezone.utc),
            ),
        )
    )

    store.record_outcome(
        source_generation_id="gen-safe-contract",
        outcome_score=0.81,
        engagement_score=0.74,
        progress_score=0.78,
    )
    refreshed = store.get_fresh_entry(key=key)

    assert refreshed is not None
    assert refreshed.provenance is not None
    assert refreshed.provenance.artifact_outcome_summary is not None
    assert refreshed.provenance.artifact_outcome_summary.intent == "remediation"
    assert (
        refreshed.provenance.artifact_outcome_summary.content_type
        == "remedial_micro_module"
    )
    assert refreshed.provenance.artifact_outcome_summary.pattern_key is not None
    assert refreshed.provenance.artifact_outcome_summary.sample_count == 1
    assert refreshed.provenance.artifact_outcome_summary.average_outcome_score == 0.81
