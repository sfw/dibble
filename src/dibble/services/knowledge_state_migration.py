from __future__ import annotations

from dataclasses import dataclass

from dibble.models.assessment import SocraticEvidenceStrength
from dibble.models.curriculum import KnowledgeComponent
from dibble.services.knowledge_component_graph import (
    KnowledgeComponentGraph,
    KnowledgeComponentRelation,
)
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
    prerequisite_depth_decay: float = 0.84
    dependent_depth_decay: float = 0.8
    lo_to_kc_backfill_weight: float = 0.32

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
            return KnowledgeStateMigrationResult(
                kc_mastery_updates={}, lo_mastery_updates={}
            )

        all_components = self.knowledge_component_store.list()
        graph = KnowledgeComponentGraph(
            all_components,
            prerequisite_depth_decay=self.prerequisite_depth_decay,
            dependent_depth_decay=self.dependent_depth_decay,
        )
        component_by_id = {component.kc_id: component for component in all_components}
        propagated_kc_updates: dict[str, float] = {}
        affected_lo_ids = {lo_id for lo_id in direct_lo_updates if lo_id is not None}
        affected_lo_ids.update(
            component.parent_lo_id
            for kc_id, component in component_by_id.items()
            if kc_id in direct_kc_updates
        )

        propagated_kc_updates.update(
            self._backfill_kc_mastery_from_los(
                kc_mastery=kc_mastery,
                lo_mastery=lo_mastery,
                graph=graph,
                affected_lo_ids=affected_lo_ids,
                direct_kc_updates=direct_kc_updates,
            )
        )

        for kc_id, updated_mastery in direct_kc_updates.items():
            component = component_by_id.get(kc_id)
            if component is None:
                continue
            propagated_kc_updates.update(
                self._propagate_to_prerequisites(
                    kc_mastery=kc_mastery,
                    graph=graph,
                    component=component,
                    updated_mastery=updated_mastery,
                    evidence_strength=evidence_strength,
                )
            )
            propagated_kc_updates.update(
                self._propagate_to_dependents(
                    kc_mastery=kc_mastery,
                    graph=graph,
                    source_kc_id=kc_id,
                    updated_mastery=updated_mastery,
                    evidence_strength=evidence_strength,
                )
            )

        for propagated_kc_id, propagated_mastery in propagated_kc_updates.items():
            kc_mastery[propagated_kc_id] = propagated_mastery

        affected_lo_ids = {lo_id for lo_id in direct_lo_updates if lo_id is not None}
        affected_lo_ids.update(
            component.parent_lo_id
            for component in all_components
            if component.kc_id
            in {*direct_kc_updates.keys(), *propagated_kc_updates.keys()}
        )
        propagated_lo_updates = self._recompute_lo_mastery(
            kc_mastery=kc_mastery,
            lo_mastery=lo_mastery,
            graph=graph,
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
        graph: KnowledgeComponentGraph,
        component: KnowledgeComponent,
        updated_mastery: float,
        evidence_strength: SocraticEvidenceStrength,
    ) -> dict[str, float]:
        if (
            evidence_strength != SocraticEvidenceStrength.demonstrated
            or updated_mastery < 0.7
        ):
            return {}
        propagated: dict[str, float] = {}
        for relation in graph.prerequisites_for(component.kc_id):
            prerequisite = relation.component
            prior = kc_mastery.get(prerequisite.kc_id, 0.5)
            target = min(1.0, updated_mastery + 0.05)
            if target <= prior:
                continue
            weight = self._relation_weight(
                base=self.prerequisite_positive_weight,
                relation=relation,
                polarity="positive",
            )
            propagated[prerequisite.kc_id] = round(
                _clamp(_blend(prior, target, weight)),
                2,
            )
        return propagated

    def _propagate_to_dependents(
        self,
        *,
        kc_mastery: dict[str, float],
        graph: KnowledgeComponentGraph,
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
        target_ceiling = min(1.0, updated_mastery + 0.12)
        for relation in graph.dependents_for(source_kc_id):
            descendant_id = relation.component.kc_id
            prior = kc_mastery.get(descendant_id)
            if prior is None or prior <= target_ceiling:
                continue
            weight = self._relation_weight(
                base=self.dependent_negative_weight,
                relation=relation,
                polarity="negative",
            )
            propagated[descendant_id] = round(
                _clamp(_blend(prior, target_ceiling, weight)),
                2,
            )
        return propagated

    def _backfill_kc_mastery_from_los(
        self,
        *,
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
        graph: KnowledgeComponentGraph,
        affected_lo_ids: set[str],
        direct_kc_updates: dict[str, float],
    ) -> dict[str, float]:
        backfilled: dict[str, float] = {}
        for lo_id in affected_lo_ids:
            lo_value = lo_mastery.get(lo_id)
            if lo_value is None:
                continue
            for component in graph.components_for_lo(lo_id):
                if component.kc_id in direct_kc_updates:
                    continue
                prior = kc_mastery.get(component.kc_id)
                estimated = graph.estimate_kc_from_lo(
                    component=component,
                    lo_mastery=lo_value,
                    kc_mastery=kc_mastery,
                )
                if prior is None:
                    rounded = estimated
                else:
                    rounded = round(
                        _clamp(_blend(prior, estimated, self.lo_to_kc_backfill_weight)),
                        2,
                    )
                    if abs(rounded - prior) < 0.01:
                        continue
                kc_mastery[component.kc_id] = rounded
                backfilled[component.kc_id] = rounded
        return backfilled

    def _recompute_lo_mastery(
        self,
        *,
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
        graph: KnowledgeComponentGraph,
        affected_lo_ids: set[str],
    ) -> dict[str, float]:
        propagated_lo_updates: dict[str, float] = {}
        for lo_id in affected_lo_ids:
            updated_value = graph.weighted_lo_mastery(
                lo_id=lo_id, kc_mastery=kc_mastery
            )
            if updated_value is None:
                continue
            lo_mastery[lo_id] = updated_value
            propagated_lo_updates[lo_id] = updated_value
        return propagated_lo_updates

    def _relation_weight(
        self,
        *,
        base: float,
        relation: KnowledgeComponentRelation,
        polarity: str,
    ) -> float:
        depth_decay = (
            self.prerequisite_depth_decay
            if polarity == "positive"
            else self.dependent_depth_decay
        )
        complexity_factor = 1.0 + min(0.18, relation.component.difficulty * 0.18)
        distance_factor = max(0.45, relation.path_weight) * (
            depth_decay ** max(0, relation.depth - 1)
        )
        return _clamp(base * complexity_factor * distance_factor, lower=0.12, upper=0.5)
