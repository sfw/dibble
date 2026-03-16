from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile, LearnerStrategySummary
from dibble.models.remediation import KcSequenceSummary
from dibble.services.kc_sequence_planner import KcSequencePlanner
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
    kc_sequence: KcSequenceSummary


class RemediationPlanner:
    def __init__(
        self,
        knowledge_component_store: KnowledgeComponentStore,
        misconception_detector: MisconceptionDetector,
        module_blueprint_builder: RemediationModuleBlueprintBuilder | None = None,
        kc_sequence_planner: KcSequencePlanner | None = None,
    ) -> None:
        self.knowledge_component_store = knowledge_component_store
        self.misconception_detector = misconception_detector
        self.module_blueprint_builder = module_blueprint_builder or RemediationModuleBlueprintBuilder()
        self.kc_sequence_planner = kc_sequence_planner or KcSequencePlanner()

    def plan(
        self,
        profile: LearnerProfile,
        target_kc_id: str,
        *,
        misconception_description: str,
        curriculum_context: list[str],
        strategy_summary: LearnerStrategySummary | None = None,
    ) -> RemediationPlan:
        target_component = self.knowledge_component_store.get(target_kc_id)
        signals = self.misconception_detector.detect(
            profile,
            target_kc_id=target_kc_id,
            misconception_description=misconception_description,
            curriculum_context=curriculum_context,
        )
        primary_misconception_signals = [
            signal
            for signal in signals
            if signal.category == "known_misconception" and signal.misconception_id is not None and signal.primary_for_kc
        ]
        prerequisite_gaps = [
            signal.kc_id
            for signal in signals
            if signal.category == "prerequisite_gap"
        ]
        recurring_profile_signals = [
            signal
            for signal in primary_misconception_signals
            if signal.source == "profile" and signal.recurrence_signal in {"recurring", "relapsing"}
        ]
        misconception_repair_targets = [
            kc_id
            for signal in primary_misconception_signals
            for kc_id in signal.recommended_kc_ids
        ]
        kc_sequence = self.kc_sequence_planner.plan(
            strategy_summary=strategy_summary,
            target_kc_ids=[target_kc_id],
            prerequisite_kc_ids=prerequisite_gaps,
            repair_target_kc_ids=misconception_repair_targets or [target_kc_id],
        )

        focus_kc_ids = list(kc_sequence.ordered_kc_ids)
        for signal in recurring_profile_signals:
            for kc_id in signal.recommended_kc_ids or [signal.kc_id]:
                if kc_id not in focus_kc_ids:
                    focus_kc_ids.append(kc_id)
        if target_kc_id not in focus_kc_ids:
            focus_kc_ids.append(target_kc_id)

        matched_misconceptions = primary_misconception_signals
        if recurring_profile_signals:
            strongest_profile_signal = recurring_profile_signals[0]
            recurrence_fragment = (
                f"{strongest_profile_signal.recurrence_signal} across {strongest_profile_signal.recurrence_session_count} sessions"
            )
            rationale = (
                "Misconception profiles show a repeated pattern "
                f"({recurrence_fragment}), so remediation should explicitly repair that reasoning"
                + (
                    " while stepping back through prerequisite knowledge components."
                    if prerequisite_gaps
                    else " before returning to the target."
                )
            )
        elif matched_misconceptions:
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
        if kc_sequence.action != "monitor":
            rationale = (
                f"{rationale} Sequence the next KC focus as {kc_sequence.action.replace('_', ' ')}"
                + (f" on {kc_sequence.primary_kc_id}." if kc_sequence.primary_kc_id is not None else ".")
            )

        return RemediationPlan(
            focus_kc_ids=focus_kc_ids,
            prerequisite_kc_ids=prerequisite_gaps,
            misconception_signals=signals,
            rationale=rationale,
            module_blueprint=self.module_blueprint_builder.build(
                target_kc_id=target_kc_id,
                prerequisite_kc_ids=prerequisite_gaps,
                misconception_signals=signals,
                kc_sequence=kc_sequence,
            ),
            kc_sequence=kc_sequence,
        )
