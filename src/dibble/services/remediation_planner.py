from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile, LearnerStrategySummary
from dibble.models.remediation import KcSequenceSummary
from dibble.services.kc_sequence_planner import KcSequencePlanner
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.protocols import KnowledgeComponentStore
from dibble.services.remediation_module_blueprints import (
    RemediationModuleBlueprintBuilder,
)
from dibble.services.workflow_rationale import combine_rationales


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
        self.module_blueprint_builder = (
            module_blueprint_builder or RemediationModuleBlueprintBuilder()
        )
        self.kc_sequence_planner = kc_sequence_planner or KcSequencePlanner(
            knowledge_component_store=knowledge_component_store
        )

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
            if signal.category == "known_misconception"
            and signal.misconception_id is not None
            and signal.primary_for_kc
        ]
        prerequisite_gaps = [
            signal.kc_id for signal in signals if signal.category == "prerequisite_gap"
        ]
        recurring_profile_signals = [
            signal
            for signal in primary_misconception_signals
            if signal.source == "profile"
            and signal.recurrence_signal in {"recurring", "relapsing"}
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
            selected_signal = recurring_profile_signals[0]
            rationale = self._misconception_path_rationale(
                target_kc_id=target_kc_id,
                primary_signal=selected_signal,
                prerequisite_gaps=prerequisite_gaps,
            )
            rationale = (
                combine_rationales(
                    rationale,
                    self._misconception_selection_rationale(
                        target_kc_id=target_kc_id,
                        primary_signal=selected_signal,
                        signals=signals,
                        prerequisite_gaps=prerequisite_gaps,
                    ),
                )
                or rationale
            )
        elif matched_misconceptions:
            selected_signal = matched_misconceptions[0]
            rationale = self._misconception_path_rationale(
                target_kc_id=target_kc_id,
                primary_signal=selected_signal,
                prerequisite_gaps=prerequisite_gaps,
            )
            rationale = (
                combine_rationales(
                    rationale,
                    self._misconception_selection_rationale(
                        target_kc_id=target_kc_id,
                        primary_signal=selected_signal,
                        signals=signals,
                        prerequisite_gaps=prerequisite_gaps,
                    ),
                )
                or rationale
            )
        elif prerequisite_gaps:
            prerequisite_names = [
                self.knowledge_component_store.get(kc_id).name
                for kc_id in prerequisite_gaps
                if self.knowledge_component_store.get(kc_id) is not None
            ]
            rationale = (
                "Misconception evidence points to prerequisite knowledge components that need repair before the learner returns to the target: "
                + ", ".join(prerequisite_names)
            )
        elif target_component is not None:
            rationale = (
                f"Current misconception evidence stays centered on the target knowledge component {target_component.name}, "
                "so remediation should repair that idea directly instead of stepping back to an unrelated prerequisite."
            )
        else:
            rationale = "Misconception signals did not reveal a stronger prerequisite target, so remediation should reinforce the requested component."
        if kc_sequence.action != "monitor":
            rationale = (
                combine_rationales(
                    rationale,
                    (
                        f"Sequence the next KC focus as {kc_sequence.action.replace('_', ' ')}"
                        + (
                            f" on {kc_sequence.primary_kc_id}."
                            if kc_sequence.primary_kc_id is not None
                            else "."
                        )
                    ),
                    kc_sequence.rationale,
                )
                or rationale
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

    def _misconception_path_rationale(
        self,
        *,
        target_kc_id: str,
        primary_signal: MisconceptionSignal,
        prerequisite_gaps: list[str],
    ) -> str:
        target_label = self._kc_label(target_kc_id)
        signal_label = (
            primary_signal.misconception_id or primary_signal.category.replace("_", " ")
        )
        signal_kc_label = self._kc_label(primary_signal.kc_id)
        repair_targets = primary_signal.recommended_kc_ids or [primary_signal.kc_id]
        repair_target_labels = ", ".join(
            self._kc_label(kc_id) for kc_id in repair_targets
        )
        evidence_fragment = (
            f" with evidence on {', '.join(primary_signal.evidence_terms[:3])}"
            if primary_signal.evidence_terms
            else ""
        )
        recurrence_fragment = ""
        if (
            primary_signal.recurrence_signal in {"recurring", "relapsing"}
            and primary_signal.recurrence_session_count > 0
        ):
            recurrence_fragment = f"; it has been {primary_signal.recurrence_signal} across {primary_signal.recurrence_session_count} sessions"
        source_fragment = (
            "Durable misconception history"
            if primary_signal.source == "profile"
            else "Current misconception evidence"
        )
        return (
            f"{source_fragment} points to {signal_label} on {signal_kc_label} at {primary_signal.confidence:.2f} confidence"
            f"{evidence_fragment}{recurrence_fragment}, so remediation should repair {repair_target_labels}"
            + (
                f" before returning to {target_label}."
                if repair_target_labels != target_label or prerequisite_gaps
                else f" directly on {target_label} rather than stepping back to a different prerequisite."
            )
        )

    def _misconception_selection_rationale(
        self,
        *,
        target_kc_id: str,
        primary_signal: MisconceptionSignal,
        signals: list[MisconceptionSignal],
        prerequisite_gaps: list[str],
    ) -> str | None:
        rationale = primary_signal.disambiguation_rationale
        alternative_signal = self._strongest_alternative_signal(
            primary_signal=primary_signal,
            signals=signals,
        )
        alternative_rationale = self._alternative_path_rationale(
            target_kc_id=target_kc_id,
            primary_signal=primary_signal,
            alternative_signal=alternative_signal,
            prerequisite_gaps=prerequisite_gaps,
        )
        if rationale is None:
            competing_count = sum(
                1 for signal in signals if signal is not primary_signal
            )
            if competing_count > 0:
                rationale = (
                    f"This misconception path outranked {competing_count} adjacent candidate(s) for {self._kc_label(target_kc_id)}, "
                    "so the backend is keeping the remediation path inspectable instead of spreading effort across multiple weak hypotheses."
                )
            elif prerequisite_gaps:
                rationale = (
                    "The backend is prioritizing the stronger misconception path before a prerequisite-only step-back because "
                    "the misconception evidence is more specific than the broader prerequisite gap."
                )
        return combine_rationales(rationale, alternative_rationale)

    def _strongest_alternative_signal(
        self,
        *,
        primary_signal: MisconceptionSignal,
        signals: list[MisconceptionSignal],
    ) -> MisconceptionSignal | None:
        alternatives = [signal for signal in signals if signal is not primary_signal]
        if not alternatives:
            return None
        category_priority = {
            "known_misconception": 0,
            "prerequisite_gap": 1,
            "target_concept_confusion": 2,
        }
        return max(
            alternatives,
            key=lambda signal: (
                signal.confidence,
                signal.recurrence_session_count,
                signal.recurrence_count,
                -category_priority.get(signal.category, 3),
                len(signal.evidence_terms),
            ),
        )

    def _alternative_path_rationale(
        self,
        *,
        target_kc_id: str,
        primary_signal: MisconceptionSignal,
        alternative_signal: MisconceptionSignal | None,
        prerequisite_gaps: list[str],
    ) -> str | None:
        if alternative_signal is None:
            if prerequisite_gaps:
                return (
                    "The backend is prioritizing the stronger misconception path before a prerequisite-only step-back because "
                    "the misconception evidence is more specific than the broader prerequisite gap."
                )
            return None

        alternative_focus = self._signal_focus_label(alternative_signal)
        if alternative_signal.category == "prerequisite_gap":
            return (
                f"This path beat the broader prerequisite-gap signal on {alternative_focus} "
                f"({alternative_signal.confidence:.2f} confidence), so the backend is repairing the more specific misconception "
                "instead of defaulting to a generic step-back."
            )
        if alternative_signal.category == "target_concept_confusion":
            return (
                f"This path beat the broader target-fragility signal on {alternative_focus} "
                f"({alternative_signal.confidence:.2f} confidence), so remediation stays centered on the more specific misconception "
                "rather than a generic target confusion read."
            )
        if alternative_signal.category == "known_misconception":
            alternative_label = (
                alternative_signal.misconception_id
                or alternative_signal.category.replace("_", " ")
            )
            return (
                f"This path beat the adjacent misconception path {alternative_label} on {alternative_focus} "
                f"({alternative_signal.confidence:.2f} confidence), so the backend is choosing one inspectable repair target "
                "instead of splitting effort across competing misconception hypotheses."
            )
        if prerequisite_gaps:
            return (
                f"This path stayed stronger than the broader prerequisite-only repair posture around {self._kc_label(target_kc_id)}, "
                "so the backend is keeping the remediation target specific."
            )
        return None

    def _signal_focus_label(self, signal: MisconceptionSignal) -> str:
        focus_kc_ids = signal.recommended_kc_ids or [signal.kc_id]
        labels = [self._kc_label(kc_id) for kc_id in focus_kc_ids]
        if not labels:
            return self._kc_label(signal.kc_id)
        if len(labels) == 1:
            return labels[0]
        return ", ".join(labels)

    def _kc_label(self, kc_id: str) -> str:
        component = self.knowledge_component_store.get(kc_id)
        if component is None:
            return kc_id
        return component.name
