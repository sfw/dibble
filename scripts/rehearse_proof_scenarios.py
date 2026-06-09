from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


SCENARIO_IDS = (
    "new_household_onboarding",
    "adaptive_modality_change",
    "parent_governed_autonomy",
    "cross_session_planning_revision",
    "shared_library_reuse_without_privacy_leakage",
)
TIMELINE_IDS = ("longitudinal_fraction_recovery",)


class RehearsalError(RuntimeError):
    pass


class ApiError(RehearsalError):
    def __init__(self, method: str, path: str, status: int, body: str) -> None:
        super().__init__(f"{method} {path} returned HTTP {status}: {body}")
        self.status = status
        self.body = body


@dataclass(slots=True)
class ApiClient:
    base_url: str
    timeout_seconds: float = 120.0

    def request(
        self,
        method: str,
        path: str,
        *,
        api_key: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if api_key:
            headers["X-API-Key"] = api_key
        request = Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp is not None else ""
            raise ApiError(method, path, exc.code, raw) from exc
        except URLError as exc:
            raise RehearsalError(f"Could not reach {url}: {exc.reason}") from exc
        if not raw.strip():
            return {}
        return json.loads(raw)

    def get(self, path: str, *, api_key: str | None = None) -> Any:
        return self.request("GET", path, api_key=api_key)

    def post(
        self,
        path: str,
        *,
        api_key: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return self.request("POST", path, api_key=api_key, payload=payload or {})

    def put(self, path: str, *, api_key: str | None, payload: dict[str, Any]) -> Any:
        return self.request("PUT", path, api_key=api_key, payload=payload)


@dataclass(slots=True)
class RuntimeState:
    admin_key: str
    parent_key: str
    parent_user_id: str
    learner_ids: dict[str, str]
    learner_keys: dict[str, str]
    household_id: str
    run_stamp: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed and rehearse Dibble canonical proof scenarios."
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=120.0,
        help="HTTP timeout for proof API calls.",
    )
    parser.add_argument(
        "--admin-api-key",
        default=os.getenv("DIBBLE_PROOF_ADMIN_API_KEY"),
        help="Existing admin key. If omitted, the script tries first-run admin setup.",
    )
    parser.add_argument(
        "--seed-file",
        default="proof/fixtures/scenario_household_seed.json",
    )
    parser.add_argument(
        "--timeline-dir",
        default="proof/timelines",
        help="Directory containing longitudinal proof timelines.",
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIO_IDS,
        action="append",
        help="Run one scenario. Repeat for multiple. Defaults to all five.",
    )
    parser.add_argument(
        "--timeline",
        choices=TIMELINE_IDS,
        action="append",
        help=(
            "Run one longitudinal timeline. Repeat for multiple. If provided "
            "without --scenario, only timelines run."
        ),
    )
    parser.add_argument(
        "--summary-file",
        help="Optional path for a JSON rehearsal report for operator review.",
    )
    parser.add_argument(
        "--operator-report-file",
        help="Optional path for a Markdown report for operator handoff.",
    )
    parser.add_argument(
        "--require-real-provider",
        action="store_true",
        help=(
            "Fail unless /ready shows primary provider credentials configured and "
            "mock fallback disabled."
        ),
    )
    args = parser.parse_args()

    client = ApiClient(args.base_url, timeout_seconds=args.request_timeout_seconds)
    seed = json.loads(Path(args.seed_file).read_text())
    timelines = tuple(args.timeline or ())
    scenarios = tuple(args.scenario or (() if timelines else SCENARIO_IDS))

    try:
        initial_readiness = client.get("/ready")
        if args.require_real_provider:
            require_real_provider(initial_readiness)
        state = seed_runtime(client=client, seed=seed, admin_key=args.admin_api_key)
        report: dict[str, Any] = {
            "base_url": args.base_url,
            "household_id": state.household_id,
            "run_stamp": state.run_stamp,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pre_seed_readiness": readiness_summary(initial_readiness),
            "readiness": readiness_summary(client.get("/ready")),
            "scenarios": [],
            "timelines": [],
        }
        for scenario_id in scenarios:
            result = SCENARIO_RUNNERS[scenario_id](client, state)
            report["scenarios"].append({"scenario_id": scenario_id, "result": result})
            print(f"PASS {scenario_id}: {result}")
        for timeline_id in timelines:
            timeline = load_timeline(Path(args.timeline_dir), timeline_id)
            result = TIMELINE_RUNNERS[timeline_id](client, state, timeline)
            report["timelines"].append(result)
            print(
                f"PASS {timeline_id}: "
                f"{len(result['phases'])} phases, "
                f"{len(result['content_quality_samples'])} samples"
            )
        if args.summary_file:
            Path(args.summary_file).write_text(
                json.dumps(report, indent=2, sort_keys=True)
            )
            print(f"Summary report: {args.summary_file}")
        if args.operator_report_file:
            Path(args.operator_report_file).write_text(operator_markdown_report(report))
            print(f"Operator report: {args.operator_report_file}")
        print()
        print("Proof rehearsal complete.")
        print(f"Admin key: {state.admin_key}")
        print(f"Parent key: {state.parent_key}")
        for alias, learner_id in state.learner_ids.items():
            print(f"{alias} learner id: {learner_id}")
        return 0
    except RehearsalError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


def load_timeline(timeline_dir: Path, timeline_id: str) -> dict[str, Any]:
    path = timeline_dir / f"{timeline_id}.json"
    if not path.exists():
        raise RehearsalError(f"Timeline asset not found: {path}")
    timeline = json.loads(path.read_text())
    if timeline.get("timeline_id") != timeline_id:
        raise RehearsalError(
            f"Timeline {path} declares id {timeline.get('timeline_id')!r}."
        )
    return timeline


def readiness_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    checks = readiness.get("checks", [])
    llm_check = next(
        (check for check in checks if check.get("key") == "llm_provider"),
        {},
    )
    failed = [check.get("key") for check in checks if check.get("status") == "fail"]
    warnings = [check.get("key") for check in checks if check.get("status") == "warn"]
    return {
        "status": readiness.get("status"),
        "deployment_mode": readiness.get("deployment_mode"),
        "configured": bool(readiness.get("configured")),
        "has_admin_user": bool(readiness.get("has_admin_user")),
        "mock_fallback_enabled": bool(readiness.get("mock_fallback_enabled")),
        "cloud_library_enabled": bool(readiness.get("cloud_library_enabled")),
        "llm_provider_status": llm_check.get("status"),
        "llm_provider_summary": llm_check.get("summary"),
        "failed_checks": failed,
        "warning_checks": warnings,
        "next_steps": readiness.get("next_steps", []),
    }


def require_real_provider(readiness: dict[str, Any]) -> None:
    summary = readiness_summary(readiness)
    if summary["llm_provider_status"] != "pass":
        raise RehearsalError(
            "Real-provider proof requires /ready llm_provider=pass. "
            f"Observed {summary['llm_provider_status']}: "
            f"{summary['llm_provider_summary']}"
        )
    if summary["mock_fallback_enabled"]:
        raise RehearsalError(
            "Real-provider proof requires DIBBLE_LLM_ALLOW_MOCK_FALLBACK=false "
            "so provider failures cannot silently become mock generations."
        )


def operator_markdown_report(report: dict[str, Any]) -> str:
    readiness = report.get("readiness") or report.get("initial_readiness") or {}
    lines = [
        "# Dibble Live Household Proof Report",
        "",
        f"- Generated: {report.get('generated_at', '<unknown>')}",
        f"- Base URL: {report.get('base_url', '<unknown>')}",
        f"- Household ID: {report.get('household_id', '<unknown>')}",
        f"- Run stamp: {report.get('run_stamp', '<unknown>')}",
        "",
        "## Readiness",
        "",
        f"- Status: {readiness.get('status', '<unknown>')}",
        f"- Deployment mode: {readiness.get('deployment_mode', '<unknown>')}",
        f"- LLM provider: {readiness.get('llm_provider_status', '<unknown>')} "
        f"({readiness.get('llm_provider_summary', 'no summary')})",
        f"- Mock fallback enabled: {readiness.get('mock_fallback_enabled', '<unknown>')}",
        f"- Cloud library enabled: {readiness.get('cloud_library_enabled', '<unknown>')}",
    ]
    lines.extend(
        [
            "",
            "## How To Read This Report",
            "",
            "- `ready=ready` means startup and configuration checks passed for this proof posture.",
            "- Pending approvals are expected in guided mode; they are a parent-control signal, not a failure.",
            "- Planning revisions and recent signals should increase after learner evidence accumulates.",
            "- Degraded traces require review when they point to provider failure, privacy, persistence, or blocked learner delivery.",
            "- A real-provider proof must show `Mock fallback enabled: False`.",
        ]
    )
    if readiness.get("failed_checks"):
        lines.append(f"- Failed checks: {', '.join(readiness['failed_checks'])}")
    if readiness.get("warning_checks"):
        lines.append(f"- Warning checks: {', '.join(readiness['warning_checks'])}")
    if readiness.get("next_steps"):
        lines.extend(["", "Next steps from `/ready`:"])
        lines.extend(f"- {step}" for step in readiness["next_steps"])
    proof_households = report.get("proof_households") or {}
    if proof_households:
        lines.extend(["", "Proof households:"])
        for label, household_id in proof_households.items():
            lines.append(f"- {label}: {household_id}")

    multi_household = report.get("multi_household_evidence") or []
    if multi_household:
        lines.extend(["", "## Multi-Household Evidence", ""])
        lines.append(
            "These checks exercise an additional seeded household through public API "
            "proof paths so the report is not only true for the first canonical household."
        )
        lines.append("")
        for item in multi_household:
            readiness_summary = item.get("readiness") or {}
            audit = item.get("privacy_audit") or {}
            lines.append(
                f"- {item.get('label', '<unknown>')}: "
                f"{item.get('household_name', '<unnamed>')} "
                f"({item.get('learner_count', 0)} learners), "
                f"ready={readiness_summary.get('status', '<unknown>')}, "
                f"privacy_forbidden_hits={audit.get('forbidden_hit_count', '<unknown>')}"
            )
            for scenario in item.get("scenario_results", []):
                lines.append(
                    f"  - {scenario.get('scenario_id', '<unknown>')}: "
                    f"{scenario.get('result', '<no result>')}"
                )

    scenarios = report.get("scenarios") or []
    if scenarios:
        lines.extend(["", "## Canonical Scenarios", ""])
        for scenario in scenarios:
            lines.append(
                f"- {scenario.get('scenario_id', '<unknown>')}: "
                f"{scenario.get('result', '<no result>')}"
            )

    timelines = report.get("timelines") or []
    if timelines:
        lines.extend(["", "## Longitudinal Timelines", ""])
        for timeline in timelines:
            lines.append(
                f"### {timeline.get('title', timeline.get('timeline_id', '<unknown>'))}"
            )
            lines.append("")
            for phase in timeline.get("phases", []):
                checkpoint = phase.get("review_checkpoint") or {}
                lines.append(
                    f"- {phase.get('phase_id', '<unknown>')}: "
                    f"ready={checkpoint.get('ready_status', '<unknown>')}, "
                    f"approvals={checkpoint.get('pending_approval_count', 0)}, "
                    f"planning_revisions={checkpoint.get('planning_revision_count', 0)}, "
                    f"signals={checkpoint.get('recent_signal_count', 0)}"
                )
                lines.append(f"  Proof signal: {phase.get('proof_signal', '')}")
            samples = timeline.get("content_quality_samples") or []
            lines.append("")
            lines.append(f"Content samples captured: {len(samples)}")
            for sample in samples:
                checklist = sample.get("review_checklist") or {}
                checklist_labels = ", ".join(checklist) if checklist else "not recorded"
                lines.append(
                    f"- {sample.get('phase_id')}/{sample.get('learner_alias')}: "
                    f"{sample.get('generation_id')} "
                    f"modality={sample.get('modality')} "
                    f"cache_hit={sample.get('cache_hit')} "
                    f"review={checklist_labels}"
                )
                if sample.get("review_note"):
                    lines.append(f"  Note: {sample['review_note']}")
            audit = timeline.get("privacy_audit") or {}
            if audit:
                lines.append(
                    f"Privacy audit: entries={audit.get('entry_count', 0)}, "
                    f"forbidden_hits={len(audit.get('forbidden_field_hits', []))}"
                )

    live_ops = report.get("live_container_evidence")
    if live_ops:
        lines.extend(["", "## Live Container Evidence", ""])
        restart = live_ops.get("restart") or {}
        backup = live_ops.get("backup") or {}
        restore = live_ops.get("restore") or {}
        lines.append(
            f"- Restart preserved household state: "
            f"{restart.get('persistence_preserved', '<unknown>')}"
        )
        signatures = restart.get("pre_restart_signature")
        if isinstance(signatures, dict):
            if all(isinstance(value, dict) for value in signatures.values()):
                checked = ", ".join(sorted(signatures))
            else:
                checked = "single household signature"
            lines.append(f"- Restart/restore household labels checked: {checked}")
        if backup:
            lines.append(
                f"- Backup: {backup.get('path')} "
                f"({backup.get('size_bytes', 0)} bytes, sha256={backup.get('sha256')})"
            )
        if restore:
            lines.append(
                f"- Restore preserved household state: "
                f"{restore.get('restore_preserved_state', '<unknown>')}"
            )
            lines.append(
                f"- Post-restore readiness: "
                f"{restore.get('post_restore_ready_status', '<unknown>')}"
            )

    lines.extend(
        [
            "",
            "## Operator Review Checklist",
            "",
            "- Confirm `/ready` is acceptable for the intended run posture.",
            "- Confirm real-provider proof has mock fallback disabled.",
            "- Review generated content samples using curriculum fit, misconception targeting, age fit, privacy, and actionability.",
            "- Confirm at least two household labels appear when claiming multi-household proof.",
            "- Confirm restart and restore evidence are present before learner use.",
            "- Record any confusing wording or ambiguous next action as operator friction, even when the proof passes.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def seed_runtime(
    *, client: ApiClient, seed: dict[str, Any], admin_key: str | None
) -> RuntimeState:
    client.get("/ready")
    if not admin_key:
        admin_key = create_initial_admin(client)
    parent = client.post(
        "/api/users",
        api_key=admin_key,
        payload=seed["parent"],
    )
    parent_key = required(parent, "credential")
    parent_user_id = required(parent, "user_id")

    upsert_curriculum(client=client, admin_key=admin_key, seed=seed)
    learner_ids: dict[str, str] = {}
    learner_keys: dict[str, str] = {}
    for learner_seed in seed["learners"]:
        learner = client.post(
            "/api/users",
            api_key=admin_key,
            payload={
                "display_name": learner_seed["display_name"],
                "role": "learner",
            },
        )
        alias = learner_seed["alias"]
        learner_id = learner.get("learner_id") or lookup_learner_id(
            client=client,
            admin_key=admin_key,
            user_id=required(learner, "user_id"),
        )
        learner_ids[alias] = learner_id
        learner_keys[alias] = required(learner, "credential")
        profile_payload = {
            "student_id": learner_id,
            **learner_seed["profile"],
        }
        client.put(
            f"/api/learners/{learner_id}/profile",
            api_key=admin_key,
            payload=profile_payload,
        )

    household = client.put(
        "/api/households/me/setup",
        api_key=parent_key,
        payload={
            "household_name": seed["household_name"],
            "learner_ids": list(learner_ids.values()),
            "relationship_label": "parent",
            "preferences": seed["preferences"],
        },
    )
    household_id = required(required(household, "household"), "household_id")
    for learner_id in learner_ids.values():
        client.post(
            f"/api/households/me/learners/{learner_id}/goals",
            api_key=parent_key,
            payload={
                "title": "Proof goal: equivalent fractions",
                "target_outcome_id": "PROOF-FRAC-2",
                "target_kc_ids": ["KC-FRAC-EQUIV"],
                "rationale": "Canonical proof rehearsal seed.",
            },
        )

    return RuntimeState(
        admin_key=admin_key,
        parent_key=parent_key,
        parent_user_id=parent_user_id,
        learner_ids=learner_ids,
        learner_keys=learner_keys,
        household_id=household_id,
        run_stamp=uuid4().hex[:8],
    )


def create_initial_admin(client: ApiClient) -> str:
    try:
        response = client.post(
            "/api/setup/admin",
            payload={"display_name": "Proof Rehearsal Operator"},
        )
        return required(response, "api_key")
    except ApiError as exc:
        if exc.status == 409:
            raise RehearsalError(
                "An admin already exists. Pass --admin-api-key or set "
                "DIBBLE_PROOF_ADMIN_API_KEY."
            ) from exc
        raise


def lookup_learner_id(*, client: ApiClient, admin_key: str, user_id: str) -> str:
    user = client.get(f"/api/users/{user_id}", api_key=admin_key)
    learner_id = user.get("learner_id")
    if not isinstance(learner_id, str) or not learner_id:
        raise RehearsalError(f"User {user_id} did not receive a learner_id.")
    return learner_id


def upsert_curriculum(
    *, client: ApiClient, admin_key: str, seed: dict[str, Any]
) -> None:
    curriculum = seed["curriculum"]
    for outcome in curriculum["outcomes"]:
        client.put(
            f"/api/curriculum/outcomes/{outcome['outcome_id']}",
            api_key=admin_key,
            payload=outcome,
        )
    for component in curriculum["knowledge_components"]:
        client.put(
            f"/api/knowledge-components/{component['kc_id']}",
            api_key=admin_key,
            payload=component,
        )


def run_onboarding(client: ApiClient, state: RuntimeState) -> str:
    readiness = client.get("/ready")
    overview = client.get("/api/households/me/overview", api_key=state.parent_key)
    if overview.get("household", {}).get("household_id") != state.household_id:
        raise RehearsalError("Household overview did not return the seeded household.")
    observed_ids = {item["learner_id"] for item in overview.get("learners", [])}
    if not set(state.learner_ids.values()).issubset(observed_ids):
        raise RehearsalError("Household overview is missing seeded learners.")
    if readiness.get("status") not in {"ready", "degraded", "setup_required"}:
        raise RehearsalError(f"Unexpected readiness status {readiness.get('status')}.")
    return (
        f"overview shows {len(observed_ids)} learners and "
        f"readiness is {readiness.get('status')}"
    )


def run_adaptive_modality(client: ApiClient, state: RuntimeState) -> str:
    learner_id = state.learner_ids["avery"]
    first = generate(
        client=client,
        api_key=state.learner_keys["avery"],
        learner_id=learner_id,
        content_type="practice_problem",
        intent="practice",
        context=["Equivalent fractions practice with number sentences."],
    )
    first_modality = content_modality(first)
    for _ in range(2):
        observe(
            client=client,
            api_key=state.learner_keys["avery"],
            learner_id=learner_id,
            generation=first,
            quality="weak",
        )
    inspection = client.post(
        "/api/observability/adaptation/modality-routing/inspect",
        api_key=state.admin_key,
        payload=generation_payload(
            learner_id=learner_id,
            content_type="worked_example",
            intent="explanation",
            context=[
                "Equivalent fractions with visual area models and diagram cues.",
            ],
        ),
    )
    follow_up = generate(
        client=client,
        api_key=state.learner_keys["avery"],
        learner_id=learner_id,
        content_type="worked_example",
        intent="explanation",
        context=[
            "Equivalent fractions with visual area models and diagram cues.",
        ],
    )
    follow_up_modality = content_modality(follow_up)
    observe(
        client=client,
        api_key=state.learner_keys["avery"],
        learner_id=learner_id,
        generation=follow_up,
        quality="strong",
    )
    effective = inspection.get("effective_plugin_id")
    if first_modality == follow_up_modality and not inspection.get(
        "policy_fallback_applied"
    ):
        raise RehearsalError(
            "Follow-up content did not change modality and no policy fallback was "
            f"shown. first={first_modality}, follow_up={follow_up_modality}, "
            f"inspected={inspection.get('effective_plugin_id')}."
        )
    return f"{first_modality} -> {follow_up_modality}; inspected effective={effective}"


def run_parent_governed_autonomy(client: ApiClient, state: RuntimeState) -> str:
    learner_id = state.learner_ids["avery"]
    overview = client.get("/api/households/me/overview", api_key=state.parent_key)
    approvals = overview.get("pending_approvals", [])
    if not approvals:
        raise RehearsalError("No pending parent approvals were visible.")
    approval = approvals[0]
    approval_id = required(approval, "approval_id")
    preview = client.get(
        f"/api/households/me/approvals/{learner_id}/{approval_id}/preview",
        api_key=state.parent_key,
    )
    rejected = client.post(
        f"/api/households/me/approvals/{learner_id}/{approval_id}/reject",
        api_key=state.parent_key,
    )
    explanation = client.get(
        "/api/observability/adaptation/autonomous-teacher/"
        f"{state.household_id}/{learner_id}/explain",
        api_key=state.admin_key,
    )
    approved = client.post(
        f"/api/households/me/approvals/{learner_id}/{approval_id}/approve",
        api_key=state.parent_key,
    )
    for pending in list(approved.get("pending_approvals", [])):
        if pending.get("learner_id") == learner_id:
            approved = client.post(
                "/api/households/me/approvals/"
                f"{learner_id}/{pending['approval_id']}/approve",
                api_key=state.parent_key,
            )
    if rejected.get("session_suggestions"):
        raise RehearsalError("Rejected approval still allowed a session suggestion.")
    if not preview.get("if_approved") or not preview.get("if_denied"):
        raise RehearsalError("Approval preview did not explain both outcomes.")
    return (
        f"rejected then approved {approval.get('approval_type')}; "
        f"explanation={explanation.get('fallback_behavior') or 'available'}"
    )


def run_cross_session_planning(client: ApiClient, state: RuntimeState) -> str:
    learner_id = state.learner_ids["avery"]
    before = client.get(
        f"/api/observability/adaptation/planning/{learner_id}",
        api_key=state.admin_key,
    )
    before_revisions = len(before.get("trajectory", {}).get("revisions", []))
    sequence = [
        ("practice", "practice_problem", "weak"),
        ("practice", "practice_problem", "weak"),
        ("remediation", "remedial_micro_module", "strong"),
        ("practice", "practice_problem", "weak"),
        ("remediation", "remedial_micro_module", "strong"),
    ]
    for intent, content_type, quality in sequence:
        generated = generate(
            client=client,
            api_key=state.learner_keys["avery"],
            learner_id=learner_id,
            content_type=content_type,
            intent=intent,
            context=[
                "Equivalent fractions cross-session planning rehearsal.",
                "Use visual models for recovery steps.",
            ],
        )
        observe(
            client=client,
            api_key=state.learner_keys["avery"],
            learner_id=learner_id,
            generation=generated,
            quality=quality,
        )
    client.get(f"/api/learners/{learner_id}/workspace", api_key=state.admin_key)
    after = client.get(
        f"/api/observability/adaptation/planning/{learner_id}",
        api_key=state.admin_key,
    )
    trajectory = after.get("trajectory") or {}
    adaptation = trajectory.get("adaptation_state") or {}
    after_revisions = len(trajectory.get("revisions", []))
    revisit_density = adaptation.get("active_revisit_density", 1)
    node_kinds = [node.get("node_kind") for node in trajectory.get("nodes", [])]
    if after_revisions <= before_revisions and revisit_density <= 1:
        raise RehearsalError("Planning state did not revise after repeated outcomes.")
    return (
        f"revisions {before_revisions}->{after_revisions}; "
        f"revisit_density={revisit_density}; nodes={node_kinds[:2]}"
    )


def run_shared_library(client: ApiClient, state: RuntimeState) -> str:
    source_alias = "reuse_source" if "reuse_source" in state.learner_ids else "avery"
    peer_alias = "reuse_peer" if "reuse_peer" in state.learner_ids else "blair"
    context = [
        f"Equivalent fractions library reuse rehearsal {state.run_stamp}.",
        "Use curriculum-shaped visual model language only.",
    ]
    first = generate(
        client=client,
        api_key=state.learner_keys[source_alias],
        learner_id=state.learner_ids[source_alias],
        content_type="worked_example",
        intent="explanation",
        context=context,
    )
    second = generate(
        client=client,
        api_key=state.learner_keys[peer_alias],
        learner_id=state.learner_ids[peer_alias],
        content_type="worked_example",
        intent="explanation",
        context=context,
    )
    audit = client.get(
        "/api/observability/adaptation/library/privacy-audit",
        api_key=state.admin_key,
    )
    if audit.get("entry_count", 0) <= 0:
        raise RehearsalError("Library privacy audit found no reusable entries.")
    if audit.get("forbidden_field_hits"):
        raise RehearsalError(
            "Library privacy audit found private fields: "
            f"{audit['forbidden_field_hits']}"
        )
    second_cache_hit = bool((second.get("quality") or {}).get("cache_hit"))
    if not second_cache_hit:
        raise RehearsalError(
            f"{peer_alias} did not reuse {source_alias}'s library artifact."
        )
    return (
        f"{source_alias} generation={first.get('generation_id')}; "
        f"{peer_alias} cache_hit={second_cache_hit}; "
        f"audit_entries={audit['entry_count']}"
    )


def run_longitudinal_fraction_recovery(
    client: ApiClient, state: RuntimeState, timeline: dict[str, Any]
) -> dict[str, Any]:
    learner_id = state.learner_ids["avery"]
    learner_key = state.learner_keys["avery"]
    report: dict[str, Any] = {
        "timeline_id": timeline["timeline_id"],
        "title": timeline["title"],
        "phases": [],
        "content_quality_samples": [],
        "privacy_audit": None,
    }

    day_0 = review_checkpoint(
        client=client,
        state=state,
        phase_id="day-0-baseline",
        learner_id=learner_id,
    )
    first_decision = resolve_one_approval(
        client=client,
        state=state,
        learner_id=learner_id,
        decision="reject",
    )
    report["phases"].append(
        phase_result(
            phase_id="day-0-baseline",
            checkpoint=day_0,
            parent_decisions=[first_decision] if first_decision else [],
            proof_signal="Governance was visible before learner delivery.",
        )
    )

    baseline = generate(
        client=client,
        api_key=learner_key,
        learner_id=learner_id,
        content_type="practice_problem",
        intent="practice",
        context=[
            "Longitudinal Day 1 equivalent fractions baseline practice.",
            "Keep content curriculum-shaped for operator review.",
        ],
    )
    for _ in range(2):
        observe(
            client=client,
            api_key=learner_key,
            learner_id=learner_id,
            generation=baseline,
            quality="weak",
        )
    inspection = client.post(
        "/api/observability/adaptation/modality-routing/inspect",
        api_key=state.admin_key,
        payload=generation_payload(
            learner_id=learner_id,
            content_type="worked_example",
            intent="explanation",
            context=[
                "Longitudinal Day 1 visual-model follow-up for equivalent fractions.",
            ],
        ),
    )
    if first_decision:
        client.post(
            "/api/households/me/approvals/"
            f"{learner_id}/{first_decision['approval_id']}/approve",
            api_key=state.parent_key,
        )
        approved_after_stall = [
            {
                "approval_id": first_decision["approval_id"],
                "approval_type": first_decision.get("approval_type"),
                "decision": "approve_after_prior_reject",
                "previewed": first_decision["previewed"],
            }
        ]
        approved_after_stall.extend(
            resolve_all_pending_approvals(
                client=client,
                state=state,
                learner_id=learner_id,
            )
        )
    else:
        approved_after_stall = resolve_all_pending_approvals(
            client=client,
            state=state,
            learner_id=learner_id,
        )
    day_1 = review_checkpoint(
        client=client,
        state=state,
        phase_id="session-1-stall",
        learner_id=learner_id,
    )
    baseline_sample = content_quality_sample(
        phase_id="session-1-stall",
        learner_alias="avery",
        generation=baseline,
        review_note=(
            "Baseline practice sample captured after weak outcomes; review for "
            "curriculum shape, age fit, and absence of learner-private fields."
        ),
    )
    report["content_quality_samples"].append(baseline_sample)
    report["phases"].append(
        phase_result(
            phase_id="session-1-stall",
            checkpoint=day_1,
            parent_decisions=approved_after_stall,
            content_samples=[baseline_sample],
            modality_inspection={
                "effective_plugin_id": inspection.get("effective_plugin_id"),
                "policy_fallback_applied": inspection.get("policy_fallback_applied"),
                "fallback_reason": inspection.get("fallback_reason"),
            },
            proof_signal=(
                "Repeated weak observations created adaptation pressure and "
                "approval-gated recovery remained inspectable."
            ),
        )
    )

    recovery = generate(
        client=client,
        api_key=learner_key,
        learner_id=learner_id,
        content_type="remedial_micro_module",
        intent="remediation",
        context=[
            "Longitudinal Day 2 recovery for denominator-size misconception.",
            "Use same-sized wholes and visual area models.",
        ],
    )
    observe(
        client=client,
        api_key=learner_key,
        learner_id=learner_id,
        generation=recovery,
        quality="weak",
    )
    observe(
        client=client,
        api_key=learner_key,
        learner_id=learner_id,
        generation=recovery,
        quality="strong",
    )
    client.get(f"/api/learners/{learner_id}/workspace", api_key=state.admin_key)
    day_2 = review_checkpoint(
        client=client,
        state=state,
        phase_id="session-2-recovery-plan",
        learner_id=learner_id,
    )
    recovery_decisions = resolve_all_pending_approvals(
        client=client,
        state=state,
        learner_id=learner_id,
    )
    recovery_sample = content_quality_sample(
        phase_id="session-2-recovery-plan",
        learner_alias="avery",
        generation=recovery,
        review_note=(
            "Recovery sample captured after mixed evidence; review that it "
            "targets the denominator-size misconception."
        ),
    )
    report["content_quality_samples"].append(recovery_sample)
    assert_planning_changed(day_1, day_2)
    report["phases"].append(
        phase_result(
            phase_id="session-2-recovery-plan",
            checkpoint=day_2,
            parent_decisions=recovery_decisions,
            content_samples=[recovery_sample],
            proof_signal=(
                "Planning state changed after accumulated session evidence and "
                "remained readable from observability."
            ),
        )
    )

    follow_up = generate(
        client=client,
        api_key=learner_key,
        learner_id=learner_id,
        content_type="practice_problem",
        intent="practice",
        context=[
            "Longitudinal Day 3 recovery confirmation for equivalent fractions.",
        ],
    )
    observe(
        client=client,
        api_key=learner_key,
        learner_id=learner_id,
        generation=follow_up,
        quality="strong",
    )
    reusable_context = [
        f"Longitudinal library reuse rehearsal {state.run_stamp}.",
        "Use curriculum-shaped visual model language only.",
    ]
    source_alias = "reuse_source" if "reuse_source" in state.learner_ids else "avery"
    peer_alias = "reuse_peer" if "reuse_peer" in state.learner_ids else "blair"
    source_reusable = generate(
        client=client,
        api_key=state.learner_keys[source_alias],
        learner_id=state.learner_ids[source_alias],
        content_type="worked_example",
        intent="explanation",
        context=reusable_context,
    )
    peer_reusable = generate(
        client=client,
        api_key=state.learner_keys[peer_alias],
        learner_id=state.learner_ids[peer_alias],
        content_type="worked_example",
        intent="explanation",
        context=reusable_context,
    )
    assert_reuse_hit(peer_reusable, learner_alias=peer_alias)
    audit = client.get(
        "/api/observability/adaptation/library/privacy-audit",
        api_key=state.admin_key,
    )
    if audit.get("forbidden_field_hits"):
        raise RehearsalError(
            "Longitudinal library privacy audit found private fields: "
            f"{audit['forbidden_field_hits']}"
        )
    day_3 = review_checkpoint(
        client=client,
        state=state,
        phase_id="session-3-recovery",
        learner_id=learner_id,
    )
    follow_up_sample = content_quality_sample(
        phase_id="session-3-recovery",
        learner_alias="avery",
        generation=follow_up,
        review_note="Recovery confirmation sample captured for longitudinal review.",
    )
    source_reusable_sample = content_quality_sample(
        phase_id="session-3-recovery",
        learner_alias=source_alias,
        generation=source_reusable,
        review_note=(
            "Reusable source sample captured before the matching peer request."
        ),
    )
    peer_sample = content_quality_sample(
        phase_id="session-3-recovery",
        learner_alias=peer_alias,
        generation=peer_reusable,
        review_note=(
            "Peer sample must report cache_hit=true to prove safe curriculum reuse."
        ),
    )
    report["content_quality_samples"].extend(
        [follow_up_sample, source_reusable_sample, peer_sample]
    )
    report["privacy_audit"] = {
        "entry_count": audit.get("entry_count", 0),
        "forbidden_field_hits": audit.get("forbidden_field_hits", []),
    }
    report["phases"].append(
        phase_result(
            phase_id="session-3-recovery",
            checkpoint=day_3,
            content_samples=[follow_up_sample, source_reusable_sample, peer_sample],
            proof_signal=(
                "Recovery, proven cross-learner library reuse, readiness, "
                "traces, and privacy audit are inspectable without database access."
            ),
        )
    )
    return report


def review_checkpoint(
    *,
    client: ApiClient,
    state: RuntimeState,
    phase_id: str,
    learner_id: str,
) -> dict[str, Any]:
    readiness = client.get("/ready")
    release = client.get("/api/observability/readiness", api_key=state.admin_key)
    overview = client.get("/api/households/me/overview", api_key=state.parent_key)
    planning = client.get(
        f"/api/observability/adaptation/planning/{learner_id}",
        api_key=state.admin_key,
    )
    explanation = client.get(
        "/api/observability/adaptation/autonomous-teacher/"
        f"{state.household_id}/{learner_id}/explain",
        api_key=state.admin_key,
    )
    traces = client.get("/api/observability/traces?limit=20", api_key=state.admin_key)
    trajectory = planning.get("trajectory") or {}
    adaptation = trajectory.get("adaptation_state") or {}
    pending = overview.get("pending_approvals", [])
    suggestions = overview.get("session_suggestions", [])
    return {
        "phase_id": phase_id,
        "ready_status": readiness.get("status"),
        "degraded_trace_count": release.get("degraded_trace_count", 0),
        "pending_review_queues": release.get("pending_review_queues", []),
        "blocked_review_preview_count": len(release.get("blocked_review_previews", [])),
        "pending_approval_count": len(pending),
        "session_suggestion_count": len(suggestions),
        "planning_revision_count": len(trajectory.get("revisions", [])),
        "active_revisit_density": adaptation.get("active_revisit_density", 1),
        "recent_signal_count": len(adaptation.get("recent_signals", [])),
        "autonomous_blockers": explanation.get("blocking_approval_types", []),
        "trace_count": len(traces),
        "recent_trace_summaries": [
            {
                "harness": trace.get("harness"),
                "operation": trace.get("operation"),
                "status": trace.get("status"),
                "reason_code": trace.get("reason_code"),
            }
            for trace in traces[:5]
        ],
    }


def resolve_one_approval(
    *,
    client: ApiClient,
    state: RuntimeState,
    learner_id: str,
    decision: str,
) -> dict[str, Any] | None:
    overview = client.get("/api/households/me/overview", api_key=state.parent_key)
    approvals = [
        approval
        for approval in overview.get("pending_approvals", [])
        if approval.get("learner_id") in {None, learner_id}
    ]
    if not approvals:
        return None
    approval = approvals[0]
    approval_id = required(approval, "approval_id")
    preview = client.get(
        f"/api/households/me/approvals/{learner_id}/{approval_id}/preview",
        api_key=state.parent_key,
    )
    client.post(
        f"/api/households/me/approvals/{learner_id}/{approval_id}/{decision}",
        api_key=state.parent_key,
    )
    return {
        "approval_id": approval_id,
        "approval_type": approval.get("approval_type"),
        "decision": decision,
        "previewed": bool(preview.get("if_approved") and preview.get("if_denied")),
    }


def resolve_all_pending_approvals(
    *, client: ApiClient, state: RuntimeState, learner_id: str
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    while len(decisions) < 10:
        decision = resolve_one_approval(
            client=client,
            state=state,
            learner_id=learner_id,
            decision="approve",
        )
        if decision is None:
            return decisions
        approval_id = str(decision["approval_id"])
        if approval_id in seen:
            raise RehearsalError(
                f"Approval {approval_id} remained pending after update."
            )
        seen.add(approval_id)
        decisions.append(decision)
    raise RehearsalError("Too many pending approvals to resolve in proof rehearsal.")


def content_quality_sample(
    *,
    phase_id: str,
    learner_alias: str,
    generation: dict[str, Any],
    review_note: str,
) -> dict[str, Any]:
    quality = generation.get("quality") or {}
    workflow = generation.get("workflow_summary") or {}
    return {
        "phase_id": phase_id,
        "learner_alias": learner_alias,
        "generation_id": generation.get("generation_id"),
        "learning_session_id": workflow.get("learning_session_id"),
        "content_type": generation.get("content_type"),
        "modality": content_modality(generation),
        "cache_hit": bool(quality.get("cache_hit")),
        "review_note": review_note,
        "review_checklist": {
            "curriculum_fit": "Does the sample teach the named KC/outcome without drifting?",
            "misconception_targeting": "Does it address the intended misconception or evidence need?",
            "age_fit": "Is the language and task shape plausible for the seeded learner grade?",
            "privacy": "Does it avoid learner identity, household facts, credentials, and private history?",
            "actionability": "Would a parent know whether to approve, retry, or escalate after seeing it?",
        },
    }


def assert_reuse_hit(generation: dict[str, Any], *, learner_alias: str) -> None:
    if not bool((generation.get("quality") or {}).get("cache_hit")):
        raise RehearsalError(
            f"{learner_alias} did not receive a cache/library hit for the "
            "longitudinal reuse proof."
        )


def phase_result(
    *,
    phase_id: str,
    checkpoint: dict[str, Any],
    proof_signal: str,
    parent_decisions: list[dict[str, Any]] | None = None,
    content_samples: list[dict[str, Any]] | None = None,
    modality_inspection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "phase_id": phase_id,
        "review_checkpoint": checkpoint,
        "parent_decisions": parent_decisions or [],
        "content_samples": content_samples or [],
        "proof_signal": proof_signal,
    }
    if modality_inspection is not None:
        result["modality_inspection"] = modality_inspection
    return result


def assert_planning_changed(
    before_checkpoint: dict[str, Any], after_checkpoint: dict[str, Any]
) -> None:
    before_revisions = before_checkpoint.get("planning_revision_count", 0)
    after_revisions = after_checkpoint.get("planning_revision_count", 0)
    before_density = before_checkpoint.get("active_revisit_density", 1)
    after_density = after_checkpoint.get("active_revisit_density", 1)
    before_signals = before_checkpoint.get("recent_signal_count", 0)
    after_signals = after_checkpoint.get("recent_signal_count", 0)
    if (
        after_revisions <= before_revisions
        and after_density <= before_density
        and after_signals <= before_signals
    ):
        raise RehearsalError(
            "Longitudinal planning review did not show accumulated evidence, "
            "revision, or revisit-density change."
        )


def generate(
    *,
    client: ApiClient,
    api_key: str,
    learner_id: str,
    content_type: str,
    intent: str,
    context: list[str],
) -> dict[str, Any]:
    return client.post(
        "/api/content/generate",
        api_key=api_key,
        payload=generation_payload(
            learner_id=learner_id,
            content_type=content_type,
            intent=intent,
            context=context,
        ),
    )


def generation_payload(
    *,
    learner_id: str,
    content_type: str,
    intent: str,
    context: list[str],
) -> dict[str, Any]:
    return {
        "student_id": learner_id,
        "target_kc_ids": ["KC-FRAC-EQUIV"],
        "intent": intent,
        "requested_content_type": content_type,
        "curriculum_context": context,
    }


def observe(
    *,
    client: ApiClient,
    api_key: str,
    learner_id: str,
    generation: dict[str, Any],
    quality: str,
) -> None:
    weak = quality == "weak"
    workflow = generation.get("workflow_summary") or {}
    client.post(
        f"/api/learners/{learner_id}/observations",
        api_key=api_key,
        payload={
            "response_time_ms": 95000 if weak else 28000,
            "hints_used": 4 if weak else 0,
            "error_count": 3 if weak else 0,
            "pause_count": 5 if weak else 1,
            "modality_switches": 1 if weak else 0,
            "completed": not weak,
            "confidence": 0.18 if weak else 0.86,
            "task_type": "practice",
            "support_level": "high" if weak else "low",
            "expected_duration_ms": 45000,
            "learning_session_id": workflow.get("learning_session_id"),
            "generation_id": generation.get("generation_id"),
            "observed_content_type": generation.get("content_type"),
            "target_kc_ids": ["KC-FRAC-EQUIV"],
            "target_lo_ids": [],
            "interaction_events": [
                {
                    "event_type": "answer",
                    "block_id": "proof-observation",
                    "correct": not weak,
                    "response_text": (
                        "I picked the bigger denominator."
                        if weak
                        else "Two fourths and one half cover the same area."
                    ),
                }
            ],
            "response_text": (
                "I picked the bigger denominator."
                if weak
                else "Two fourths and one half cover the same area."
            ),
        },
    )


def content_modality(content: dict[str, Any]) -> str:
    request_context = content.get("request_context") or {}
    if isinstance(request_context.get("modality_plugin_id"), str):
        return request_context["modality_plugin_id"]
    artifacts = content.get("response", {}).get("artifacts", [])
    if artifacts:
        provenance = artifacts[0].get("provenance") or {}
        if isinstance(provenance.get("plugin_id"), str):
            return provenance["plugin_id"]
        if isinstance(provenance.get("modality"), str):
            return provenance["modality"]
    return "text"


def required(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value is None:
        raise RehearsalError(f"Missing required response field: {key}")
    return value


SCENARIO_RUNNERS = {
    "new_household_onboarding": run_onboarding,
    "adaptive_modality_change": run_adaptive_modality,
    "parent_governed_autonomy": run_parent_governed_autonomy,
    "cross_session_planning_revision": run_cross_session_planning,
    "shared_library_reuse_without_privacy_leakage": run_shared_library,
}
TIMELINE_RUNNERS = {
    "longitudinal_fraction_recovery": run_longitudinal_fraction_recovery,
}


if __name__ == "__main__":
    raise SystemExit(main())
