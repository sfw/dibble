from __future__ import annotations

from dibble.models.assessment import SocraticEvidenceStrength
from dibble.models.curriculum import KnowledgeComponent
from dibble.services.knowledge_state_migration import KnowledgeStateMigrator


class StubKnowledgeComponentStore:
    def __init__(self, components: list[KnowledgeComponent]) -> None:
        self._components = {component.kc_id: component for component in components}

    def list(self) -> list[KnowledgeComponent]:
        return list(self._components.values())

    def get(self, kc_id: str) -> KnowledgeComponent | None:
        return self._components.get(kc_id)

    def list_prerequisites(self, kc_id: str) -> list[KnowledgeComponent]:
        seen: set[str] = set()
        ordered: list[KnowledgeComponent] = []

        def visit(current_id: str) -> None:
            component = self.get(current_id)
            if component is None:
                return
            for prerequisite_id in component.prerequisite_kc_ids:
                if prerequisite_id in seen:
                    continue
                seen.add(prerequisite_id)
                visit(prerequisite_id)
                prerequisite = self.get(prerequisite_id)
                if prerequisite is not None:
                    ordered.append(prerequisite)

        visit(kc_id)
        return ordered


def test_knowledge_state_migrator_lifts_prerequisites_and_recomputes_lo_mastery():
    store = StubKnowledgeComponentStore(
        [
            _build_component("KC-1", parent_lo_id="LO-1"),
            _build_component("KC-2", parent_lo_id="LO-1", prerequisite_kc_ids=["KC-1"]),
        ]
    )
    migrator = KnowledgeStateMigrator(knowledge_component_store=store)
    kc_mastery = {"KC-1": 0.45, "KC-2": 0.88}
    lo_mastery = {"LO-1": 0.66}

    result = migrator.migrate(
        kc_mastery=kc_mastery,
        lo_mastery=lo_mastery,
        direct_kc_updates={"KC-2": 0.88},
        direct_lo_updates={},
        evidence_strength=SocraticEvidenceStrength.demonstrated,
    )

    assert result.kc_mastery_updates["KC-1"] > 0.45
    assert result.lo_mastery_updates["LO-1"] == round((kc_mastery["KC-1"] + kc_mastery["KC-2"]) / 2, 2)


def test_knowledge_state_migrator_dampens_dependents_after_weak_evidence():
    store = StubKnowledgeComponentStore(
        [
            _build_component("KC-1", parent_lo_id="LO-1"),
            _build_component("KC-2", parent_lo_id="LO-1", prerequisite_kc_ids=["KC-1"]),
            _build_component("KC-3", parent_lo_id="LO-2", prerequisite_kc_ids=["KC-2"]),
        ]
    )
    migrator = KnowledgeStateMigrator(knowledge_component_store=store)
    kc_mastery = {"KC-1": 0.62, "KC-2": 0.34, "KC-3": 0.82}
    lo_mastery = {"LO-1": 0.48, "LO-2": 0.82}

    result = migrator.migrate(
        kc_mastery=kc_mastery,
        lo_mastery=lo_mastery,
        direct_kc_updates={"KC-2": 0.34},
        direct_lo_updates={},
        evidence_strength=SocraticEvidenceStrength.insufficient,
    )

    assert result.kc_mastery_updates["KC-3"] < 0.82
    assert result.lo_mastery_updates["LO-2"] == kc_mastery["KC-3"]


def _build_component(
    kc_id: str,
    *,
    parent_lo_id: str,
    prerequisite_kc_ids: list[str] | None = None,
) -> KnowledgeComponent:
    return KnowledgeComponent(
        kc_id=kc_id,
        name=kc_id,
        parent_lo_id=parent_lo_id,
        grade_level="5",
        subject="math",
        prerequisite_kc_ids=prerequisite_kc_ids or [],
        difficulty=0.5,
        estimated_time_minutes=10,
        tags=[],
        common_misconceptions=[],
    )
