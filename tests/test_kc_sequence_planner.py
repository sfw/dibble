from dibble.models.profile import LearnerStrategySummary
from dibble.models.curriculum import KnowledgeComponent
from dibble.services.kc_sequence_planner import KcSequencePlanner


def test_kc_sequence_planner_rebuilds_prerequisite_when_strategy_requires_step_back():
    sequence = KcSequencePlanner().plan(
        strategy_summary=LearnerStrategySummary(
            signal="support_intensive",
            source="strategy_profile",
            recovery_focus="prerequisite_rebuild",
            recommended_next_action="rebuild_prerequisite",
            trajectory_state="relapsing",
        ),
        target_kc_ids=["KC-2"],
        prerequisite_kc_ids=["KC-1"],
        repair_target_kc_ids=["KC-1"],
    )

    assert sequence.action == "rebuild_prerequisite_first"
    assert sequence.primary_kc_id == "KC-1"
    assert sequence.ordered_kc_ids == ["KC-1", "KC-2"]


def test_kc_sequence_planner_attempts_transfer_when_strategy_is_independence_ready():
    sequence = KcSequencePlanner().plan(
        strategy_summary=LearnerStrategySummary(
            signal="independence_ready",
            source="strategy_profile",
            support_bias=1,
            trajectory_state="accelerating",
            recommended_next_action="check_transfer_readiness",
        ),
        target_kc_ids=["KC-2"],
    )

    assert sequence.action == "attempt_transfer"
    assert sequence.primary_kc_id == "KC-2"
    assert sequence.ordered_kc_ids == ["KC-2"]


def test_kc_sequence_planner_inserts_same_lo_bridge_before_target_return():
    planner = KcSequencePlanner(
        knowledge_component_store=_StubKnowledgeComponentStore(
            [
                _build_component("KC-1", parent_lo_id="LO-1", difficulty=0.3),
                _build_component(
                    "KC-2",
                    parent_lo_id="LO-2",
                    prerequisite_kc_ids=["KC-1"],
                    difficulty=0.46,
                ),
                _build_component(
                    "KC-3",
                    parent_lo_id="LO-2",
                    prerequisite_kc_ids=["KC-1"],
                    difficulty=0.62,
                ),
            ]
        )
    )

    sequence = planner.plan(
        strategy_summary=LearnerStrategySummary(
            signal="support_intensive",
            source="strategy_profile",
            recovery_focus="prerequisite_rebuild",
            recommended_next_action="rebuild_prerequisite",
            trajectory_state="relapsing",
        ),
        target_kc_ids=["KC-3"],
        prerequisite_kc_ids=["KC-1"],
        repair_target_kc_ids=["KC-1"],
    )

    assert sequence.action == "rebuild_prerequisite_first"
    assert sequence.ordered_kc_ids == ["KC-1", "KC-2", "KC-3"]
    assert sequence.bridge_kc_ids == ["KC-2"]
    assert sequence.deferred_kc_ids == ["KC-3"]
    assert "nearby bridge KC(s) KC-2" in (sequence.rationale or "")


def test_kc_sequence_planner_can_use_curated_taxonomy_neighbor_when_same_lo_bridge_is_absent():
    planner = KcSequencePlanner(
        knowledge_component_store=_StubKnowledgeComponentStore(
            [
                _build_component(
                    "KC-1",
                    parent_lo_id="LO-1",
                    concept_family="fraction-sense",
                    taxonomy_cluster_id="fractions-core",
                    difficulty=0.3,
                ),
                _build_component(
                    "KC-2",
                    parent_lo_id="LO-3",
                    prerequisite_kc_ids=["KC-1"],
                    concept_family="fraction-equivalence",
                    taxonomy_cluster_id="fractions-core",
                    nearby_kc_ids=["KC-3"],
                    difficulty=0.44,
                ),
                _build_component(
                    "KC-3",
                    parent_lo_id="LO-2",
                    prerequisite_kc_ids=["KC-1"],
                    concept_family="fraction-equivalence",
                    taxonomy_cluster_id="fractions-core",
                    difficulty=0.62,
                ),
            ]
        )
    )

    sequence = planner.plan(
        strategy_summary=LearnerStrategySummary(
            signal="support_intensive",
            source="strategy_profile",
            recovery_focus="prerequisite_rebuild",
            recommended_next_action="rebuild_prerequisite",
            trajectory_state="relapsing",
        ),
        target_kc_ids=["KC-3"],
        prerequisite_kc_ids=["KC-1"],
        repair_target_kc_ids=["KC-1"],
    )

    assert sequence.action == "rebuild_prerequisite_first"
    assert sequence.ordered_kc_ids == ["KC-1", "KC-2", "KC-3"]
    assert sequence.bridge_kc_ids == ["KC-2"]
    assert "nearby bridge KC(s) KC-2" in (sequence.rationale or "")


class _StubKnowledgeComponentStore:
    def __init__(self, components: list[KnowledgeComponent]) -> None:
        self._components = components

    def list(self) -> list[KnowledgeComponent]:
        return list(self._components)


def _build_component(
    kc_id: str,
    *,
    parent_lo_id: str,
    prerequisite_kc_ids: list[str] | None = None,
    difficulty: float = 0.5,
    taxonomy_cluster_id: str | None = None,
    concept_family: str | None = None,
    nearby_kc_ids: list[str] | None = None,
) -> KnowledgeComponent:
    return KnowledgeComponent(
        kc_id=kc_id,
        name=kc_id,
        parent_lo_id=parent_lo_id,
        grade_level="5",
        subject="math",
        taxonomy_cluster_id=taxonomy_cluster_id,
        concept_family=concept_family,
        prerequisite_kc_ids=prerequisite_kc_ids or [],
        nearby_kc_ids=nearby_kc_ids or [],
        difficulty=difficulty,
        estimated_time_minutes=10,
        tags=[],
        common_misconceptions=[],
    )
