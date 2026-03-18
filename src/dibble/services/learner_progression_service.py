from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.curriculum import CurriculumResource, KnowledgeComponent
from dibble.models.profile import (
    CurriculumResourceProgressSummary,
    LearnerCurriculumProgressionSummary,
    LearnerFlowSummary,
)
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.protocols import CurriculumStore, KnowledgeComponentStore, ProfileStore
from dibble.services.workflow_rationale import combine_rationales

MASTERY_THRESHOLD = 0.8
PREREQUISITE_READY_THRESHOLD = 0.65
ACTIVE_RESOURCE_LIMIT = 3


@dataclass(slots=True)
class ResourcePlanningEntry:
    summary: CurriculumResourceProgressSummary
    dependency_resource_ids: list[str]
    blocked_prerequisite_kc_ids: list[str]
    current_flow_match_count: int = 0
    deferred_flow_match_count: int = 0
    depth: int = 0


@dataclass(slots=True)
class LearnerProgressionService:
    profile_store: ProfileStore
    curriculum_store: CurriculumStore
    knowledge_component_store: KnowledgeComponentStore
    learner_flow_service: LearnerFlowService

    def build_for_student(self, *, student_id: UUID) -> LearnerCurriculumProgressionSummary | None:
        profile = self.profile_store.get(student_id)
        if profile is None:
            return None

        resources = sorted(self.curriculum_store.list(), key=lambda resource: resource.resource_id)
        if not resources:
            flow = self.learner_flow_service.build_for_student(student_id=student_id)
            return LearnerCurriculumProgressionSummary(
                flow_type=flow.flow_type,
                current_stage=flow.current_phase,
                progression_action=flow.progression_action,
                active_target_kc_ids=list(flow.active_target_kc_ids),
                rationale="No curriculum resources are available for broader progression tracking.",
                updated_at=flow.updated_at or profile.updated_at,
            )

        flow = self.learner_flow_service.build_for_student(student_id=student_id)
        components = {component.kc_id: component for component in self.knowledge_component_store.list()}
        active_target_kc_ids = list(flow.active_target_kc_ids or flow.next_step.target_kc_ids)
        deferred_target_kc_ids = self._deferred_target_kc_ids(flow=flow)
        resource_by_id = {resource.resource_id: resource for resource in resources}
        kc_to_resource_ids = self._kc_to_resource_ids(resources=resources)
        entries = [
            self._resource_entry(
                resource=resource,
                components=components,
                kc_mastery=profile.knowledge_state.kc_mastery,
                lo_mastery=profile.knowledge_state.lo_mastery,
                flow=flow,
                active_target_kc_ids=active_target_kc_ids,
                deferred_target_kc_ids=deferred_target_kc_ids,
                current_stage=flow.target_stage,
                resource_by_id=resource_by_id,
                kc_to_resource_ids=kc_to_resource_ids,
            )
            for resource in resources
        ]
        depth_cache: dict[str, int] = {}
        for entry in entries:
            entry.depth = self._resource_depth(
                resource_id=entry.summary.resource_id,
                dependency_map={item.summary.resource_id: item.dependency_resource_ids for item in entries},
                cache=depth_cache,
                visiting=set(),
            )

        active_resources = sorted(
            [entry for entry in entries if entry.summary.state == "active"],
            key=self._active_priority,
        )
        ready_resources = sorted(
            [entry for entry in entries if entry.summary.state == "ready"],
            key=self._ready_priority,
        )
        blocked_resources = sorted(
            [entry for entry in entries if entry.summary.state == "blocked"],
            key=self._blocked_priority,
        )
        mastered_resources = sorted(
            [entry for entry in entries if entry.summary.state == "mastered"],
            key=lambda entry: (entry.depth, entry.summary.resource_id),
        )

        current_resource = active_resources[0].summary if active_resources else None
        next_resource = ready_resources[0].summary if ready_resources else None
        if current_resource is not None:
            status = "active_curriculum_focus"
            rationale = current_resource.rationale
        elif next_resource is not None:
            status = "ready_for_next_resource"
            rationale = next_resource.rationale
        elif blocked_resources:
            status = "blocked_on_prerequisites"
            rationale = blocked_resources[0].summary.rationale
        else:
            status = "catalog_mastered"
            rationale = "Current mapped curriculum resources appear sufficiently mastered."

        return LearnerCurriculumProgressionSummary(
            status=status,
            flow_type=flow.flow_type,
            current_stage=flow.current_phase,
            progression_action=flow.progression_action,
            active_target_kc_ids=active_target_kc_ids,
            resource_count=len(entries),
            mastered_resource_count=len(mastered_resources),
            ready_resource_count=len(ready_resources),
            blocked_resource_count=len(blocked_resources),
            active_resource_count=len(active_resources),
            mastered_resource_ratio=(
                round(len(mastered_resources) / len(entries), 2)
                if entries
                else 0.0
            ),
            current_resource=current_resource,
            next_resource=next_resource,
            blocked_resources=[entry.summary for entry in blocked_resources[:ACTIVE_RESOURCE_LIMIT]],
            ready_resources=[entry.summary for entry in ready_resources[:ACTIVE_RESOURCE_LIMIT]],
            rationale=rationale,
            updated_at=flow.updated_at or profile.updated_at,
        )

    def _resource_entry(
        self,
        *,
        resource: CurriculumResource,
        components: dict[str, KnowledgeComponent],
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
        flow: LearnerFlowSummary,
        active_target_kc_ids: list[str],
        deferred_target_kc_ids: list[str],
        current_stage: str,
        resource_by_id: dict[str, CurriculumResource],
        kc_to_resource_ids: dict[str, list[str]],
    ) -> ResourcePlanningEntry:
        required_kc_ids = list(resource.knowledge_component_ids)
        mastery_ratio = self._mastery_ratio(
            kc_ids=required_kc_ids,
            lo_ids=resource.learning_objective_ids,
            kc_mastery=kc_mastery,
            lo_mastery=lo_mastery,
        )
        blocked_prerequisites = self._blocked_prerequisites(
            kc_ids=required_kc_ids,
            components=components,
            kc_mastery=kc_mastery,
        )
        current_flow_match_count = len(set(required_kc_ids) & set(active_target_kc_ids))
        deferred_flow_match_count = len(set(required_kc_ids) & set(deferred_target_kc_ids))
        current_flow_aligned = current_flow_match_count > 0
        dependency_resource_ids = self._dependency_resource_ids(
            resource=resource,
            components=components,
            kc_to_resource_ids=kc_to_resource_ids,
        )
        if current_flow_aligned:
            state = "active"
            rationale = flow.rationale or "The current learner flow is focused on this curriculum resource."
        elif self._is_mastered(kc_ids=required_kc_ids, lo_ids=resource.learning_objective_ids, kc_mastery=kc_mastery, lo_mastery=lo_mastery):
            state = "mastered"
            rationale = "Mastery across this resource's mapped targets is strong enough to treat it as complete."
        elif self._is_deferred_target_being_unlocked(
            flow=flow,
            blocked_prerequisites=blocked_prerequisites,
            active_target_kc_ids=active_target_kc_ids,
            deferred_flow_match_count=deferred_flow_match_count,
        ):
            state = "ready"
            blocked_labels = ", ".join(
                self._blocked_prerequisite_label(
                    kc_id=kc_id,
                    components=components,
                    kc_mastery=kc_mastery,
                )
                for kc_id in blocked_prerequisites
            )
            rationale = combine_rationales(
                (
                    f"The current learner flow is actively repairing prerequisite KCs {blocked_labels} for this resource, "
                    "so it remains the planned next curriculum focus instead of falling behind unrelated ready work."
                ),
                self._deferred_target_rationale(flow=flow, resource=resource),
                "The backend can move here as soon as the current learner flow releases the active target.",
            ) or "The backend can move here as soon as the current learner flow releases the active target."
        elif blocked_prerequisites:
            state = "blocked"
            blocked_labels = ", ".join(
                self._blocked_prerequisite_label(
                    kc_id=kc_id,
                    components=components,
                    kc_mastery=kc_mastery,
                )
                for kc_id in blocked_prerequisites
            )
            blocking_resource_titles = self._blocking_resource_titles(
                prerequisite_kc_ids=blocked_prerequisites,
                resource_by_id=resource_by_id,
                kc_to_resource_ids=kc_to_resource_ids,
                current_resource_id=resource.resource_id,
            )
            rationale = (
                f"Prerequisite KCs {blocked_labels} are not yet strong enough, so this resource stays blocked "
                "instead of becoming the next curriculum focus."
            )
            if blocking_resource_titles:
                rationale = combine_rationales(
                    rationale,
                    f"This resource is still waiting behind {', '.join(blocking_resource_titles)}.",
                ) or rationale
        else:
            state = "ready"
            rationale = combine_rationales(
                "Prerequisites are met, so this resource is available as the next curriculum focus.",
                (
                    self._deferred_target_rationale(flow=flow, resource=resource)
                    if deferred_flow_match_count > 0
                    else None
                ),
                (
                    "The backend can move here as soon as the current learner flow releases the active target."
                    if flow.status != "idle"
                    else None
                ),
            ) or "Prerequisites are met, so this resource is available as the next curriculum focus."

        return ResourcePlanningEntry(
            summary=CurriculumResourceProgressSummary(
                resource_id=resource.resource_id,
                title=resource.title,
                state=state,
                learning_objective_ids=list(resource.learning_objective_ids),
                knowledge_component_ids=required_kc_ids,
                blocked_prerequisite_kc_ids=blocked_prerequisites,
                mastery_ratio=mastery_ratio,
                current_flow_aligned=current_flow_aligned,
                target_stage=current_stage if current_flow_aligned else "target",
                rationale=rationale,
            ),
            dependency_resource_ids=dependency_resource_ids,
            blocked_prerequisite_kc_ids=blocked_prerequisites,
            current_flow_match_count=current_flow_match_count,
            deferred_flow_match_count=deferred_flow_match_count,
        )

    def _kc_to_resource_ids(self, *, resources: list[CurriculumResource]) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        for resource in resources:
            for kc_id in resource.knowledge_component_ids:
                resource_ids = index.setdefault(kc_id, [])
                if resource.resource_id not in resource_ids:
                    resource_ids.append(resource.resource_id)
        return index

    def _dependency_resource_ids(
        self,
        *,
        resource: CurriculumResource,
        components: dict[str, KnowledgeComponent],
        kc_to_resource_ids: dict[str, list[str]],
    ) -> list[str]:
        dependency_ids: list[str] = []
        for kc_id in resource.knowledge_component_ids:
            component = components.get(kc_id)
            if component is None:
                continue
            for prerequisite_id in component.prerequisite_kc_ids:
                for resource_id in kc_to_resource_ids.get(prerequisite_id, []):
                    if resource_id != resource.resource_id and resource_id not in dependency_ids:
                        dependency_ids.append(resource_id)
        return dependency_ids

    def _resource_depth(
        self,
        *,
        resource_id: str,
        dependency_map: dict[str, list[str]],
        cache: dict[str, int],
        visiting: set[str],
    ) -> int:
        if resource_id in cache:
            return cache[resource_id]
        if resource_id in visiting:
            return 0
        visiting.add(resource_id)
        dependencies = dependency_map.get(resource_id, [])
        if not dependencies:
            depth = 0
        else:
            depth = 1 + max(
                self._resource_depth(
                    resource_id=dependency_id,
                    dependency_map=dependency_map,
                    cache=cache,
                    visiting=visiting,
                )
                for dependency_id in dependencies
            )
        visiting.remove(resource_id)
        cache[resource_id] = depth
        return depth

    def _active_priority(self, entry: ResourcePlanningEntry) -> tuple[int, int, str]:
        return (-entry.current_flow_match_count, entry.depth, entry.summary.resource_id)

    def _ready_priority(self, entry: ResourcePlanningEntry) -> tuple[int, int, int, str]:
        return (-entry.deferred_flow_match_count, entry.depth, len(entry.dependency_resource_ids), entry.summary.resource_id)

    def _blocked_priority(self, entry: ResourcePlanningEntry) -> tuple[int, int, str]:
        return (len(entry.blocked_prerequisite_kc_ids), entry.depth, entry.summary.resource_id)

    def _deferred_target_kc_ids(self, *, flow: LearnerFlowSummary) -> list[str]:
        return list(
            dict.fromkeys(
                [
                    *flow.deferred_target_kc_ids,
                    *flow.transfer_target_kc_ids,
                ]
            )
        )

    def _blocked_prerequisite_label(
        self,
        *,
        kc_id: str,
        components: dict[str, KnowledgeComponent],
        kc_mastery: dict[str, float],
    ) -> str:
        component = components.get(kc_id)
        label = component.name if component is not None else kc_id
        score = float(kc_mastery.get(kc_id, 0.0))
        return f"{label} ({score:.2f}/{PREREQUISITE_READY_THRESHOLD:.2f})"

    def _blocking_resource_titles(
        self,
        *,
        prerequisite_kc_ids: list[str],
        resource_by_id: dict[str, CurriculumResource],
        kc_to_resource_ids: dict[str, list[str]],
        current_resource_id: str,
    ) -> list[str]:
        titles: list[str] = []
        for kc_id in prerequisite_kc_ids:
            for resource_id in kc_to_resource_ids.get(kc_id, []):
                if resource_id == current_resource_id:
                    continue
                resource = resource_by_id.get(resource_id)
                if resource is None or resource.title in titles:
                    continue
                titles.append(resource.title)
        return titles

    def _deferred_target_rationale(
        self,
        *,
        flow: LearnerFlowSummary,
        resource: CurriculumResource,
    ) -> str | None:
        if flow.status == "idle":
            return None
        if flow.target_stage == "repair":
            return (
                f"This resource is the deferred return target while the backend holds repair on the current prerequisite path "
                f"before reopening {resource.title}."
            )
        if flow.target_stage == "bridge":
            return (
                f"This resource is the deferred return target while the backend holds one guided bridge step "
                f"before reopening {resource.title}."
            )
        if flow.target_stage == "transfer":
            return "This resource is the current transfer-return target once the active flow completes."
        return None

    def _is_deferred_target_being_unlocked(
        self,
        *,
        flow: LearnerFlowSummary,
        blocked_prerequisites: list[str],
        active_target_kc_ids: list[str],
        deferred_flow_match_count: int,
    ) -> bool:
        if deferred_flow_match_count <= 0 or not blocked_prerequisites:
            return False
        if flow.target_stage not in {"repair", "bridge"}:
            return False
        return set(blocked_prerequisites).issubset(set(active_target_kc_ids))

    def _blocked_prerequisites(
        self,
        *,
        kc_ids: list[str],
        components: dict[str, KnowledgeComponent],
        kc_mastery: dict[str, float],
    ) -> list[str]:
        blocked: list[str] = []
        for kc_id in kc_ids:
            component = components.get(kc_id)
            if component is None:
                continue
            for prerequisite_id in component.prerequisite_kc_ids:
                if float(kc_mastery.get(prerequisite_id, 0.0)) < PREREQUISITE_READY_THRESHOLD:
                    blocked.append(prerequisite_id)
        return list(dict.fromkeys(blocked))

    def _is_mastered(
        self,
        *,
        kc_ids: list[str],
        lo_ids: list[str],
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
    ) -> bool:
        if kc_ids:
            scores = [float(kc_mastery.get(kc_id, 0.0)) for kc_id in kc_ids]
            return bool(scores) and min(scores) >= PREREQUISITE_READY_THRESHOLD and sum(scores) / len(scores) >= MASTERY_THRESHOLD
        if lo_ids:
            scores = [float(lo_mastery.get(lo_id, 0.0)) for lo_id in lo_ids]
            return bool(scores) and min(scores) >= PREREQUISITE_READY_THRESHOLD and sum(scores) / len(scores) >= MASTERY_THRESHOLD
        return False

    def _mastery_ratio(
        self,
        *,
        kc_ids: list[str],
        lo_ids: list[str],
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
    ) -> float:
        if kc_ids:
            scores = [float(kc_mastery.get(kc_id, 0.0)) for kc_id in kc_ids]
        else:
            scores = [float(lo_mastery.get(lo_id, 0.0)) for lo_id in lo_ids]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 2)
