from __future__ import annotations

from dibble.models.profile import LearnerStrategySummary
from dibble.models.remediation import KcSequenceSummary
from dibble.services.knowledge_component_graph import KnowledgeComponentGraph
from dibble.services.protocols import KnowledgeComponentStore


class KcSequencePlanner:
    def __init__(
        self,
        knowledge_component_store: KnowledgeComponentStore | None = None,
        *,
        maximum_bridge_kc_ids: int = 2,
    ) -> None:
        self.knowledge_component_store = knowledge_component_store
        self.maximum_bridge_kc_ids = maximum_bridge_kc_ids

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
        bridge_kc_ids = self._bridge_kc_ids(
            target_kc_ids=targets,
            prerequisite_kc_ids=prerequisites,
            repair_target_kc_ids=repair_targets,
        )

        if self._should_attempt_transfer(strategy=strategy, prerequisites=prerequisites):
            return KcSequenceSummary(
                action="attempt_transfer",
                primary_kc_id=targets[0] if targets else None,
                ordered_kc_ids=list(targets),
                bridge_kc_ids=[],
                deferred_kc_ids=[],
                rationale=(
                    strategy.rationale
                    or "Recent strategy signals support testing transfer on the target KC instead of staying in repair."
                ),
            )

        if self._should_rebuild_prerequisite(strategy=strategy, prerequisites=prerequisites):
            repair_phase_targets = [
                kc_id for kc_id in repair_targets if kc_id not in prerequisites and kc_id not in bridge_kc_ids
            ]
            ordered = _unique([*prerequisites, *repair_phase_targets, *bridge_kc_ids, *targets])
            return KcSequenceSummary(
                action="rebuild_prerequisite_first",
                primary_kc_id=ordered[0] if ordered else None,
                ordered_kc_ids=ordered,
                bridge_kc_ids=bridge_kc_ids,
                deferred_kc_ids=[kc_id for kc_id in targets if kc_id not in prerequisites and kc_id not in bridge_kc_ids],
                rationale=self._sequence_rationale(
                    strategy_rationale=strategy.rationale,
                    fallback="Recent strategy signals suggest rebuilding the prerequisite KC before returning to the target.",
                    bridge_kc_ids=bridge_kc_ids,
                ),
            )

        lead_targets = [kc_id for kc_id in repair_targets if kc_id not in targets] or list(targets) or list(repair_targets)
        bridge_kc_ids = bridge_kc_ids if lead_targets and lead_targets[0] not in targets else []
        ordered = _unique([*lead_targets, *bridge_kc_ids, *targets])
        action = "hold_repair_target" if lead_targets and lead_targets[0] not in targets else "hold_target"
        fallback_rationale = (
            "Recent strategy signals suggest staying on the current repair KC before moving back into transfer."
            if action == "hold_repair_target"
            else "Recent strategy signals suggest holding on the target KC until the learner stabilizes."
        )
        rationale = self._sequence_rationale(
            strategy_rationale=strategy.rationale,
            fallback=fallback_rationale,
            bridge_kc_ids=bridge_kc_ids,
        )
        return KcSequenceSummary(
            action=action,
            primary_kc_id=ordered[0] if ordered else None,
            ordered_kc_ids=ordered,
            bridge_kc_ids=bridge_kc_ids,
            deferred_kc_ids=[kc_id for kc_id in targets if kc_id not in lead_targets and kc_id not in bridge_kc_ids],
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

    def _bridge_kc_ids(
        self,
        *,
        target_kc_ids: list[str],
        prerequisite_kc_ids: list[str],
        repair_target_kc_ids: list[str],
    ) -> list[str]:
        if self.knowledge_component_store is None or not target_kc_ids:
            return []
        components = self.knowledge_component_store.list()
        if not components:
            return []
        graph = KnowledgeComponentGraph(components)
        anchor_kc_ids = _unique([*prerequisite_kc_ids, *repair_target_kc_ids])
        bridge_kc_ids: list[str] = []
        for target_kc_id in target_kc_ids:
            for relation in graph.bridge_candidates_for(
                target_kc_id,
                anchor_kc_ids=anchor_kc_ids,
                limit=self.maximum_bridge_kc_ids,
            ):
                if relation.component.kc_id not in bridge_kc_ids:
                    bridge_kc_ids.append(relation.component.kc_id)
        return bridge_kc_ids[: self.maximum_bridge_kc_ids]

    def _sequence_rationale(
        self,
        *,
        strategy_rationale: str | None,
        fallback: str,
        bridge_kc_ids: list[str],
    ) -> str:
        rationale = strategy_rationale or fallback
        if not bridge_kc_ids:
            return rationale
        bridge_fragment = ", ".join(bridge_kc_ids)
        return f"{rationale} Use nearby bridge KC(s) {bridge_fragment} before returning fully to the target."


def _unique(values: list[str]) -> list[str]:
    deduplicated: list[str] = []
    for value in values:
        if value not in deduplicated:
            deduplicated.append(value)
    return deduplicated
