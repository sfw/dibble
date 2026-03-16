from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import MisconceptionSignal
from dibble.models.remediation import KcSequenceSummary


@dataclass(slots=True)
class RemediationModuleBlueprintBuilder:
    def build(
        self,
        *,
        target_kc_id: str,
        prerequisite_kc_ids: list[str],
        misconception_signals: list[MisconceptionSignal],
        kc_sequence: KcSequenceSummary,
    ) -> dict[str, object]:
        primary_profile_signal = next(
            (
                signal
                for signal in misconception_signals
                if signal.primary_for_kc
                and signal.source == "profile"
                and signal.recurrence_signal in {"recurring", "relapsing"}
            ),
            None,
        )
        primary_catalog_signal = next(
            (
                signal
                for signal in misconception_signals
                if signal.primary_for_kc and signal.source in {"catalog", "profile"} and signal.misconception_id
            ),
            None,
        )
        repair_targets = []
        primary_signal = primary_profile_signal or primary_catalog_signal
        prioritized_signals = [primary_signal] if primary_signal is not None else misconception_signals
        for signal in prioritized_signals:
            if signal is None:
                continue
            for kc_id in signal.recommended_kc_ids or [signal.kc_id]:
                if kc_id not in repair_targets:
                    repair_targets.append(kc_id)
        if not repair_targets:
            repair_targets.append(target_kc_id)
        ordered_focus_kc_ids = kc_sequence.ordered_kc_ids or [*repair_targets, target_kc_id]
        ordered_prerequisite_targets = [kc_id for kc_id in ordered_focus_kc_ids if kc_id in prerequisite_kc_ids]
        ordered_repair_targets = [
            kc_id
            for kc_id in ordered_focus_kc_ids
            if kc_id in repair_targets and kc_id not in ordered_prerequisite_targets
        ] or repair_targets
        ordered_bridge_targets = [
            kc_id
            for kc_id in ordered_focus_kc_ids
            if kc_id in kc_sequence.bridge_kc_ids and kc_id not in ordered_repair_targets
        ] or list(kc_sequence.bridge_kc_ids)

        steps: list[dict[str, object]] = []
        if prerequisite_kc_ids and kc_sequence.action == "rebuild_prerequisite_first":
            steps.append(
                {
                    "phase": "step_back",
                    "title": "Rebuild the prerequisite idea",
                    "target_kc_ids": ordered_prerequisite_targets or prerequisite_kc_ids,
                    "support_level": "high",
                    "objective": "Reconnect the learner to the weaker prerequisite concept before returning to the target.",
                    "misconception_ids": [],
                    "guidance": "Use concrete language, a quick model, and one check-for-understanding.",
                }
            )
        if primary_signal is not None:
            steps.append(
                {
                    "phase": "repair",
                    "title": "Address the specific misconception" if kc_sequence.action != "hold_target" else "Hold on the target reasoning",
                    "target_kc_ids": ordered_repair_targets,
                    "support_level": "high" if steps else "medium",
                    "objective": primary_signal.rationale,
                    "misconception_ids": [primary_signal.misconception_id] if primary_signal.misconception_id else [],
                    "guidance": primary_signal.remediation_hint
                    or "Name the misconception explicitly, contrast it with the correct reasoning, and show one corrected example.",
                    "recurrence_signal": primary_signal.recurrence_signal,
                }
            )
        if ordered_bridge_targets:
            steps.append(
                {
                    "phase": "bridge",
                    "title": "Bridge through a nearby knowledge component",
                    "target_kc_ids": ordered_bridge_targets,
                    "support_level": "medium",
                    "objective": "Reconnect the repaired idea through a nearby knowledge component in the same learning objective before returning to the target.",
                    "misconception_ids": [],
                    "guidance": "Use a closely related example that shares the repaired prerequisite, then fade support before the target transfer check.",
                }
            )
        steps.append(
            {
                "phase": "return",
                "title": "Attempt transfer on the target" if kc_sequence.action == "attempt_transfer" else "Bridge back to the target",
                "target_kc_ids": kc_sequence.deferred_kc_ids or [target_kc_id],
                "support_level": "low" if kc_sequence.action == "attempt_transfer" else ("medium" if steps else "low"),
                "objective": (
                    "Check whether the learner can now transfer the corrected reasoning to the target knowledge component."
                    if kc_sequence.action == "attempt_transfer"
                    else "Reconnect the repaired idea to the requested target knowledge component."
                ),
                "misconception_ids": [],
                "guidance": (
                    "Use one short transfer check that verifies the corrected reasoning now holds on the target task."
                    if kc_sequence.action == "attempt_transfer"
                    else "End with a short transfer prompt that checks whether the corrected reasoning now holds on the target task."
                ),
            }
        )
        return {
            "trigger": "misconception_detected",
            "primary_misconception_id": primary_signal.misconception_id if primary_signal else None,
            "primary_misconception_source": primary_signal.source if primary_signal else None,
            "primary_recurrence_signal": primary_signal.recurrence_signal if primary_signal else "none",
            "repair_target_kc_ids": repair_targets,
            "sequence_action": kc_sequence.action,
            "sequence_primary_kc_id": kc_sequence.primary_kc_id,
            "bridge_target_kc_ids": ordered_bridge_targets,
            "ordered_focus_kc_ids": ordered_focus_kc_ids,
            "deferred_focus_kc_ids": kc_sequence.deferred_kc_ids,
            "steps": steps,
        }
