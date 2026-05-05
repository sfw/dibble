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
    "rehearsal_assets",
    "setup_path",
    "execution_path",
    "rehearsal_steps",
    "expected_observations",
    "visible_outcome",
    "observability_hooks",
    "approval_hooks",
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
REQUIRED_TIMELINE_KEYS = {
    "timeline_id",
    "title",
    "proof_focus",
    "rehearsal_assets",
    "household_narrative",
    "phases",
    "review_surfaces",
    "longitudinal_success_criteria",
    "remaining_poc_evidence",
    "privacy_contract",
}
REQUIRED_TIMELINE_PHASE_KEYS = {
    "phase_id",
    "day",
    "scenario_threads",
    "learner_actions",
    "system_expectations",
    "parent_operator_review",
    "content_quality_review",
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


def load_timelines(timeline_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text()) for path in sorted(timeline_dir.glob("*.json"))
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
        "rehearsal_assets",
        "setup_path",
        "execution_path",
        "expected_observations",
        "visible_outcome",
        "observability_hooks",
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


def validate_timeline(timeline: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    timeline_id = str(timeline.get("timeline_id", "<missing>"))
    missing = REQUIRED_TIMELINE_KEYS - set(timeline)
    if missing:
        errors.append(f"{timeline_id}: missing keys {sorted(missing)}")

    for key in [
        "proof_focus",
        "rehearsal_assets",
        "household_narrative",
        "phases",
        "review_surfaces",
        "longitudinal_success_criteria",
        "remaining_poc_evidence",
    ]:
        if not timeline.get(key):
            errors.append(f"{timeline_id}: {key} must not be empty")

    phases = timeline.get("phases", [])
    if not isinstance(phases, list) or not phases:
        errors.append(f"{timeline_id}: phases must not be empty")
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            errors.append(f"{timeline_id}: phase {index} must be an object")
            continue
        missing_phase = REQUIRED_TIMELINE_PHASE_KEYS - set(phase)
        if missing_phase:
            errors.append(
                f"{timeline_id}: phase {index} missing keys {sorted(missing_phase)}"
            )

    privacy_contract = timeline.get("privacy_contract", {})
    if not isinstance(privacy_contract, dict):
        errors.append(f"{timeline_id}: privacy_contract must be an object")
        return errors
    if not privacy_contract.get("container_private_fields"):
        errors.append(f"{timeline_id}: container_private_fields must not be empty")
    external_flows = privacy_contract.get("external_flows", [])
    if not isinstance(external_flows, list) or not external_flows:
        errors.append(f"{timeline_id}: external_flows must not be empty")
        return errors
    for flow in external_flows:
        errors.extend(_validate_external_flow(timeline_id, flow))
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
    repo_root = scenario_dir.resolve().parents[1]
    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id", "<missing>"))
        if scenario_id in seen_ids:
            errors.append(f"{scenario_id}: duplicate scenario_id")
        seen_ids.add(scenario_id)
        errors.extend(validate_scenario(scenario))
        errors.extend(_validate_rehearsal_assets(repo_root, scenario))
    return errors


def validate_timeline_assets(timeline_dir: Path) -> list[str]:
    timelines = load_timelines(timeline_dir)
    errors: list[str] = []
    seen_ids: set[str] = set()
    repo_root = timeline_dir.resolve().parents[1]
    for timeline in timelines:
        timeline_id = str(timeline.get("timeline_id", "<missing>"))
        if timeline_id in seen_ids:
            errors.append(f"{timeline_id}: duplicate timeline_id")
        seen_ids.add(timeline_id)
        errors.extend(validate_timeline(timeline))
        errors.extend(_validate_rehearsal_assets(repo_root, timeline))
    return errors


def _validate_rehearsal_assets(repo_root: Path, scenario: dict[str, Any]) -> list[str]:
    scenario_id = str(scenario.get("scenario_id", "<missing>"))
    assets = scenario.get("rehearsal_assets", [])
    errors: list[str] = []
    if not isinstance(assets, list) or not assets:
        return [f"{scenario_id}: rehearsal_assets must be a non-empty list"]
    for asset in assets:
        if not isinstance(asset, str) or not asset.strip():
            errors.append(f"{scenario_id}: rehearsal asset must be a non-empty string")
            continue
        if not (repo_root / asset).exists():
            errors.append(f"{scenario_id}: rehearsal asset not found: {asset}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Dibble proof scenarios.")
    parser.add_argument(
        "scenario_dir",
        nargs="?",
        default="proof/scenarios",
        help="Directory containing proof scenario JSON files.",
    )
    parser.add_argument(
        "--timeline-dir",
        default="proof/timelines",
        help="Directory containing longitudinal proof timeline JSON files.",
    )
    args = parser.parse_args()
    errors = validate_all(Path(args.scenario_dir))
    timeline_dir = Path(args.timeline_dir)
    if timeline_dir.exists():
        errors.extend(validate_timeline_assets(timeline_dir))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("proof scenarios valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
