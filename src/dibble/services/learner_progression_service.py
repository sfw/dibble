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
        entries = [
            self._resource_summary(
                resource=resource,
                components=components,
                kc_mastery=profile.knowledge_state.kc_mastery,
                lo_mastery=profile.knowledge_state.lo_mastery,
                flow=flow,
                active_target_kc_ids=active_target_kc_ids,
                current_stage=flow.target_stage,
            )
            for resource in resources
        ]

        active_resources = [entry for entry in entries if entry.state == "active"]
        ready_resources = [entry for entry in entries if entry.state == "ready"]
        blocked_resources = [entry for entry in entries if entry.state == "blocked"]
        mastered_resources = [entry for entry in entries if entry.state == "mastered"]

        current_resource = active_resources[0] if active_resources else None
        next_resource = ready_resources[0] if ready_resources else None
        if current_resource is not None:
            status = "active_curriculum_focus"
            rationale = current_resource.rationale
        elif next_resource is not None:
            status = "ready_for_next_resource"
            rationale = next_resource.rationale
        elif blocked_resources:
            status = "blocked_on_prerequisites"
            rationale = blocked_resources[0].rationale
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
            blocked_resources=blocked_resources[:ACTIVE_RESOURCE_LIMIT],
            ready_resources=ready_resources[:ACTIVE_RESOURCE_LIMIT],
            rationale=rationale,
            updated_at=flow.updated_at or profile.updated_at,
        )

    def _resource_summary(
        self,
        *,
        resource: CurriculumResource,
        components: dict[str, KnowledgeComponent],
        kc_mastery: dict[str, float],
        lo_mastery: dict[str, float],
        flow: LearnerFlowSummary,
        active_target_kc_ids: list[str],
        current_stage: str,
    ) -> CurriculumResourceProgressSummary:
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
        current_flow_aligned = bool(set(required_kc_ids) & set(active_target_kc_ids))
        if current_flow_aligned:
            state = "active"
            rationale = flow.rationale or "The current learner flow is focused on this curriculum resource."
        elif self._is_mastered(kc_ids=required_kc_ids, lo_ids=resource.learning_objective_ids, kc_mastery=kc_mastery, lo_mastery=lo_mastery):
            state = "mastered"
            rationale = "Mastery across this resource's mapped targets is strong enough to treat it as complete."
        elif blocked_prerequisites:
            state = "blocked"
            blocked_labels = ", ".join(
                component.name if (component := components.get(kc_id)) is not None else kc_id
                for kc_id in blocked_prerequisites
            )
            rationale = (
                f"Prerequisite KCs {blocked_labels} are not yet strong enough, so this resource stays blocked "
                "instead of becoming the next curriculum focus."
            )
        else:
            state = "ready"
            rationale = combine_rationales(
                "Prerequisites are met, so this resource is available as the next curriculum focus.",
                (
                    "The backend can move here as soon as the current learner flow releases the active target."
                    if flow.status != "idle"
                    else None
                ),
            ) or "Prerequisites are met, so this resource is available as the next curriculum focus."

        return CurriculumResourceProgressSummary(
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
        )

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
