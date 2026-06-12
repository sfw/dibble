from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.models.curriculum import KnowledgeComponentUpsert, OutcomeUpsert
from dibble.models.profile import LearnerProfile
from dibble.models.retention import (
    RetentionReviewCandidate,
    RetentionReviewReason,
    RetentionStrengthTier,
)
from dibble.services.auth import hash_credential
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.retention_review_candidate_store import (
    SQLiteRetentionReviewCandidateStore,
)
from dibble.services.sqlite_connection import create_connection
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database
from tests.support import build_knowledge_component, build_outcome, build_profile


def _seed_user(
    db_path: str,
    *,
    api_key: str,
    role: str,
    user_id: str,
    learner_id: str | None = None,
    display_name: str | None = None,
) -> None:
    conn = create_connection(db_path)
    store = SQLiteUserStore(conn)
    now = datetime.now(timezone.utc).isoformat()
    store.create(
        User(
            user_id=user_id,
            display_name=display_name,
            role=role,
            api_key_hash=hash_credential(api_key),
            learner_id=learner_id,
            created_at=now,
            updated_at=now,
        )
    )


def test_adaptation_observability_routes_expose_modality_and_autonomous_teacher_state(
    tmp_path,
):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)
    student_id = uuid4()

    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-1")
    _seed_user(
        db_path,
        api_key="parent-key",
        role="parent",
        user_id="parent-1",
        display_name="Morgan",
    )
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-user-1",
        learner_id=str(student_id),
        display_name="Avery",
    )

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(
        LearnerProfile.model_validate(
            build_profile(student_id, frustration="low", total_load=0.3)
        )
    )
    SQLiteOutcomeStore(conn).upsert(
        OutcomeUpsert.model_validate(
            build_outcome("CURR-1", knowledge_component_ids=["KC-1"])
        )
    )
    SQLiteKnowledgeComponentStore(conn).upsert(
        KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1"))
    )

    with TestClient(app) as client:
        setup_response = client.put(
            "/api/households/me/setup",
            headers={"X-API-Key": "parent-key"},
            json={
                "household_name": "Avery Family",
                "learner_ids": [str(student_id)],
                "relationship_label": "parent",
                "preferences": {
                    "session_cadence": "daily",
                    "auto_session_suggestions": True,
                    "weekly_summary_day": "sunday",
                    "soft_escalation_enabled": True,
                    "approval_mode": "guided",
                    "modality_introduction_requires_approval": False,
                    "trajectory_revision_requires_approval": False,
                    "high_autonomy_session_requires_approval": False,
                },
            },
        )
        overview_response = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )
        modality_response = client.post(
            "/api/observability/adaptation/modality-routing/inspect",
            headers={"X-API-Key": "admin-key"},
            json={
                "student_id": str(student_id),
                "target_kc_ids": ["KC-1"],
                "intent": "explanation",
                "requested_content_type": "worked_example",
                "curriculum_context": ["Equivalent fractions with diagrams"],
            },
        )
        modality_explain_response = client.post(
            "/api/observability/adaptation/modality-routing/explain",
            headers={"X-API-Key": "admin-key"},
            json={
                "student_id": str(student_id),
                "target_kc_ids": ["KC-1"],
                "intent": "explanation",
                "requested_content_type": "worked_example",
                "curriculum_context": ["Equivalent fractions with diagrams"],
            },
        )
        household_id = setup_response.json()["household"]["household_id"]
        planning_response = client.get(
            f"/api/observability/adaptation/planning/{student_id}",
            headers={"X-API-Key": "admin-key"},
        )
        relationship_response = client.get(
            f"/api/observability/adaptation/autonomous-teacher/{household_id}/{student_id}",
            headers={"X-API-Key": "admin-key"},
        )
        autonomous_explain_response = client.get(
            f"/api/observability/adaptation/autonomous-teacher/{household_id}/{student_id}/explain",
            headers={"X-API-Key": "admin-key"},
        )

    assert overview_response.status_code == 200
    assert modality_response.status_code == 200
    assert modality_explain_response.status_code == 200
    assert planning_response.status_code == 200
    assert relationship_response.status_code == 200
    assert autonomous_explain_response.status_code == 200
    modality_payload = modality_response.json()
    modality_explain_payload = modality_explain_response.json()
    planning_payload = planning_response.json()
    relationship_payload = relationship_response.json()
    autonomous_explain_payload = autonomous_explain_response.json()
    assert modality_payload["selected_plugin_id"] in {"text", "diagram", "narrative"}
    assert modality_payload["candidate_scores"]
    assert modality_explain_payload["inspection"]["effective_plugin_id"] in {
        "text",
        "diagram",
        "narrative",
    }
    assert modality_explain_payload["next_expected_consequence"].startswith(
        "Content generation will use"
    )
    assert planning_payload["trajectory"]["adaptation_state"] is not None
    assert "recent_signals" in planning_payload["trajectory"]["adaptation_state"]
    assert "modality_preferences" in planning_payload["trajectory"]["adaptation_state"]
    assert "adaptation_state" in relationship_payload
    assert "latest_decision_trace" in relationship_payload
    assert "modality_preferences" in relationship_payload["latest_decision_trace"]
    assert autonomous_explain_payload["rollout_effects"]
    assert autonomous_explain_payload["next_expected_consequence"]


def test_retention_observability_routes_expose_due_and_scheduled_candidates(tmp_path):
    db_path = str(tmp_path / "dibble-retention-observability.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)
    student_id = uuid4()
    now = datetime.now(timezone.utc)

    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-1")
    conn = create_connection(db_path)
    SQLiteRetentionReviewCandidateStore(conn).upsert_many(
        [
            RetentionReviewCandidate(
                candidate_id="due-retention",
                learner_id=student_id,
                kc_ids=["KC-DUE"],
                review_reason=RetentionReviewReason.recovery_after_stall,
                retention_strength_tier=RetentionStrengthTier.urgent,
                due_at=now - timedelta(minutes=10),
            ),
            RetentionReviewCandidate(
                candidate_id="scheduled-retention",
                learner_id=student_id,
                kc_ids=["KC-SCHEDULED"],
                review_reason=RetentionReviewReason.outcome_mastered,
                retention_strength_tier=RetentionStrengthTier.light,
                due_at=now + timedelta(days=2),
            ),
        ]
    )

    with TestClient(app) as client:
        due_response = client.get(
            f"/api/observability/adaptation/retention/{student_id}/due",
            headers={"X-API-Key": "admin-key"},
        )
        scheduled_response = client.get(
            f"/api/observability/adaptation/retention/{student_id}/scheduled",
            headers={"X-API-Key": "admin-key"},
        )

    assert due_response.status_code == 200
    assert scheduled_response.status_code == 200
    due_payload = due_response.json()
    scheduled_payload = scheduled_response.json()
    assert [item["candidate_id"] for item in due_payload] == ["due-retention"]
    assert due_payload[0]["status"] == "due"
    assert [item["candidate_id"] for item in scheduled_payload] == [
        "scheduled-retention"
    ]


def test_mastery_progression_observability_route_exposes_bounded_metrics(tmp_path):
    db_path = str(tmp_path / "dibble-mastery-progression-observability.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)
    student_id = uuid4()

    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-1")
    audit_store = SQLiteAuditStore(create_connection(db_path))
    audit_store.append(
        event_type="progression.outcome",
        status="positive",
        student_id=str(student_id),
        payload={
            "decision_action": "attempt_transfer",
            "outcome": "positive",
        },
    )
    audit_store.append(
        event_type="progression.outcome",
        status="negative",
        student_id=str(student_id),
        payload={
            "decision_action": "attempt_transfer",
            "outcome": "negative",
        },
    )
    audit_store.append(
        event_type="curriculum.outcome.transition",
        status="mastered",
        student_id=str(student_id),
        payload={
            "outcome_id": "OUT-1",
            "from_state": "ready",
            "to_state": "mastered",
        },
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/observability/adaptation/mastery-progression/metrics",
            headers={"X-API-Key": "admin-key"},
            params={"student_id": str(student_id), "limit": 50},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "learner"
    assert payload["learner_id"] == str(student_id)
    assert payload["transfer_positive_rate"]["numerator"] == 1
    assert payload["transfer_positive_rate"]["denominator"] == 2
    assert payload["release_regret_rate"]["rate"] == 0.5
    assert payload["outcome_mastery_stability"]["rate"] == 1.0
    assert payload["assumptions"]


def test_observability_readiness_and_traces_surface_parent_approval_audit(tmp_path):
    db_path = str(tmp_path / "dibble-readiness.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)
    student_id = uuid4()

    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-1")
    _seed_user(
        db_path,
        api_key="parent-key",
        role="parent",
        user_id="parent-1",
        display_name="Morgan",
    )
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-user-1",
        learner_id=str(student_id),
        display_name="Avery",
    )

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(
        LearnerProfile.model_validate(build_profile(student_id))
    )
    SQLiteOutcomeStore(conn).upsert(
        OutcomeUpsert.model_validate(
            build_outcome("CURR-1", knowledge_component_ids=["KC-1"])
        )
    )
    SQLiteKnowledgeComponentStore(conn).upsert(
        KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1"))
    )

    with TestClient(app) as client:
        client.put(
            "/api/households/me/setup",
            headers={"X-API-Key": "parent-key"},
            json={
                "household_name": "Avery Family",
                "learner_ids": [str(student_id)],
                "relationship_label": "parent",
                "preferences": {
                    "session_cadence": "daily",
                    "auto_session_suggestions": True,
                    "weekly_summary_day": "sunday",
                    "soft_escalation_enabled": True,
                    "approval_mode": "guided",
                    "modality_introduction_requires_approval": True,
                    "trajectory_revision_requires_approval": True,
                    "high_autonomy_session_requires_approval": True,
                },
            },
        )
        overview_response = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )
        readiness_response = client.get(
            "/api/observability/readiness",
            headers={"X-API-Key": "admin-key"},
        )
        approval_id = overview_response.json()["pending_approvals"][0]["approval_id"]
        approve_response = client.post(
            f"/api/households/me/approvals/{student_id}/{approval_id}/approve",
            headers={"X-API-Key": "parent-key"},
        )
        trace_response = client.get(
            "/api/observability/traces?harness=autonomous_teacher",
            headers={"X-API-Key": "admin-key"},
        )

    assert overview_response.status_code == 200
    assert readiness_response.status_code == 200
    assert approve_response.status_code == 200
    assert trace_response.status_code == 200
    readiness_payload = readiness_response.json()
    traces_payload = trace_response.json()
    assert any(
        queue["queue_key"] == "parent_approvals" and queue["count"] >= 1
        for queue in readiness_payload["pending_review_queues"]
    )
    assert any(
        trace["operation"] == "parent_approval_update"
        and trace["reason_code"] == "parent_approval_approved"
        for trace in traces_payload
    )
    assert readiness_payload["blocked_review_previews"]


def test_rollout_simulation_and_parent_approval_preview_routes(tmp_path):
    db_path = str(tmp_path / "dibble-preview.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)
    student_id = uuid4()

    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-1")
    _seed_user(
        db_path,
        api_key="parent-key",
        role="parent",
        user_id="parent-1",
        display_name="Morgan",
    )
    _seed_user(
        db_path,
        api_key="learner-key",
        role="learner",
        user_id="learner-user-1",
        learner_id=str(student_id),
        display_name="Avery",
    )

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(
        LearnerProfile.model_validate(build_profile(student_id))
    )
    SQLiteOutcomeStore(conn).upsert(
        OutcomeUpsert.model_validate(
            build_outcome("CURR-1", knowledge_component_ids=["KC-1"])
        )
    )
    SQLiteKnowledgeComponentStore(conn).upsert(
        KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1"))
    )

    with TestClient(app) as client:
        policy_response = client.get(
            "/api/admin/rollout/policy",
            headers={"X-API-Key": "admin-key"},
        )
        policy_before = policy_response.json()
        policy_payload = deepcopy(policy_before["policy"])
        for gate in policy_payload["behavior_gates"]:
            if gate["capability"] == "autonomous_session_suggestions":
                gate["mode"] = "disabled"
            if gate["capability"] == "cloud_library_remote_read":
                gate["mode"] = "remote_preferred"
        simulate_response = client.post(
            "/api/admin/rollout/simulate",
            headers={"X-API-Key": "admin-key"},
            json={
                "proposed_policy": policy_payload,
                "subjects": [{"learner_id": str(student_id)}],
            },
        )
        policy_after_response = client.get(
            "/api/admin/rollout/policy",
            headers={"X-API-Key": "admin-key"},
        )
        client.put(
            "/api/households/me/setup",
            headers={"X-API-Key": "parent-key"},
            json={
                "household_name": "Avery Family",
                "learner_ids": [str(student_id)],
                "relationship_label": "parent",
                "preferences": {
                    "session_cadence": "daily",
                    "auto_session_suggestions": True,
                    "weekly_summary_day": "sunday",
                    "soft_escalation_enabled": True,
                    "approval_mode": "guided",
                    "modality_introduction_requires_approval": True,
                    "trajectory_revision_requires_approval": True,
                    "high_autonomy_session_requires_approval": True,
                },
            },
        )
        client.put(
            "/api/admin/rollout/policy",
            headers={"X-API-Key": "admin-key"},
            json={"policy": policy_payload},
        )
        overview_response = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )
        high_autonomy = next(
            approval
            for approval in overview_response.json()["pending_approvals"]
            if approval["approval_type"] == "high_autonomy_session"
        )
        preview_response = client.get(
            f"/api/households/me/approvals/{student_id}/{high_autonomy['approval_id']}/preview",
            headers={"X-API-Key": "parent-key"},
        )

    assert policy_response.status_code == 200
    assert simulate_response.status_code == 200
    assert policy_after_response.status_code == 200
    assert overview_response.status_code == 200
    assert preview_response.status_code == 200
    simulate_payload = simulate_response.json()
    preview_payload = preview_response.json()
    assert (
        simulate_payload["summary"]["capability_change_counts"][
            "cloud_library_remote_read"
        ]
        == 1
    )
    assert simulate_payload["summary"]["newly_risky_subject_count"] == 1
    assert (
        policy_after_response.json()["policy"]["behavior_gates"]
        == policy_before["policy"]["behavior_gates"]
    )
    assert (
        policy_after_response.json()["policy"]["evaluation_buckets"]
        == policy_before["policy"]["evaluation_buckets"]
    )
    assert any(
        "disables autonomous session suggestions" in item.lower()
        for item in preview_payload["rollout_constraints"]
    )
    assert any(
        "re-engagement session can move forward" in item.lower()
        for item in preview_payload["if_approved"]
    )


def test_library_privacy_audit_reports_curriculum_safe_entries(tmp_path):
    db_path = str(tmp_path / "dibble-library-audit.db")
    ensure_database(db_path)
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)
    student_id = uuid4()

    _seed_user(db_path, api_key="admin-key", role="admin", user_id="admin-1")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(
        LearnerProfile.model_validate(
            build_profile(student_id, frustration="low", total_load=0.3)
        )
    )
    SQLiteOutcomeStore(conn).upsert(
        OutcomeUpsert.model_validate(
            build_outcome("CURR-1", knowledge_component_ids=["KC-1"])
        )
    )
    SQLiteKnowledgeComponentStore(conn).upsert(
        KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1"))
    )

    with TestClient(app) as client:
        generate_response = client.post(
            "/api/content/generate",
            headers={"X-API-Key": "admin-key"},
            json={
                "student_id": str(student_id),
                "target_kc_ids": ["KC-1"],
                "intent": "explanation",
                "requested_content_type": "worked_example",
                "curriculum_context": ["Equivalent fractions with visual models"],
            },
        )
        audit_response = client.get(
            "/api/observability/adaptation/library/privacy-audit",
            headers={"X-API-Key": "admin-key"},
        )

    assert generate_response.status_code == 200
    assert generate_response.json()["request_context"]["modality_plugin_id"] in {
        "text",
        "diagram",
        "narrative",
    }
    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["entry_count"] >= 1
    assert payload["forbidden_field_hits"] == []
    assert payload["entries"][0]["content_student_id"] == (
        "00000000-0000-0000-0000-000000000000"
    )
    assert "curriculum_cache_key" in payload["entries"][0]["request_context_keys"]
