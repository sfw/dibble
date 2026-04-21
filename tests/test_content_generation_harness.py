from __future__ import annotations

import sqlite3
from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    CurriculumContentRequest,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import ModalityCapabilityProfile, ModalityPlugins
from dibble.services.harness.content_generation import ContentGenerationHarness
from dibble.services.harness.facades import PreparedAuthoringRequest
from dibble.services.harness.modality_routing import ModalityDirective, ModalityRoutingPlan
from dibble.services.harness.policy import HarnessAuthoringPolicy
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.operational_trace_store import SQLiteOperationalTraceStore
from dibble.storage import OPERATIONAL_TRACE_TABLE_SQL
from tests.support import build_profile


class _NoopTextPlugin:
    plugin_id = "text"
    modality = "text"
    composition_mode = "single"
    capabilities = ModalityCapabilityProfile()

    def apply(self, *, request: CurriculumContentRequest, accessibility_requirements):
        return request


class _FailingDiagramPlugin:
    plugin_id = "diagram"
    modality = "diagram"
    composition_mode = "single"
    capabilities = ModalityCapabilityProfile()

    def apply(self, *, request: CurriculumContentRequest, accessibility_requirements):
        raise RuntimeError("diagram renderer unavailable")


class _RoutingHarness:
    def plan(self, *, profile, request):
        return ModalityRoutingPlan(
            route=AdaptiveRouteDecision(
                intervention_type=InterventionType.reteach,
                delivery_mode=DeliveryMode.generated,
                scaffolding_level="medium",
                reasons=["retry with visuals"],
            ),
            pedagogical_move="reteach",
            directive=ModalityDirective(
                modality="diagram",
                plugin_id="diagram",
                composition_mode="single",
                plugin_ids=("diagram",),
            ),
        )


class _AuthoringFacade:
    def prepare_request_for(self, *, profile, request, route):
        return PreparedAuthoringRequest(
            policy=HarnessAuthoringPolicy(
                content_type=RequestedContentType.worked_example,
                prompt_guidance="Keep the explanation calm and specific.",
                request_context={"learning_session_id": request.learning_session_id},
                generation_constraints={},
            ),
            curriculum_request=CurriculumContentRequest(
                grade_level=profile.grade_level or "5",
                intent=ContentIntent.explanation,
                content_type=RequestedContentType.worked_example,
                target_kc_ids=list(request.target_kc_ids),
            ),
        )


class _HarnessFacade:
    def __init__(self) -> None:
        self.authoring = _AuthoringFacade()


class _GenerationEngine:
    def __init__(self) -> None:
        self.harness = _HarnessFacade()


def test_content_generation_harness_falls_back_to_text_when_modality_plugin_fails():
    student_id = uuid4()
    profile = LearnerProfile.model_validate(build_profile(student_id))
    conn = sqlite3.connect(":memory:")
    conn.executescript(OPERATIONAL_TRACE_TABLE_SQL)
    observability = OperationalObservabilityService(
        trace_store=SQLiteOperationalTraceStore(conn)
    )
    harness = ContentGenerationHarness(
        generation_engine=_GenerationEngine(),
        modality_routing_harness=_RoutingHarness(),
        modality_plugins=ModalityPlugins(
            plugins={
                "text": _NoopTextPlugin(),
                "diagram": _FailingDiagramPlugin(),
            }
        ),
        operational_observability_service=observability,
    )

    prepared = harness.prepare_generation(
        profile=profile,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-123",
            target_kc_ids=["KC-1"],
            requested_content_type=RequestedContentType.worked_example,
        ),
    )

    assert prepared.routing_plan.directive.plugin_id == "text"
    assert prepared.authoring.policy.request_context["selected_modality"] == "text"
    traces = observability.list_traces(limit=5)
    assert traces[0].status == "degraded"
    assert traces[0].reason_code == "modality_plugin_failed"
    assert traces[0].fallback_kind == "text_modality_fallback"
