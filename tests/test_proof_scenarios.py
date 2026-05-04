from __future__ import annotations

from pathlib import Path

from scripts.validate_proof_scenarios import load_scenarios, validate_all


SCENARIO_DIR = Path(__file__).resolve().parents[1] / "proof" / "scenarios"
CANONICAL_SCENARIO_IDS = {
    "new_household_onboarding",
    "adaptive_modality_change",
    "parent_governed_autonomy",
    "cross_session_planning_revision",
    "shared_library_reuse_without_privacy_leakage",
}


def test_canonical_proof_scenarios_are_present() -> None:
    scenario_ids = {
        scenario["scenario_id"] for scenario in load_scenarios(SCENARIO_DIR)
    }

    assert scenario_ids == CANONICAL_SCENARIO_IDS


def test_proof_scenarios_validate_privacy_and_rehearsal_shape() -> None:
    assert validate_all(SCENARIO_DIR) == []
