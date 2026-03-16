from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import MisconceptionSignal


@dataclass(slots=True)
class RemediationModuleBlueprintBuilder:
    def build(
        self,
        *,
        target_kc_id: str,
        prerequisite_kc_ids: list[str],
        misconception_signals: list[MisconceptionSignal],
    ) -> dict[str, object]:
        primary_profile_signal = next(
            (
                signal
                for signal in misconception_signals
                if signal.source == "profile" and signal.recurrence_signal in {"recurring", "relapsing"}
            ),
            None,
        )
        primary_catalog_signal = next(
            (signal for signal in misconception_signals if signal.source == "catalog" and signal.misconception_id),
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

        steps: list[dict[str, object]] = []
        if prerequisite_kc_ids:
            steps.append(
                {
                    "phase": "step_back",
                    "title": "Rebuild the prerequisite idea",
                    "target_kc_ids": prerequisite_kc_ids,
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
                    "title": "Address the specific misconception",
                    "target_kc_ids": repair_targets,
                    "support_level": "high" if prerequisite_kc_ids else "medium",
                    "objective": primary_signal.rationale,
                    "misconception_ids": [primary_signal.misconception_id] if primary_signal.misconception_id else [],
                    "guidance": primary_signal.remediation_hint
                    or "Name the misconception explicitly, contrast it with the correct reasoning, and show one corrected example.",
                    "recurrence_signal": primary_signal.recurrence_signal,
                }
            )
        steps.append(
            {
                "phase": "return",
                "title": "Bridge back to the target",
                "target_kc_ids": [target_kc_id],
                "support_level": "medium" if prerequisite_kc_ids else "low",
                "objective": "Reconnect the repaired idea to the requested target knowledge component.",
                "misconception_ids": [],
                "guidance": "End with a short transfer prompt that checks whether the corrected reasoning now holds on the target task.",
            }
        )
        return {
            "trigger": "misconception_detected",
            "primary_misconception_id": primary_signal.misconception_id if primary_signal else None,
            "primary_misconception_source": primary_signal.source if primary_signal else None,
            "primary_recurrence_signal": primary_signal.recurrence_signal if primary_signal else "none",
            "repair_target_kc_ids": repair_targets,
            "steps": steps,
        }
