from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.rehearse_proof_scenarios import (
        ApiClient,
        RehearsalError,
        SCENARIO_IDS,
        SCENARIO_RUNNERS,
        TIMELINE_RUNNERS,
        load_timeline,
        operator_markdown_report,
        readiness_summary,
        require_real_provider,
        seed_runtime,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution path.
    from rehearse_proof_scenarios import (
        ApiClient,
        RehearsalError,
        SCENARIO_IDS,
        SCENARIO_RUNNERS,
        TIMELINE_RUNNERS,
        load_timeline,
        operator_markdown_report,
        readiness_summary,
        require_real_provider,
        seed_runtime,
    )


@dataclass(slots=True)
class ComposeRuntime:
    compose_dir: Path
    service: str

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = ["docker", "compose", *args]
        result = subprocess.run(
            command,
            cwd=self.compose_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RehearsalError(
                f"{' '.join(command)} failed with exit {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return result

    def restart(self) -> None:
        self.run("restart", self.service)

    def stop(self) -> None:
        self.run("stop", self.service)

    def start(self) -> None:
        self.run("start", self.service)

    def copy_from_container(self, container_path: str, host_path: Path) -> None:
        host_path.parent.mkdir(parents=True, exist_ok=True)
        self.run("cp", f"{self.service}:{container_path}", str(host_path))

    def copy_to_container(self, host_path: Path, container_path: str) -> None:
        self.run("cp", str(host_path), f"{self.service}:{container_path}")

    def chown_database(self) -> None:
        self.run("exec", "-u", "root", self.service, "chown", "dibble:dibble", "/data/dibble.db")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run live household proof against the Docker Compose household "
            "container and capture restart, backup, and restore evidence."
        )
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=120.0,
        help="HTTP timeout for proof API calls.",
    )
    parser.add_argument("--compose-dir", default="deploy/household")
    parser.add_argument("--service", default="dibble")
    parser.add_argument("--admin-api-key", default=os.getenv("DIBBLE_PROOF_ADMIN_API_KEY"))
    parser.add_argument(
        "--seed-file",
        default="proof/fixtures/scenario_household_seed.json",
    )
    parser.add_argument(
        "--multi-household-seed-file",
        action="append",
        default=None,
        help=(
            "Additional varied proof household seed to exercise after the canonical "
            "and longitudinal households. Repeat for multiple households."
        ),
    )
    parser.add_argument(
        "--skip-multi-household-evidence",
        action="store_true",
        help="Do not seed and exercise the default additional operator household.",
    )
    parser.add_argument(
        "--timeline-dir",
        default="proof/timelines",
        help="Directory containing longitudinal proof timelines.",
    )
    parser.add_argument(
        "--artifact-dir",
        help="Directory for JSON, Markdown, and SQLite backup artifacts.",
    )
    parser.add_argument(
        "--require-real-provider",
        action="store_true",
        help="Fail unless /ready shows real provider config and mock fallback off.",
    )
    parser.add_argument(
        "--skip-container-ops",
        action="store_true",
        help="Run API proof only; do not restart, back up, or restore the container.",
    )
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir or default_artifact_dir()).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    client = ApiClient(args.base_url, timeout_seconds=args.request_timeout_seconds)
    compose = ComposeRuntime(Path(args.compose_dir), args.service)

    try:
        seed = json.loads(Path(args.seed_file).read_text())
        initial_readiness = client.get("/ready")
        if args.require_real_provider:
            require_real_provider(initial_readiness)
        canonical_state = seed_runtime(
            client=client,
            seed=seed,
            admin_key=args.admin_api_key,
        )
        report: dict[str, Any] = {
            "base_url": args.base_url,
            "household_id": canonical_state.household_id,
            "run_stamp": canonical_state.run_stamp,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pre_seed_readiness": readiness_summary(initial_readiness),
            "readiness": readiness_summary(client.get("/ready")),
            "proof_households": {
                "canonical": canonical_state.household_id,
                "longitudinal": None,
            },
            "scenarios": [],
            "timelines": [],
            "multi_household_evidence": [],
        }
        restart_restore_parent_keys = {
            "canonical": canonical_state.parent_key,
        }

        for scenario_id in SCENARIO_IDS:
            result = SCENARIO_RUNNERS[scenario_id](client, canonical_state)
            report["scenarios"].append({"scenario_id": scenario_id, "result": result})
            print(f"PASS {scenario_id}: {result}")

        longitudinal_state = seed_runtime(
            client=client,
            seed=seed,
            admin_key=canonical_state.admin_key,
        )
        report["proof_households"]["longitudinal"] = longitudinal_state.household_id
        restart_restore_parent_keys["longitudinal"] = longitudinal_state.parent_key
        timeline = load_timeline(Path(args.timeline_dir), "longitudinal_fraction_recovery")
        timeline_result = TIMELINE_RUNNERS["longitudinal_fraction_recovery"](
            client,
            longitudinal_state,
            timeline,
        )
        report["timelines"].append(timeline_result)
        print(
            "PASS longitudinal_fraction_recovery: "
            f"{len(timeline_result['phases'])} phases, "
            f"{len(timeline_result['content_quality_samples'])} samples"
        )

        for extra_index, seed_file in enumerate(multi_household_seed_files(args), start=1):
            evidence = exercise_additional_household(
                client=client,
                seed_file=seed_file,
                admin_key=canonical_state.admin_key,
                label=f"operator_household_{extra_index}",
            )
            restart_restore_parent_keys[evidence["label"]] = evidence["parent_key"]
            report["proof_households"][evidence["label"]] = evidence["household_id"]
            public_evidence = dict(evidence)
            public_evidence.pop("parent_key", None)
            report["multi_household_evidence"].append(public_evidence)
            print(
                f"PASS {evidence['label']}: "
                f"{len(evidence['scenario_results'])} scenario checks, "
                f"privacy_forbidden_hits={evidence['privacy_audit']['forbidden_hit_count']}"
            )

        if not args.skip_container_ops:
            report["live_container_evidence"] = exercise_container_ops(
                client=client,
                compose=compose,
                household_parent_keys=restart_restore_parent_keys,
                backup_path=artifact_dir / "dibble-live-household-backup.db",
            )

        json_path = artifact_dir / "live-household-proof-report.json"
        markdown_path = artifact_dir / "live-household-proof-report.md"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True))
        markdown_path.write_text(operator_markdown_report(report))

        print(f"JSON report: {json_path}")
        print(f"Operator report: {markdown_path}")
        print(f"Backup artifact: {artifact_dir / 'dibble-live-household-backup.db'}")
        return 0
    except RehearsalError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


def default_artifact_dir() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"proof-artifacts/live-household-{stamp}"


def multi_household_seed_files(args: argparse.Namespace) -> list[Path]:
    if args.skip_multi_household_evidence:
        return []
    seed_files = args.multi_household_seed_file or [
        "proof/fixtures/operator_household_seed.json"
    ]
    return [Path(seed_file) for seed_file in seed_files]


def exercise_additional_household(
    *,
    client: ApiClient,
    seed_file: Path,
    admin_key: str,
    label: str,
) -> dict[str, Any]:
    if not seed_file.exists():
        raise RehearsalError(f"Multi-household seed not found: {seed_file}")
    seed = json.loads(seed_file.read_text())
    state = seed_runtime(client=client, seed=seed, admin_key=admin_key)
    scenario_results = []
    for scenario_id in (
        "new_household_onboarding",
        "adaptive_modality_change",
        "shared_library_reuse_without_privacy_leakage",
    ):
        result = SCENARIO_RUNNERS[scenario_id](client, state)
        scenario_results.append({"scenario_id": scenario_id, "result": result})
    audit = client.get(
        "/api/observability/adaptation/library/privacy-audit",
        api_key=state.admin_key,
    )
    forbidden_hits = audit.get("forbidden_field_hits", [])
    if forbidden_hits:
        raise RehearsalError(
            f"Additional household {label} privacy audit found private fields: "
            f"{forbidden_hits}"
        )
    return {
        "label": label,
        "seed_file": str(seed_file),
        "household_id": state.household_id,
        "parent_key": state.parent_key,
        "run_stamp": state.run_stamp,
        "household_name": seed.get("household_name"),
        "learner_aliases": sorted(state.learner_ids),
        "learner_count": len(state.learner_ids),
        "preferences": seed.get("preferences", {}),
        "scenario_results": scenario_results,
        "readiness": readiness_summary(client.get("/ready")),
        "privacy_audit": {
            "entry_count": audit.get("entry_count", 0),
            "forbidden_hit_count": len(forbidden_hits),
        },
    }


def exercise_container_ops(
    *,
    client: ApiClient,
    compose: ComposeRuntime,
    household_parent_keys: dict[str, str],
    backup_path: Path,
) -> dict[str, Any]:
    before_restart = household_signatures(client, household_parent_keys)
    compose.restart()
    restart_ready = wait_for_ready(client)
    after_restart = household_signatures(client, household_parent_keys)
    restart_evidence = {
        "pre_restart_signature": before_restart,
        "post_restart_signature": after_restart,
        "post_restart_ready_status": restart_ready.get("status"),
        "persistence_preserved": before_restart == after_restart,
    }
    if not restart_evidence["persistence_preserved"]:
        raise RehearsalError("Household state changed across Docker restart.")

    compose.stop()
    try:
        compose.copy_from_container("/data/dibble.db", backup_path)
        backup_evidence = file_evidence(backup_path)
        compose.copy_to_container(backup_path, "/data/dibble.db")
    finally:
        compose.start()
    compose.chown_database()
    restore_ready = wait_for_ready(client)
    after_restore = household_signatures(client, household_parent_keys)
    restore_evidence = {
        "post_restore_signature": after_restore,
        "post_restore_ready_status": restore_ready.get("status"),
        "restore_preserved_state": after_restore == after_restart,
    }
    if not restore_evidence["restore_preserved_state"]:
        raise RehearsalError("Household state changed after backup restore.")

    return {
        "restart": restart_evidence,
        "backup": backup_evidence,
        "restore": restore_evidence,
    }


def household_signatures(
    client: ApiClient, household_parent_keys: dict[str, str]
) -> dict[str, Any]:
    return {
        label: household_signature(
            client.get("/api/households/me/overview", api_key=parent_key)
        )
        for label, parent_key in sorted(household_parent_keys.items())
    }


def wait_for_ready(
    client: ApiClient,
    *,
    timeout_seconds: float = 90,
    interval_seconds: float = 2,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            readiness = client.get("/ready")
            if readiness.get("status") in {"ready", "degraded", "setup_required"}:
                return readiness
        except Exception as exc:
            last_error = exc
        time.sleep(interval_seconds)
    if last_error is not None:
        raise RehearsalError(f"Timed out waiting for /ready: {last_error}") from last_error
    raise RehearsalError("Timed out waiting for /ready.")


def household_signature(overview: dict[str, Any]) -> dict[str, Any]:
    household = overview.get("household") or {}
    learners = overview.get("learners") or []
    approvals = overview.get("pending_approvals") or []
    suggestions = overview.get("session_suggestions") or []
    return {
        "household_id": household.get("household_id"),
        "household_name": household.get("display_name") or household.get("name"),
        "learner_ids": sorted(
            str(learner.get("learner_id")) for learner in learners if learner.get("learner_id")
        ),
        "pending_approval_count": len(approvals),
        "session_suggestion_count": len(suggestions),
    }


def file_evidence(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
