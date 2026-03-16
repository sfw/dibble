from __future__ import annotations

from dataclasses import dataclass

from dibble.models.profile import LearnerStrategySummary
from dibble.models.remediation import KcSequenceSummary


@dataclass(slots=True)
class KcSequencePlanner:
    def plan(
        self,
        *,
        strategy_summary: LearnerStrategySummary | None,
        target_kc_ids: list[str],
        prerequisite_kc_ids: list[str] | None = None,
        repair_target_kc_ids: list[str] | None = None,
    ) -> KcSequenceSummary:
        strategy = strategy_summary or LearnerStrategySummary()
        targets = _unique(target_kc_ids)
        prerequisites = [kc_id for kc_id in _unique(prerequisite_kc_ids or []) if kc_id not in targets]
        repair_targets = _unique(repair_target_kc_ids or []) or list(targets)

        if self._should_attempt_transfer(strategy=strategy, prerequisites=prerequisites):
            return KcSequenceSummary(
                action="attempt_transfer",
                primary_kc_id=targets[0] if targets else None,
                ordered_kc_ids=list(targets),
                deferred_kc_ids=[],
                rationale=(
                    strategy.rationale
                    or "Recent strategy signals support testing transfer on the target KC instead of staying in repair."
                ),
            )

        if self._should_rebuild_prerequisite(strategy=strategy, prerequisites=prerequisites):
            ordered = _unique([*prerequisites, *repair_targets, *targets])
            return KcSequenceSummary(
                action="rebuild_prerequisite_first",
                primary_kc_id=ordered[0] if ordered else None,
                ordered_kc_ids=ordered,
                deferred_kc_ids=[kc_id for kc_id in targets if kc_id not in prerequisites],
                rationale=(
                    strategy.rationale
                    or "Recent strategy signals suggest rebuilding the prerequisite KC before returning to the target."
                ),
            )

        lead_targets = [kc_id for kc_id in repair_targets if kc_id not in targets] or list(targets) or list(repair_targets)
        ordered = _unique([*lead_targets, *targets])
        action = "hold_repair_target" if lead_targets and lead_targets[0] not in targets else "hold_target"
        rationale = (
            strategy.rationale
            or (
                "Recent strategy signals suggest staying on the current repair KC before moving back into transfer."
                if action == "hold_repair_target"
                else "Recent strategy signals suggest holding on the target KC until the learner stabilizes."
            )
        )
        return KcSequenceSummary(
            action=action,
            primary_kc_id=ordered[0] if ordered else None,
            ordered_kc_ids=ordered,
            deferred_kc_ids=[kc_id for kc_id in targets if kc_id not in lead_targets],
            rationale=rationale,
        )

    def _should_attempt_transfer(
        self,
        *,
        strategy: LearnerStrategySummary,
        prerequisites: list[str],
    ) -> bool:
        if prerequisites:
            return False
        return strategy.recommended_next_action == "check_transfer_readiness" or (
            strategy.support_bias > 0 and strategy.trajectory_state in {"accelerating", "consolidating"}
        )

    def _should_rebuild_prerequisite(
        self,
        *,
        strategy: LearnerStrategySummary,
        prerequisites: list[str],
    ) -> bool:
        if not prerequisites:
            return False
        if strategy.source == "insufficient":
            return True
        return (
            strategy.recommended_next_action == "rebuild_prerequisite"
            or strategy.recovery_focus == "prerequisite_rebuild"
            or strategy.trajectory_state == "relapsing"
            or strategy.signal == "support_intensive"
        )


def _unique(values: list[str]) -> list[str]:
    deduplicated: list[str] = []
    for value in values:
        if value not in deduplicated:
            deduplicated.append(value)
    return deduplicated
