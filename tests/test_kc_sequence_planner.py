from dibble.models.profile import LearnerStrategySummary
from dibble.services.kc_sequence_planner import KcSequencePlanner


def test_kc_sequence_planner_rebuilds_prerequisite_when_strategy_requires_step_back():
    sequence = KcSequencePlanner().plan(
        strategy_summary=LearnerStrategySummary(
            signal="support_intensive",
            source="strategy_profile",
            recovery_focus="prerequisite_rebuild",
            recommended_next_action="rebuild_prerequisite",
            trajectory_state="relapsing",
        ),
        target_kc_ids=["KC-2"],
        prerequisite_kc_ids=["KC-1"],
        repair_target_kc_ids=["KC-1"],
    )

    assert sequence.action == "rebuild_prerequisite_first"
    assert sequence.primary_kc_id == "KC-1"
    assert sequence.ordered_kc_ids == ["KC-1", "KC-2"]


def test_kc_sequence_planner_attempts_transfer_when_strategy_is_independence_ready():
    sequence = KcSequencePlanner().plan(
        strategy_summary=LearnerStrategySummary(
            signal="independence_ready",
            source="strategy_profile",
            support_bias=1,
            trajectory_state="accelerating",
            recommended_next_action="check_transfer_readiness",
        ),
        target_kc_ids=["KC-2"],
    )

    assert sequence.action == "attempt_transfer"
    assert sequence.primary_kc_id == "KC-2"
    assert sequence.ordered_kc_ids == ["KC-2"]
