from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.protocols import KnowledgeComponentStore
from dibble.services.remediation_module_blueprints import RemediationModuleBlueprintBuilder


@dataclass(slots=True)
class RemediationPlan:
    focus_kc_ids: list[str]
    prerequisite_kc_ids: list[str]
    misconception_signals: list[MisconceptionSignal]
    rationale: str
    module_blueprint: dict[str, object]


class RemediationPlanner:
    def __init__(
        self,
        knowledge_component_store: KnowledgeComponentStore,
        misconception_detector: MisconceptionDetector,
        module_blueprint_builder: RemediationModuleBlueprintBuilder | None = None,
    ) -> None:
        self.knowledge_component_store = knowledge_component_store
        self.misconception_detector = misconception_detector
        self.module_blueprint_builder = module_blueprint_builder or RemediationModuleBlueprintBuilder()

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
        misconception_repair_targets = [
            kc_id
            for signal in signals
            if signal.category == "known_misconception"
            for kc_id in signal.recommended_kc_ids
        ]

        focus_kc_ids: list[str] = []
        for kc_id in misconception_repair_targets:
            if kc_id not in focus_kc_ids:
                focus_kc_ids.append(kc_id)
        for kc_id in prerequisite_gaps:
            if kc_id not in focus_kc_ids:
                focus_kc_ids.append(kc_id)
        if target_kc_id not in focus_kc_ids:
            focus_kc_ids.append(target_kc_id)

        matched_misconceptions = [
            signal
            for signal in signals
            if signal.category == "known_misconception" and signal.misconception_id is not None
        ]
        if matched_misconceptions:
            labels = ", ".join(
                signal.misconception_id or signal.category
                for signal in matched_misconceptions[:2]
            )
            rationale = (
                f"Misconception signals matched catalogued patterns ({labels}), so remediation should explicitly repair that reasoning"
                + (
                    " while stepping back through prerequisite knowledge components."
                    if prerequisite_gaps
                    else " before returning to the target."
                )
            )
        elif prerequisite_gaps:
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
            module_blueprint=self.module_blueprint_builder.build(
                target_kc_id=target_kc_id,
                prerequisite_kc_ids=prerequisite_gaps,
                misconception_signals=signals,
            ),
        )
