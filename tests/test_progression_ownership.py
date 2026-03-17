from __future__ import annotations

from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponent
from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerStrategySummary
from dibble.services.progression_ownership import ProgressionOwnershipService
from dibble.services.within_session_adaptation import WithinSessionAdaptationSummary


class StubKnowledgeComponentStore:
    def __init__(self) -> None:
        self.components = {
            "KC-1": KnowledgeComponent(
                kc_id="KC-1",
                name="Prerequisite fraction model reading",
                parent_lo_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=[],
                difficulty=0.3,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
            "KC-2": KnowledgeComponent(
                kc_id="KC-2",
                name="Bridge equivalent fractions",
                parent_lo_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
                difficulty=0.4,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
            "KC-3": KnowledgeComponent(
                kc_id="KC-3",
                name="Target equivalent fractions",
                parent_lo_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
                difficulty=0.5,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
        }

    def list(self):
        return list(self.components.values())

    def get(self, kc_id):
        return self.components.get(kc_id)


class StubStrategySignalService:
    def __init__(self, summary: LearnerStrategySummary) -> None:
        self.summary = summary

    def strategy_for(self, *, student_id, request):
        return self.summary


class StubWithinSessionAdaptationService:
    def __init__(self, summary: WithinSessionAdaptationSummary) -> None:
        self.summary = summary

    def adaptation_for(self, *, student_id, request):
        return self.summary


def test_progression_ownership_rebuilds_prerequisite_before_requested_target():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(
            LearnerStrategySummary(
                signal="support_intensive",
                source="strategy_profile",
                recovery_focus="prerequisite_rebuild",
                recommended_next_action="rebuild_prerequisite",
                rationale="Rebuild the prerequisite before returning to the target.",
            )
        ),
        within_session_adaptation_service=StubWithinSessionAdaptationService(WithinSessionAdaptationSummary()),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
            curriculum_context=["Equivalent fractions"],
        ),
    )

    assert decision.action == "rebuild_prerequisite_first"
    assert decision.source == "strategy_profile"
    assert decision.requested_target_kc_ids == ["KC-3"]
    assert decision.applied_target_kc_ids == ["KC-1"]
    assert decision.request.target_kc_ids == ["KC-1"]
    assert decision.request.curriculum_context[-2] == "Progression ownership: rebuild_prerequisite_first."


def test_progression_ownership_bridges_through_related_kc_during_bridge_phase():
    student_id = uuid4()
    service = ProgressionOwnershipService(
        knowledge_component_store=StubKnowledgeComponentStore(),
        strategy_signal_service=StubStrategySignalService(LearnerStrategySummary()),
        within_session_adaptation_service=StubWithinSessionAdaptationService(
            WithinSessionAdaptationSummary(
                signal="recovering",
                source="session_controller",
                phase="bridge",
                recovery_intent="bridge_target",
                sequence_action="hold_repair_target",
                rationale="Bridge through a nearby KC before the final return.",
            )
        ),
    )

    decision = service.resolve_request(
        student_id=student_id,
        request=GenerationRequest(
            student_id=student_id,
            learning_session_id="session-bridge",
            target_kc_ids=["KC-3"],
            target_lo_ids=["LO-1"],
        ),
    )

    assert decision.action == "bridge_to_related_kc"
    assert decision.source == "session_controller"
    assert decision.applied_target_kc_ids == ["KC-2"]
    assert decision.bridge_kc_ids == ["KC-2"]
    assert decision.request.target_kc_ids == ["KC-2"]
