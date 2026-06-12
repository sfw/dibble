from __future__ import annotations

from uuid import UUID, uuid4

from dibble.models.curriculum import KnowledgeComponent
from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
)
from dibble.models.profile import KnowledgeState, LearnerProfile
from dibble.models.telemetry import AuditEvent
from dibble.services.baseline_policy import (
    BASELINE_DECISION_EVENT_TYPE,
    BaselinePolicyService,
    BaselineShadowedProgressionOwnership,
    BaselineShadowedRouter,
)
from dibble.services.progression_ownership import ProgressionOwnershipDecision


class StubAuditStore:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(
        self,
        *,
        event_type: str,
        status: str,
        student_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            status=status,
            student_id=UUID(student_id) if student_id else None,
            payload=payload or {},
        )
        self.events.append(event)
        return event

    def list(self, *, limit: int = 50) -> list[AuditEvent]:
        return list(reversed(self.events))[:limit]


class FailingAuditStore(StubAuditStore):
    def append(self, **kwargs: object) -> AuditEvent:  # type: ignore[override]
        raise RuntimeError("audit store unavailable")


class StubKnowledgeComponentStore:
    def __init__(self, components: list[KnowledgeComponent]) -> None:
        self._components = {component.kc_id: component for component in components}

    def get(self, kc_id: str) -> KnowledgeComponent | None:
        return self._components.get(kc_id)


class StubProfileStore:
    def __init__(self, profile: LearnerProfile) -> None:
        self._profile = profile

    def get(self, student_id: UUID) -> LearnerProfile | None:
        if student_id == self._profile.student_id:
            return self._profile
        return None


def _component(
    kc_id: str, prerequisites: list[str] | None = None
) -> KnowledgeComponent:
    return KnowledgeComponent(
        kc_id=kc_id,
        name=f"KC {kc_id}",
        outcome_id="lo-1",
        grade_level="5",
        subject="math",
        prerequisite_kc_ids=prerequisites or [],
    )


def _profile(student_id: UUID, kc_mastery: dict[str, float]) -> LearnerProfile:
    return LearnerProfile(
        student_id=student_id,
        grade_level="5",
        knowledge_state=KnowledgeState(kc_mastery=kc_mastery),
    )


def _request(student_id: UUID, target_kc_ids: list[str]) -> GenerationRequest:
    return GenerationRequest(student_id=student_id, target_kc_ids=target_kc_ids)


def _route_decision(
    intervention: InterventionType = InterventionType.targeted_practice,
    scaffolding: str = "medium",
) -> AdaptiveRouteDecision:
    return AdaptiveRouteDecision(
        intervention_type=intervention,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level=scaffolding,
        reasons=["production decision"],
    )


def test_baseline_route_uses_fixed_thresholds() -> None:
    student_id = uuid4()
    service = BaselinePolicyService(audit_store=StubAuditStore())
    weak = _profile(student_id, {"kc-1": 0.2})
    middle = _profile(student_id, {"kc-1": 0.6})
    strong = _profile(student_id, {"kc-1": 0.9})
    request = _request(student_id, ["kc-1"])

    assert service.baseline_route(weak, request)["intervention_type"] == "reteach"
    assert service.baseline_route(weak, request)["scaffolding_level"] == "high"
    assert (
        service.baseline_route(middle, request)["intervention_type"]
        == "targeted_practice"
    )
    assert service.baseline_route(strong, request)["intervention_type"] == "stretch"
    assert service.baseline_route(strong, request)["scaffolding_level"] == "low"


def test_record_route_decision_emits_agreed_event() -> None:
    student_id = uuid4()
    audit_store = StubAuditStore()
    service = BaselinePolicyService(audit_store=audit_store)
    profile = _profile(student_id, {"kc-1": 0.6})

    service.record_route_decision(
        profile=profile,
        request=_request(student_id, ["kc-1"]),
        production=_route_decision(InterventionType.targeted_practice, "medium"),
    )

    assert len(audit_store.events) == 1
    event = audit_store.events[0]
    assert event.event_type == BASELINE_DECISION_EVENT_TYPE
    assert event.status == "agreed"
    assert event.payload["decision_point"] == "router.route"
    assert event.payload["agreed"] is True
    assert isinstance(event.payload["inputs_digest"], str)


def test_record_route_decision_emits_diverged_event() -> None:
    student_id = uuid4()
    audit_store = StubAuditStore()
    service = BaselinePolicyService(audit_store=audit_store)
    profile = _profile(student_id, {"kc-1": 0.6})

    service.record_route_decision(
        profile=profile,
        request=_request(student_id, ["kc-1"]),
        production=_route_decision(InterventionType.reteach, "high"),
    )

    event = audit_store.events[0]
    assert event.status == "diverged"
    assert event.payload["production_decision"]["intervention_type"] == "reteach"
    assert (
        event.payload["baseline_decision"]["intervention_type"] == "targeted_practice"
    )


def test_baseline_progression_steps_back_on_unmet_prerequisite() -> None:
    student_id = uuid4()
    profile = _profile(student_id, {"kc-prereq": 0.4, "kc-target": 0.6})
    service = BaselinePolicyService(
        audit_store=StubAuditStore(),
        knowledge_component_store=StubKnowledgeComponentStore(
            [_component("kc-target", ["kc-prereq"]), _component("kc-prereq")]
        ),
        profile_store=StubProfileStore(profile),
    )

    decision = service.baseline_progression(
        student_id=student_id, request=_request(student_id, ["kc-target"])
    )

    assert decision["action"] == "rebuild_prerequisite_first"
    assert decision["applied_target_kc_ids"] == ["kc-prereq"]


def test_baseline_progression_stays_when_prerequisites_met() -> None:
    student_id = uuid4()
    profile = _profile(student_id, {"kc-prereq": 0.95})
    service = BaselinePolicyService(
        audit_store=StubAuditStore(),
        knowledge_component_store=StubKnowledgeComponentStore(
            [_component("kc-target", ["kc-prereq"]), _component("kc-prereq")]
        ),
        profile_store=StubProfileStore(profile),
    )

    decision = service.baseline_progression(
        student_id=student_id, request=_request(student_id, ["kc-target"])
    )

    assert decision["action"] == "stay_on_requested_target"
    assert decision["applied_target_kc_ids"] == ["kc-target"]


def test_record_progression_decision_skips_empty_targets() -> None:
    student_id = uuid4()
    audit_store = StubAuditStore()
    service = BaselinePolicyService(audit_store=audit_store)

    service.record_progression_decision(
        student_id=student_id,
        request=_request(student_id, []),
        production=ProgressionOwnershipDecision(request=_request(student_id, [])),
    )

    assert audit_store.events == []


def test_record_progression_decision_marks_divergence() -> None:
    student_id = uuid4()
    audit_store = StubAuditStore()
    profile = _profile(student_id, {"kc-prereq": 0.95})
    service = BaselinePolicyService(
        audit_store=audit_store,
        knowledge_component_store=StubKnowledgeComponentStore(
            [_component("kc-target", ["kc-prereq"])]
        ),
        profile_store=StubProfileStore(profile),
    )
    request = _request(student_id, ["kc-target"])
    production = ProgressionOwnershipDecision(
        request=request,
        action="hold_target",
        requested_target_kc_ids=["kc-target"],
        applied_target_kc_ids=["kc-target"],
    )

    service.record_progression_decision(
        student_id=student_id, request=request, production=production
    )

    event = audit_store.events[0]
    assert event.status == "diverged"
    assert event.payload["decision_point"] == "progression.resolve"
    assert event.payload["baseline_decision"]["action"] == "stay_on_requested_target"


def test_agreement_summary_aggregates_by_decision_point() -> None:
    student_id = uuid4()
    audit_store = StubAuditStore()
    service = BaselinePolicyService(audit_store=audit_store)
    profile = _profile(student_id, {"kc-1": 0.6})
    request = _request(student_id, ["kc-1"])

    service.record_route_decision(
        profile=profile,
        request=request,
        production=_route_decision(InterventionType.targeted_practice, "medium"),
    )
    service.record_route_decision(
        profile=profile,
        request=request,
        production=_route_decision(InterventionType.reteach, "high"),
    )

    summary = service.agreement_summary()

    assert summary.total_decisions == 2
    assert summary.agreed_decisions == 1
    assert summary.agreement_rate == 0.5
    assert summary.decision_points[0].decision_point == "router.route"
    assert summary.decision_points[0].agreement_rate == 0.5
    assert len(summary.divergences) == 1
    assert summary.divergences[0].production_decision["intervention_type"] == "reteach"


def test_agreement_summary_filters_by_student() -> None:
    student_id = uuid4()
    other_id = uuid4()
    audit_store = StubAuditStore()
    service = BaselinePolicyService(audit_store=audit_store)
    service.record_route_decision(
        profile=_profile(student_id, {"kc-1": 0.6}),
        request=_request(student_id, ["kc-1"]),
        production=_route_decision(InterventionType.targeted_practice, "medium"),
    )
    service.record_route_decision(
        profile=_profile(other_id, {"kc-1": 0.6}),
        request=_request(other_id, ["kc-1"]),
        production=_route_decision(InterventionType.targeted_practice, "medium"),
    )

    summary = service.agreement_summary(student_id=str(student_id))

    assert summary.total_decisions == 1


class StubRouter:
    def __init__(self, decision: AdaptiveRouteDecision) -> None:
        self.decision = decision
        self.extra_attribute = "inner-attribute"

    def route(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> AdaptiveRouteDecision:
        return self.decision


def test_shadowed_router_returns_production_decision_and_logs() -> None:
    student_id = uuid4()
    audit_store = StubAuditStore()
    production = _route_decision(InterventionType.targeted_practice, "medium")
    router = BaselineShadowedRouter(
        inner=StubRouter(production),
        baseline_policy=BaselinePolicyService(audit_store=audit_store),
    )

    decision = router.route(
        _profile(student_id, {"kc-1": 0.6}), _request(student_id, ["kc-1"])
    )

    assert decision is production
    assert len(audit_store.events) == 1
    assert router.extra_attribute == "inner-attribute"


def test_shadowed_router_swallows_logging_failures() -> None:
    student_id = uuid4()
    production = _route_decision()
    router = BaselineShadowedRouter(
        inner=StubRouter(production),
        baseline_policy=BaselinePolicyService(audit_store=FailingAuditStore()),
    )

    decision = router.route(
        _profile(student_id, {"kc-1": 0.6}), _request(student_id, ["kc-1"])
    )

    assert decision is production


class StubProgressionService:
    def __init__(self, decision: ProgressionOwnershipDecision) -> None:
        self.decision = decision
        self.kc_sequence_planner = "planner-sentinel"

    def resolve_request(
        self, *, student_id: UUID, request: GenerationRequest
    ) -> ProgressionOwnershipDecision:
        return self.decision


def test_shadowed_progression_returns_production_decision_and_logs() -> None:
    student_id = uuid4()
    audit_store = StubAuditStore()
    request = _request(student_id, ["kc-target"])
    production = ProgressionOwnershipDecision(
        request=request,
        action="stay_on_requested_target",
        requested_target_kc_ids=["kc-target"],
        applied_target_kc_ids=["kc-target"],
    )
    wrapper = BaselineShadowedProgressionOwnership(
        inner=StubProgressionService(production),
        baseline_policy=BaselinePolicyService(audit_store=audit_store),
    )

    decision = wrapper.resolve_request(student_id=student_id, request=request)

    assert decision is production
    assert len(audit_store.events) == 1
    assert audit_store.events[0].status == "agreed"
    assert wrapper.kc_sequence_planner == "planner-sentinel"


def test_shadowed_progression_swallows_logging_failures() -> None:
    student_id = uuid4()
    request = _request(student_id, ["kc-target"])
    production = ProgressionOwnershipDecision(request=request)
    wrapper = BaselineShadowedProgressionOwnership(
        inner=StubProgressionService(production),
        baseline_policy=BaselinePolicyService(audit_store=FailingAuditStore()),
    )

    decision = wrapper.resolve_request(student_id=student_id, request=request)

    assert decision is production
