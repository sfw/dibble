from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
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
            with urlopen(request, timeout=30) as response:
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
        "--admin-api-key",
        default=os.getenv("DIBBLE_PROOF_ADMIN_API_KEY"),
        help="Existing admin key. If omitted, the script tries first-run admin setup.",
    )
    parser.add_argument(
        "--seed-file",
        default="proof/fixtures/scenario_household_seed.json",
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIO_IDS,
        action="append",
        help="Run one scenario. Repeat for multiple. Defaults to all five.",
    )
    args = parser.parse_args()

    client = ApiClient(args.base_url)
    seed = json.loads(Path(args.seed_file).read_text())
    scenarios = tuple(args.scenario or SCENARIO_IDS)

    try:
        state = seed_runtime(client=client, seed=seed, admin_key=args.admin_api_key)
        results = []
        for scenario_id in scenarios:
            result = SCENARIO_RUNNERS[scenario_id](client, state)
            results.append(result)
            print(f"PASS {scenario_id}: {result}")
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
    context = [
        f"Equivalent fractions library reuse rehearsal {state.run_stamp}.",
        "Use curriculum-shaped visual model language only.",
    ]
    first = generate(
        client=client,
        api_key=state.learner_keys["avery"],
        learner_id=state.learner_ids["avery"],
        content_type="worked_example",
        intent="explanation",
        context=context,
    )
    second = generate(
        client=client,
        api_key=state.learner_keys["blair"],
        learner_id=state.learner_ids["blair"],
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
        raise RehearsalError("Learner B did not reuse learner A's library artifact.")
    return (
        f"learner A generation={first.get('generation_id')}; "
        f"learner B cache_hit={second_cache_hit}; audit_entries={audit['entry_count']}"
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


if __name__ == "__main__":
    raise SystemExit(main())
