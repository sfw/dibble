from __future__ import annotations

from dataclasses import dataclass

from dibble.models.profile import LearnerProfile
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore


@dataclass(slots=True)
class RemediationPlan:
    focus_kc_ids: list[str]
    prerequisite_kc_ids: list[str]
    rationale: str


class RemediationPlanner:
    def __init__(self, knowledge_component_store: SQLiteKnowledgeComponentStore) -> None:
        self.knowledge_component_store = knowledge_component_store

    def plan(self, profile: LearnerProfile, target_kc_id: str) -> RemediationPlan:
        target_component = self.knowledge_component_store.get(target_kc_id)
        prerequisite_components = self.knowledge_component_store.list_prerequisites(target_kc_id)

        prerequisite_gaps = [
            component.kc_id
            for component in prerequisite_components
            if profile.knowledge_state.kc_mastery.get(component.kc_id, 0.0) < 0.75
        ]
        target_mastery = profile.knowledge_state.kc_mastery.get(target_kc_id, 0.0)

        focus_kc_ids = [*prerequisite_gaps]
        if target_kc_id not in focus_kc_ids:
            focus_kc_ids.append(target_kc_id)

        if prerequisite_gaps:
            prerequisite_names = [
                self.knowledge_component_store.get(kc_id).name
                for kc_id in prerequisite_gaps
                if self.knowledge_component_store.get(kc_id) is not None
            ]
            rationale = (
                "Remediation should step back through prerequisite knowledge components before returning to the target: "
                + ", ".join(prerequisite_names)
            )
        elif target_component is not None and target_mastery < 0.85:
            rationale = f"Remediation can stay on the target knowledge component: {target_component.name}."
        else:
            rationale = "No prerequisite gap was detected, so remediation should reinforce the requested target component."

        return RemediationPlan(
            focus_kc_ids=focus_kc_ids,
            prerequisite_kc_ids=prerequisite_gaps,
            rationale=rationale,
        )
