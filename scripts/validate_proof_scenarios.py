from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_SCENARIO_KEYS = {
    "scenario_id",
    "title",
    "proof_focus",
    "entrypoints",
    "preconditions",
    "rehearsal_steps",
    "expected_observations",
    "privacy_contract",
    "success_criteria",
    "reset_notes",
}
REQUIRED_STEP_KEYS = {
    "step_id",
    "actor",
    "surface",
    "action",
    "expected_observation",
    "proof_signal",
}
PRIVATE_FIELD_TOKENS = {
    "learner_id",
    "student_id",
    "household_id",
    "parent_user_id",
    "session_id",
    "learning_session_id",
    "profile",
    "observation",
    "response_text",
    "relationship_state",
    "parent_preferences",
}


def load_scenarios(scenario_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text()) for path in sorted(scenario_dir.glob("*.json"))
    ]


def validate_scenario(scenario: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scenario_id = str(scenario.get("scenario_id", "<missing>"))
    missing = REQUIRED_SCENARIO_KEYS - set(scenario)
    if missing:
        errors.append(f"{scenario_id}: missing keys {sorted(missing)}")

    for key in [
        "proof_focus",
        "entrypoints",
        "preconditions",
        "expected_observations",
        "success_criteria",
    ]:
        if not scenario.get(key):
            errors.append(f"{scenario_id}: {key} must not be empty")

    steps = scenario.get("rehearsal_steps", [])
    if not isinstance(steps, list) or not steps:
        errors.append(f"{scenario_id}: rehearsal_steps must not be empty")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"{scenario_id}: step {index} must be an object")
            continue
        missing_step = REQUIRED_STEP_KEYS - set(step)
        if missing_step:
            errors.append(
                f"{scenario_id}: step {index} missing keys {sorted(missing_step)}"
            )

    privacy_contract = scenario.get("privacy_contract", {})
    if not isinstance(privacy_contract, dict):
        errors.append(f"{scenario_id}: privacy_contract must be an object")
        return errors
    if not privacy_contract.get("container_private_fields"):
        errors.append(f"{scenario_id}: container_private_fields must not be empty")
    external_flows = privacy_contract.get("external_flows", [])
    if not isinstance(external_flows, list) or not external_flows:
        errors.append(f"{scenario_id}: external_flows must not be empty")
        return errors
    for flow in external_flows:
        errors.extend(_validate_external_flow(scenario_id, flow))
    return errors


def _validate_external_flow(scenario_id: str, flow: Any) -> list[str]:
    if not isinstance(flow, dict):
        return [f"{scenario_id}: external flow must be an object"]
    destination = flow.get("destination", "<missing>")
    allowed = set(flow.get("allowed_fields", []))
    forbidden = set(flow.get("forbidden_fields", []))
    errors: list[str] = []
    if not allowed:
        errors.append(f"{scenario_id}: {destination} allowed_fields must not be empty")
    if not forbidden:
        errors.append(
            f"{scenario_id}: {destination} forbidden_fields must not be empty"
        )
    overlap = allowed & forbidden
    if overlap:
        errors.append(
            f"{scenario_id}: {destination} allows forbidden fields {sorted(overlap)}"
        )
    unsafe_allowed = {
        field
        for field in allowed
        if any(token in field for token in PRIVATE_FIELD_TOKENS)
    }
    if unsafe_allowed:
        errors.append(
            f"{scenario_id}: {destination} allows private-looking fields "
            f"{sorted(unsafe_allowed)}"
        )
    return errors


def validate_all(scenario_dir: Path) -> list[str]:
    scenarios = load_scenarios(scenario_dir)
    errors: list[str] = []
    seen_ids: set[str] = set()
    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id", "<missing>"))
        if scenario_id in seen_ids:
            errors.append(f"{scenario_id}: duplicate scenario_id")
        seen_ids.add(scenario_id)
        errors.extend(validate_scenario(scenario))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Dibble proof scenarios.")
    parser.add_argument(
        "scenario_dir",
        nargs="?",
        default="proof/scenarios",
        help="Directory containing proof scenario JSON files.",
    )
    args = parser.parse_args()
    errors = validate_all(Path(args.scenario_dir))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("proof scenarios valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
