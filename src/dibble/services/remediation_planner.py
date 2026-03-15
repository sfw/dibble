from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.protocols import KnowledgeComponentStore


@dataclass(slots=True)
class RemediationPlan:
    focus_kc_ids: list[str]
    prerequisite_kc_ids: list[str]
    misconception_signals: list[MisconceptionSignal]
    rationale: str


class RemediationPlanner:
    def __init__(
        self,
        knowledge_component_store: KnowledgeComponentStore,
        misconception_detector: MisconceptionDetector,
    ) -> None:
        self.knowledge_component_store = knowledge_component_store
        self.misconception_detector = misconception_detector

    def plan(
        self,
        profile: LearnerProfile,
        target_kc_id: str,
        *,
        misconception_description: str,
        curriculum_context: list[str],
    ) -> RemediationPlan:
        target_component = self.knowledge_component_store.get(target_kc_id)
        signals = self.misconception_detector.detect(
            profile,
            target_kc_id=target_kc_id,
            misconception_description=misconception_description,
            curriculum_context=curriculum_context,
        )
        prerequisite_gaps = [
            signal.kc_id
            for signal in signals
            if signal.category == "prerequisite_gap"
        ]

        focus_kc_ids: list[str] = []
        for kc_id in prerequisite_gaps:
            if kc_id not in focus_kc_ids:
                focus_kc_ids.append(kc_id)
        if target_kc_id not in focus_kc_ids:
            focus_kc_ids.append(target_kc_id)

        if prerequisite_gaps:
            prerequisite_names = [
                self.knowledge_component_store.get(kc_id).name
                for kc_id in prerequisite_gaps
                if self.knowledge_component_store.get(kc_id) is not None
            ]
            rationale = (
                "Misconception signals suggest stepping back through prerequisite knowledge components before returning to the target: "
                + ", ".join(prerequisite_names)
            )
        elif target_component is not None:
            rationale = f"Misconception signals stay centered on the target knowledge component: {target_component.name}."
        else:
            rationale = "Misconception signals did not reveal a stronger prerequisite target, so remediation should reinforce the requested component."

        return RemediationPlan(
            focus_kc_ids=focus_kc_ids,
            prerequisite_kc_ids=prerequisite_gaps,
            misconception_signals=signals,
            rationale=rationale,
        )
