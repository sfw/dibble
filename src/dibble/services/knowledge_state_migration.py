from __future__ import annotations

from dataclasses import dataclass

from dibble.models.assessment import SocraticEvidenceStrength
from dibble.models.curriculum import KnowledgeComponent
from dibble.services.protocols import KnowledgeComponentStore


def _clamp(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _blend(prior: float, observed: float, weight: float) -> float:
    return (prior * (1.0 - weight)) + (observed * weight)


@dataclass(frozen=True, slots=True)
class KnowledgeStateMigrationResult:
    kc_mastery_updates: dict[str, float]
    lo_mastery_updates: dict[str, float]


@dataclass(slots=True)
class KnowledgeStateMigrator:
    knowledge_component_store: KnowledgeComponentStore
    prerequisite_positive_weight: float = 0.28
    dependent_negative_weight: float = 0.24

    def migrate(
        self,
        *,
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
        direct_kc_updates: dict[str, float],
        direct_lo_updates: dict[str, float],
        evidence_strength: SocraticEvidenceStrength,
    ) -> KnowledgeStateMigrationResult:
        if not direct_kc_updates and not direct_lo_updates:
            return KnowledgeStateMigrationResult(kc_mastery_updates={}, lo_mastery_updates={})

        all_components = self.knowledge_component_store.list()
        component_by_id = {component.kc_id: component for component in all_components}
        propagated_kc_updates: dict[str, float] = {}

        for kc_id, updated_mastery in direct_kc_updates.items():
            component = component_by_id.get(kc_id)
            if component is None:
                continue
            propagated_kc_updates.update(
                self._propagate_to_prerequisites(
                    kc_mastery=kc_mastery,
                    component=component,
                    updated_mastery=updated_mastery,
                    evidence_strength=evidence_strength,
                )
            )
            propagated_kc_updates.update(
                self._propagate_to_dependents(
                    kc_mastery=kc_mastery,
                    all_components=all_components,
                    source_kc_id=kc_id,
                    updated_mastery=updated_mastery,
                    evidence_strength=evidence_strength,
                )
            )

        for propagated_kc_id, propagated_mastery in propagated_kc_updates.items():
            kc_mastery[propagated_kc_id] = propagated_mastery

        affected_lo_ids = {
            lo_id
            for lo_id in direct_lo_updates
            if lo_id is not None
        }
        affected_lo_ids.update(
            component.parent_lo_id
            for component in all_components
            if component.kc_id in {*direct_kc_updates.keys(), *propagated_kc_updates.keys()}
        )
        propagated_lo_updates = self._recompute_lo_mastery(
            kc_mastery=kc_mastery,
            lo_mastery=lo_mastery,
            all_components=all_components,
            affected_lo_ids=affected_lo_ids,
        )
        return KnowledgeStateMigrationResult(
            kc_mastery_updates=propagated_kc_updates,
            lo_mastery_updates=propagated_lo_updates,
        )

    def _propagate_to_prerequisites(
        self,
        *,
        kc_mastery: dict[str, float],
        component: KnowledgeComponent,
        updated_mastery: float,
        evidence_strength: SocraticEvidenceStrength,
    ) -> dict[str, float]:
        if evidence_strength != SocraticEvidenceStrength.demonstrated or updated_mastery < 0.7:
            return {}
        propagated: dict[str, float] = {}
        for prerequisite in self.knowledge_component_store.list_prerequisites(component.kc_id):
            prior = kc_mastery.get(prerequisite.kc_id, 0.5)
            target = min(1.0, updated_mastery + 0.05)
            if target <= prior:
                continue
            propagated[prerequisite.kc_id] = round(
                _clamp(_blend(prior, target, self.prerequisite_positive_weight)),
                2,
            )
        return propagated

    def _propagate_to_dependents(
        self,
        *,
        kc_mastery: dict[str, float],
        all_components: list[KnowledgeComponent],
        source_kc_id: str,
        updated_mastery: float,
        evidence_strength: SocraticEvidenceStrength,
    ) -> dict[str, float]:
        if evidence_strength not in {
            SocraticEvidenceStrength.insufficient,
            SocraticEvidenceStrength.emerging,
        }:
            return {}
        propagated: dict[str, float] = {}
        descendant_ids = self._descendant_kc_ids(all_components=all_components, source_kc_id=source_kc_id)
        target_ceiling = min(1.0, updated_mastery + 0.12)
        for descendant_id in descendant_ids:
            prior = kc_mastery.get(descendant_id)
            if prior is None or prior <= target_ceiling:
                continue
            propagated[descendant_id] = round(
                _clamp(_blend(prior, target_ceiling, self.dependent_negative_weight)),
                2,
            )
        return propagated

    def _descendant_kc_ids(self, *, all_components: list[KnowledgeComponent], source_kc_id: str) -> list[str]:
        dependent_ids_by_prerequisite: dict[str, list[str]] = {}
        for component in all_components:
            for prerequisite_kc_id in component.prerequisite_kc_ids:
                dependent_ids_by_prerequisite.setdefault(prerequisite_kc_id, []).append(component.kc_id)

        ordered: list[str] = []
        seen: set[str] = set()
        queue = list(dependent_ids_by_prerequisite.get(source_kc_id, []))
        while queue:
            current_id = queue.pop(0)
            if current_id in seen:
                continue
            seen.add(current_id)
            ordered.append(current_id)
            queue.extend(dependent_ids_by_prerequisite.get(current_id, []))
        return ordered

    def _recompute_lo_mastery(
        self,
        *,
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
        all_components: list[KnowledgeComponent],
        affected_lo_ids: set[str],
    ) -> dict[str, float]:
        propagated_lo_updates: dict[str, float] = {}
        components_by_lo_id: dict[str, list[KnowledgeComponent]] = {}
        for component in all_components:
            components_by_lo_id.setdefault(component.parent_lo_id, []).append(component)

        for lo_id in affected_lo_ids:
            components = components_by_lo_id.get(lo_id, [])
            values = [kc_mastery[component.kc_id] for component in components if component.kc_id in kc_mastery]
            if not values:
                continue
            updated_value = round(sum(values) / len(values), 2)
            lo_mastery[lo_id] = updated_value
            propagated_lo_updates[lo_id] = updated_value
        return propagated_lo_updates
