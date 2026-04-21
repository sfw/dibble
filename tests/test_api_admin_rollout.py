from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import hash_credential
from dibble.services.sqlite_connection import create_connection
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database


def _seed_user(
    db_path: str,
    *,
    api_key: str,
    role: str,
    user_id: str,
    learner_id: str | None = None,
    household_id: str | None = None,
) -> None:
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id=user_id,
            display_name=user_id,
            role=role,
            api_key_hash=hash_credential(api_key),
            learner_id=learner_id,
            household_id=household_id,
            created_at=now,
            updated_at=now,
        )
    )


def test_admin_rollout_routes_manage_policy_and_evaluation_summary(tmp_path):
    db_path = str(tmp_path / "dibble-rollout.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)
    learner_id = str(uuid4())
    household_id = "household-1"

    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-1")
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-user-1",
        learner_id=learner_id,
        household_id=household_id,
    )

    conn = create_connection(db_path)
    audit_store = SQLiteAuditStore(conn)
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=learner_id,
        payload={
            "generation_id": "gen-1",
            "modality_plugin_id": "text",
            "rollout_evaluation_bucket_id": "baseline_controlled",
            "rollout_evaluation_bucket_label": "Baseline Controlled",
            "rollout_evaluation_dimensions": {
                "cloud_mode": "local_only",
                "modality_mode": "full_multimodal",
            },
        },
    )
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=learner_id,
        payload={
            "source_generation_event_id": generation_event.event_id,
            "generation_id": "gen-1",
            "run_summary_score": 0.82,
            "downstream_observation_score": 0.78,
            "downstream_assessment_score": 0.74,
        },
    )

    with TestClient(app) as client:
        policy_response = client.get(
            "/api/admin/rollout/policy",
            headers={"X-API-Key": "admin-key"},
        )
        inspect_response = client.post(
            "/api/admin/rollout/inspect",
            headers={"X-API-Key": "admin-key"},
            json={"learner_id": learner_id},
        )
        evaluation_response = client.get(
            "/api/admin/rollout/evaluation-summary",
            headers={"X-API-Key": "admin-key"},
        )

        updated_policy = policy_response.json()["policy"]
        for switch in updated_policy["kill_switches"]:
            if switch["capability"] == "non_text_modalities":
                switch["active"] = True
                switch["reason"] = "pause multimodal rollout"
                break
        else:
            updated_policy["kill_switches"].append(
                {
                    "capability": "non_text_modalities",
                    "active": True,
                    "reason": "pause multimodal rollout",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        update_response = client.put(
            "/api/admin/rollout/policy",
            headers={"X-API-Key": "admin-key"},
            json={"policy": updated_policy},
        )
        readiness_response = client.get(
            "/api/observability/readiness",
            headers={"X-API-Key": "admin-key"},
        )

    assert policy_response.status_code == 200
    assert inspect_response.status_code == 200
    assert evaluation_response.status_code == 200
    assert update_response.status_code == 200
    assert readiness_response.status_code == 200

    inspect_payload = inspect_response.json()
    evaluation_payload = evaluation_response.json()
    readiness_payload = readiness_response.json()

    assert inspect_payload["evaluation_bucket"]["bucket_id"] == "baseline_controlled"
    assert any(
        decision["capability"] == "non_text_modalities"
        for decision in inspect_payload["decisions"]
    )
    assert evaluation_payload["total_samples"] == 1
    assert evaluation_payload["buckets"][0]["bucket_id"] == "baseline_controlled"
    assert evaluation_payload["buckets"][0]["average_run_outcome_score"] == 0.82
    assert any(
        switch["capability"] == "non_text_modalities"
        for switch in readiness_payload["active_kill_switches"]
    )
