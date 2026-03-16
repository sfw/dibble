from __future__ import annotations

from dataclasses import dataclass, field

from dibble.models.curriculum import KnowledgeComponent


def _clamp(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True, slots=True)
class KnowledgeComponentRelation:
    component: KnowledgeComponent
    depth: int
    path_weight: float
    relation_kind: str = "graph"


@dataclass(slots=True)
class KnowledgeComponentGraph:
    components: list[KnowledgeComponent]
    prerequisite_depth_decay: float = 0.82
    dependent_depth_decay: float = 0.78
    _components_by_id: dict[str, KnowledgeComponent] = field(init=False, default_factory=dict)
    _dependents_by_prerequisite: dict[str, list[str]] = field(init=False, default_factory=dict)
    _components_by_lo: dict[str, list[KnowledgeComponent]] = field(init=False, default_factory=dict)
    _components_by_family: dict[str, list[KnowledgeComponent]] = field(init=False, default_factory=dict)
    _components_by_cluster: dict[str, list[KnowledgeComponent]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._components_by_id = {component.kc_id: component for component in self.components}
        dependents: dict[str, list[str]] = {}
        components_by_lo: dict[str, list[KnowledgeComponent]] = {}
        components_by_family: dict[str, list[KnowledgeComponent]] = {}
        components_by_cluster: dict[str, list[KnowledgeComponent]] = {}
        for component in self.components:
            components_by_lo.setdefault(component.parent_lo_id, []).append(component)
            if component.concept_family:
                components_by_family.setdefault(component.concept_family, []).append(component)
            if component.taxonomy_cluster_id:
                components_by_cluster.setdefault(component.taxonomy_cluster_id, []).append(component)
            for prerequisite_kc_id in component.prerequisite_kc_ids:
                dependents.setdefault(prerequisite_kc_id, []).append(component.kc_id)
        self._dependents_by_prerequisite = dependents
        self._components_by_lo = components_by_lo
        self._components_by_family = components_by_family
        self._components_by_cluster = components_by_cluster

    def prerequisites_for(self, kc_id: str) -> list[KnowledgeComponentRelation]:
        return self._walk_prerequisites(kc_id=kc_id)

    def dependents_for(self, kc_id: str) -> list[KnowledgeComponentRelation]:
        return self._walk_dependents(kc_id=kc_id)

    def components_for_lo(self, lo_id: str) -> list[KnowledgeComponent]:
        return list(self._components_by_lo.get(lo_id, []))

    def sibling_relations_for(self, kc_id: str) -> list[KnowledgeComponentRelation]:
        component = self._components_by_id.get(kc_id)
        if component is None:
            return []
        siblings: list[KnowledgeComponentRelation] = []
        for sibling in self.components_for_lo(component.parent_lo_id):
            if sibling.kc_id == kc_id:
                continue
            siblings.append(
                KnowledgeComponentRelation(
                    component=sibling,
                    depth=1,
                    path_weight=round(self.relation_strength(source=component, target=sibling), 3),
                    relation_kind="same_lo",
                )
            )
        siblings.sort(key=lambda relation: (-relation.path_weight, relation.component.difficulty, relation.component.kc_id))
        return siblings

    def neighborhood_relations_for(
        self,
        kc_id: str,
        *,
        anchor_kc_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[KnowledgeComponentRelation]:
        component = self._components_by_id.get(kc_id)
        if component is None:
            return []
        anchor_ids = {value for value in anchor_kc_ids or [] if value != kc_id}
        candidates: dict[str, KnowledgeComponentRelation] = {}

        def include(candidate: KnowledgeComponent, *, relation_kind: str, base_weight: float) -> None:
            if candidate.kc_id == kc_id or candidate.kc_id in anchor_ids:
                return
            locality_weight = self._locality_weight(source=component, candidate=candidate, relation_kind=relation_kind)
            relation = KnowledgeComponentRelation(
                component=candidate,
                depth=1,
                path_weight=round(_clamp(base_weight + locality_weight), 3),
                relation_kind=relation_kind,
            )
            existing = candidates.get(candidate.kc_id)
            if existing is None or relation.path_weight > existing.path_weight or (
                relation.relation_kind == "curated_neighbor" and existing.relation_kind != "curated_neighbor"
            ):
                candidates[candidate.kc_id] = relation

        for relation in self.sibling_relations_for(kc_id):
            include(relation.component, relation_kind="same_lo", base_weight=0.52)

        for neighbor_id in component.nearby_kc_ids:
            neighbor = self._components_by_id.get(neighbor_id)
            if neighbor is not None:
                include(neighbor, relation_kind="curated_neighbor", base_weight=0.68)
        for candidate in self.components:
            if kc_id in candidate.nearby_kc_ids:
                include(candidate, relation_kind="curated_neighbor", base_weight=0.72)

        if component.concept_family:
            for family_component in self._components_by_family.get(component.concept_family, []):
                include(family_component, relation_kind="concept_family", base_weight=0.5)

        if component.taxonomy_cluster_id:
            for cluster_component in self._components_by_cluster.get(component.taxonomy_cluster_id, []):
                include(cluster_component, relation_kind="taxonomy_cluster", base_weight=0.44)

        relations = list(candidates.values())
        relations.sort(key=lambda relation: (-relation.path_weight, relation.component.difficulty, relation.component.kc_id))
        if limit is not None:
            return relations[:limit]
        return relations

    def bridge_candidates_for(
        self,
        kc_id: str,
        *,
        anchor_kc_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[KnowledgeComponentRelation]:
        component = self._components_by_id.get(kc_id)
        if component is None:
            return []
        anchor_ids = {value for value in anchor_kc_ids or [] if value != kc_id}
        target_prerequisites = set(component.prerequisite_kc_ids)
        candidates: list[KnowledgeComponentRelation] = []
        for relation in self.neighborhood_relations_for(kc_id, anchor_kc_ids=list(anchor_ids)):
            sibling = relation.component
            if sibling.kc_id in anchor_ids:
                continue
            shared_anchor_ids = anchor_ids.intersection(sibling.prerequisite_kc_ids)
            shared_target_prerequisites = target_prerequisites.intersection(sibling.prerequisite_kc_ids)
            locality_match = relation.relation_kind in {"curated_neighbor", "concept_family"}
            if not shared_anchor_ids and not shared_target_prerequisites and not locality_match:
                continue
            bridge_weight = relation.path_weight
            if shared_anchor_ids:
                bridge_weight += min(0.18, 0.09 * len(shared_anchor_ids))
            elif shared_target_prerequisites:
                bridge_weight += min(0.12, 0.06 * len(shared_target_prerequisites))
            elif relation.relation_kind == "curated_neighbor":
                bridge_weight += 0.12
            elif relation.relation_kind == "concept_family":
                bridge_weight += 0.08
            elif relation.relation_kind == "same_lo":
                bridge_weight += 0.05
            if sibling.difficulty <= component.difficulty:
                bridge_weight += 0.08
            else:
                bridge_weight -= min(0.12, (sibling.difficulty - component.difficulty) * 0.25)
            candidates.append(
                KnowledgeComponentRelation(
                    component=sibling,
                    depth=1,
                    path_weight=round(_clamp(bridge_weight), 3),
                    relation_kind=relation.relation_kind,
                )
            )
        candidates.sort(key=lambda relation: (-relation.path_weight, relation.component.difficulty, relation.component.kc_id))
        if limit is not None:
            return candidates[:limit]
        return candidates

    def weighted_lo_mastery(self, *, lo_id: str, kc_mastery: dict[str, float]) -> float | None:
        components = self.components_for_lo(lo_id)
        if not components:
            return None
        weighted_values: list[tuple[float, float]] = []
        for component in components:
            if component.kc_id not in kc_mastery:
                continue
            weighted_values.append((kc_mastery[component.kc_id], self.component_weight(component)))
        if not weighted_values:
            return None
        total_weight = sum(weight for _, weight in weighted_values)
        if total_weight <= 0:
            return None
        return round(sum(value * weight for value, weight in weighted_values) / total_weight, 2)

    def component_weight(self, component: KnowledgeComponent) -> float:
        prerequisite_count = len(component.prerequisite_kc_ids)
        time_factor = min(0.25, component.estimated_time_minutes / 40.0)
        return round(1.0 + (component.difficulty * 0.35) + (prerequisite_count * 0.12) + time_factor, 3)

    def relation_strength(self, *, source: KnowledgeComponent, target: KnowledgeComponent) -> float:
        difficulty_gap = abs(source.difficulty - target.difficulty)
        time_gap = abs(source.estimated_time_minutes - target.estimated_time_minutes)
        taxonomy_bonus = 0.0
        if source.parent_lo_id == target.parent_lo_id:
            taxonomy_bonus += 0.08
        if source.concept_family and source.concept_family == target.concept_family:
            taxonomy_bonus += 0.07
        if source.taxonomy_cluster_id and source.taxonomy_cluster_id == target.taxonomy_cluster_id:
            taxonomy_bonus += 0.05
        if target.kc_id in source.nearby_kc_ids or source.kc_id in target.nearby_kc_ids:
            taxonomy_bonus += 0.08
        return _clamp(
            0.95 - (difficulty_gap * 0.35) - min(0.18, time_gap / 100.0) + taxonomy_bonus,
            lower=0.45,
            upper=0.98,
        )

    def estimate_kc_from_lo(
        self,
        *,
        component: KnowledgeComponent,
        lo_mastery: float,
        kc_mastery: dict[str, float],
    ) -> float:
        prerequisite_values = [kc_mastery[kc_id] for kc_id in component.prerequisite_kc_ids if kc_id in kc_mastery]
        prerequisite_anchor = sum(prerequisite_values) / len(prerequisite_values) if prerequisite_values else lo_mastery
        sibling_values = [
            kc_mastery[sibling.kc_id]
            for sibling in self.components_for_lo(component.parent_lo_id)
            if sibling.kc_id != component.kc_id and sibling.kc_id in kc_mastery
        ]
        sibling_anchor = sum(sibling_values) / len(sibling_values) if sibling_values else lo_mastery
        difficulty_penalty = component.difficulty * 0.08
        estimated = (
            (lo_mastery * 0.55)
            + (prerequisite_anchor * 0.3)
            + (sibling_anchor * 0.15)
            - difficulty_penalty
        )
        return round(_clamp(estimated), 2)

    def _locality_weight(
        self,
        *,
        source: KnowledgeComponent,
        candidate: KnowledgeComponent,
        relation_kind: str,
    ) -> float:
        weight = self.relation_strength(source=source, target=candidate) * 0.34
        shared_prerequisites = set(source.prerequisite_kc_ids).intersection(candidate.prerequisite_kc_ids)
        if shared_prerequisites:
            weight += min(0.1, 0.04 * len(shared_prerequisites))
        if relation_kind == "curated_neighbor":
            weight += 0.1
        elif relation_kind == "concept_family":
            weight += 0.06
        elif relation_kind == "same_lo":
            weight += 0.04
        elif relation_kind == "taxonomy_cluster":
            weight += 0.03
        return weight

    def _walk_prerequisites(self, *, kc_id: str) -> list[KnowledgeComponentRelation]:
        ordered: list[KnowledgeComponentRelation] = []
        seen: set[str] = set()

        def visit(current_id: str, *, depth: int, path_weight: float) -> None:
            component = self._components_by_id.get(current_id)
            if component is None:
                return
            for prerequisite_id in component.prerequisite_kc_ids:
                prerequisite = self._components_by_id.get(prerequisite_id)
                if prerequisite is None:
                    continue
                relation_weight = self.relation_strength(source=component, target=prerequisite)
                next_depth = depth + 1
                next_weight = path_weight * relation_weight * self.prerequisite_depth_decay
                if prerequisite_id in seen:
                    continue
                seen.add(prerequisite_id)
                visit(prerequisite_id, depth=next_depth, path_weight=next_weight)
                ordered.append(
                    KnowledgeComponentRelation(
                        component=prerequisite,
                        depth=next_depth,
                        path_weight=round(next_weight, 3),
                        relation_kind="prerequisite",
                    )
                )

        visit(kc_id, depth=0, path_weight=1.0)
        ordered.sort(key=lambda relation: (relation.depth, -relation.path_weight, relation.component.kc_id))
        return ordered

    def _walk_dependents(self, *, kc_id: str) -> list[KnowledgeComponentRelation]:
        ordered: list[KnowledgeComponentRelation] = []
        seen: set[str] = set()
        queue: list[tuple[str, int, float]] = [
            (dependent_id, 1, self.dependent_depth_decay)
            for dependent_id in self._dependents_by_prerequisite.get(kc_id, [])
        ]
        source_component = self._components_by_id.get(kc_id)
        while queue:
            current_id, depth, path_weight = queue.pop(0)
            if current_id in seen:
                continue
            current_component = self._components_by_id.get(current_id)
            if current_component is None or source_component is None:
                continue
            seen.add(current_id)
            relation_weight = self.relation_strength(source=current_component, target=source_component)
            weighted_path = round(path_weight * relation_weight, 3)
            ordered.append(
                KnowledgeComponentRelation(
                    component=current_component,
                    depth=depth,
                    path_weight=weighted_path,
                    relation_kind="dependent",
                )
            )
            for child_id in self._dependents_by_prerequisite.get(current_id, []):
                if child_id in seen:
                    continue
                queue.append((child_id, depth + 1, weighted_path * self.dependent_depth_decay))
        ordered.sort(key=lambda relation: (relation.depth, -relation.path_weight, relation.component.kc_id))
        return ordered
