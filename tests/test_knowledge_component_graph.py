from dibble.models.curriculum import KnowledgeComponent
from dibble.services.knowledge_component_graph import KnowledgeComponentGraph


def test_knowledge_component_graph_tracks_multi_hop_prerequisites_and_dependents():
    graph = KnowledgeComponentGraph(
        [
            _build_component("KC-1", parent_lo_id="LO-1", difficulty=0.35),
            _build_component("KC-2", parent_lo_id="LO-1", prerequisite_kc_ids=["KC-1"], difficulty=0.45),
            _build_component("KC-3", parent_lo_id="LO-2", prerequisite_kc_ids=["KC-2"], difficulty=0.58),
        ]
    )

    prerequisites = graph.prerequisites_for("KC-3")
    dependents = graph.dependents_for("KC-1")

    assert [relation.component.kc_id for relation in prerequisites] == ["KC-2", "KC-1"]
    assert prerequisites[0].depth == 1
    assert prerequisites[1].depth == 2
    assert prerequisites[0].path_weight > prerequisites[1].path_weight
    assert [relation.component.kc_id for relation in dependents] == ["KC-2", "KC-3"]
    assert dependents[0].depth == 1
    assert dependents[1].depth == 2


def test_knowledge_component_graph_estimates_missing_kc_mastery_from_lo_and_neighbors():
    graph = KnowledgeComponentGraph(
        [
            _build_component("KC-1", parent_lo_id="LO-1", difficulty=0.32),
            _build_component("KC-2", parent_lo_id="LO-1", prerequisite_kc_ids=["KC-1"], difficulty=0.55),
        ]
    )

    estimate = graph.estimate_kc_from_lo(
        component=graph.components_for_lo("LO-1")[1],
        lo_mastery=0.72,
        kc_mastery={"KC-1": 0.76},
    )

    assert 0.6 <= estimate <= 0.75


def test_knowledge_component_graph_surfaces_same_lo_bridge_candidates():
    graph = KnowledgeComponentGraph(
        [
            _build_component("KC-1", parent_lo_id="LO-1", difficulty=0.28),
            _build_component("KC-2", parent_lo_id="LO-2", prerequisite_kc_ids=["KC-1"], difficulty=0.48),
            _build_component("KC-3", parent_lo_id="LO-2", prerequisite_kc_ids=["KC-1"], difficulty=0.6),
            _build_component("KC-4", parent_lo_id="LO-2", prerequisite_kc_ids=["KC-5"], difficulty=0.92),
            _build_component("KC-5", parent_lo_id="LO-3", difficulty=0.42),
        ]
    )

    siblings = graph.sibling_relations_for("KC-3")
    bridges = graph.bridge_candidates_for("KC-3", anchor_kc_ids=["KC-1"])

    assert [relation.component.kc_id for relation in siblings] == ["KC-2", "KC-4"]
    assert [relation.component.kc_id for relation in bridges] == ["KC-2"]
    assert bridges[0].path_weight > siblings[0].path_weight


def _build_component(
    kc_id: str,
    *,
    parent_lo_id: str,
    prerequisite_kc_ids: list[str] | None = None,
    difficulty: float = 0.5,
) -> KnowledgeComponent:
    return KnowledgeComponent(
        kc_id=kc_id,
        name=kc_id,
        parent_lo_id=parent_lo_id,
        grade_level="5",
        subject="math",
        prerequisite_kc_ids=prerequisite_kc_ids or [],
        difficulty=difficulty,
        estimated_time_minutes=10,
        tags=[],
        common_misconceptions=[],
    )
