from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.models.auth import User
from dibble.models.curriculum import KnowledgeComponentUpsert, OutcomeUpsert
from dibble.models.profile import LearnerProfile
from dibble.services.auth import hash_credential
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.sqlite_connection import create_connection
from dibble.services.user_store import SQLiteUserStore
from dibble.storage import ensure_database
from tests.support import build_knowledge_component, build_outcome, build_profile


def _seed_user(db_path: str, *, api_key: str, role: str, user_id: str, learner_id: str | None = None, display_name: str | None = None) -> None:
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


def test_household_setup_and_parent_overview_route(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    student_id = uuid4()
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)

    _seed_user(db_path, api_key="parent-key", role="parent", user_id="parent-1", display_name="Morgan")
    _seed_user(db_path, api_key="learner-key", role="learner", user_id="learner-user-1", learner_id=str(student_id), display_name="Avery")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(LearnerProfile.model_validate(build_profile(student_id, frustration="low", total_load=0.3)))
    SQLiteOutcomeStore(conn).upsert(OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"])))
    SQLiteKnowledgeComponentStore(conn).upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1")))

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
                },
            },
        )
        overview_response = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )

    assert setup_response.status_code == 200
    assert overview_response.status_code == 200
    payload = overview_response.json()
    assert payload["household"]["household_name"] == "Avery Family"
    assert payload["learners"][0]["learner_label"] == "Avery"
    assert payload["session_suggestions"]
    assert payload["weekly_summaries"]


def test_household_notification_read_state_persists_across_overview_refresh(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    student_id = uuid4()
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)

    _seed_user(db_path, api_key="parent-key", role="household_admin", user_id="parent-1", display_name="Morgan")
    _seed_user(db_path, api_key="learner-key", role="learner", user_id="learner-user-1", learner_id=str(student_id), display_name="Avery")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(LearnerProfile.model_validate(build_profile(student_id, frustration="high", total_load=0.6)))
    SQLiteOutcomeStore(conn).upsert(OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"])))
    SQLiteKnowledgeComponentStore(conn).upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1")))

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
                },
            },
        )
        overview_response = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )
        notification_id = overview_response.json()["notifications"][0]["notification_id"]
        mark_read_response = client.post(
            f"/api/households/me/notifications/{notification_id}/read",
            headers={"X-API-Key": "parent-key"},
        )
        refreshed_overview = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )

    assert setup_response.status_code == 200
    assert mark_read_response.status_code == 200
    assert refreshed_overview.status_code == 200
    refreshed_notification = next(
        item
        for item in refreshed_overview.json()["notifications"]
        if item["notification_id"] == notification_id
    )
    assert refreshed_notification["status"] == "read"
    assert refreshed_overview.json()["weekly_summaries"]


def test_household_setup_rejects_learner_already_assigned_to_another_household(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    student_id = uuid4()
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)

    _seed_user(db_path, api_key="parent-one-key", role="household_admin", user_id="parent-1", display_name="Morgan")
    _seed_user(db_path, api_key="parent-two-key", role="household_admin", user_id="parent-2", display_name="Casey")
    _seed_user(db_path, api_key="learner-key", role="learner", user_id="learner-user-1", learner_id=str(student_id), display_name="Avery")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(LearnerProfile.model_validate(build_profile(student_id, frustration="low", total_load=0.3)))
    SQLiteOutcomeStore(conn).upsert(OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"])))
    SQLiteKnowledgeComponentStore(conn).upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1")))

    with TestClient(app) as client:
        first_setup = client.put(
            "/api/households/me/setup",
            headers={"X-API-Key": "parent-one-key"},
            json={
                "household_name": "First Family",
                "learner_ids": [str(student_id)],
                "relationship_label": "parent",
                "preferences": {
                    "session_cadence": "daily",
                    "auto_session_suggestions": True,
                    "weekly_summary_day": "sunday",
                    "soft_escalation_enabled": True,
                    "approval_mode": "guided",
                },
            },
        )
        second_setup = client.put(
            "/api/households/me/setup",
            headers={"X-API-Key": "parent-two-key"},
            json={
                "household_name": "Second Family",
                "learner_ids": [str(student_id)],
                "relationship_label": "parent",
                "preferences": {
                    "session_cadence": "daily",
                    "auto_session_suggestions": True,
                    "weekly_summary_day": "sunday",
                    "soft_escalation_enabled": True,
                    "approval_mode": "guided",
                },
            },
        )

    assert first_setup.status_code == 200
    assert second_setup.status_code == 404
    assert "already belongs to another household" in second_setup.json()["detail"]


def test_household_preferences_update_can_disable_session_suggestions(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    student_id = uuid4()
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)

    _seed_user(db_path, api_key="parent-key", role="household_admin", user_id="parent-1", display_name="Morgan")
    _seed_user(db_path, api_key="learner-key", role="learner", user_id="learner-user-1", learner_id=str(student_id), display_name="Avery")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(LearnerProfile.model_validate(build_profile(student_id, frustration="low", total_load=0.3)))
    SQLiteOutcomeStore(conn).upsert(OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"])))
    SQLiteKnowledgeComponentStore(conn).upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1")))

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
                },
            },
        )
        update_response = client.patch(
            "/api/households/me/preferences",
            headers={"X-API-Key": "parent-key"},
            json={
                "relationship_label": "guardian",
                "preferences": {
                    "session_cadence": "flexible",
                    "auto_session_suggestions": False,
                    "weekly_summary_day": "monday",
                    "soft_escalation_enabled": False,
                    "approval_mode": "guided",
                },
            },
        )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["household"]["parent_profiles"][0]["relationship_label"] == "guardian"
    assert payload["household"]["parent_profiles"][0]["preferences"]["auto_session_suggestions"] is False
    assert payload["session_suggestions"] == []


def test_household_session_suggestion_actions_persist_and_snooze_hides(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    student_id = uuid4()
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)

    _seed_user(db_path, api_key="parent-key", role="household_admin", user_id="parent-1", display_name="Morgan")
    _seed_user(db_path, api_key="learner-key", role="learner", user_id="learner-user-1", learner_id=str(student_id), display_name="Avery")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(LearnerProfile.model_validate(build_profile(student_id, frustration="low", total_load=0.3)))
    SQLiteOutcomeStore(conn).upsert(OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"])))
    SQLiteKnowledgeComponentStore(conn).upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1")))

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
                },
            },
        )
        accept_response = client.post(
            f"/api/households/me/session-suggestions/{student_id}/accept",
            headers={"X-API-Key": "parent-key"},
        )
        defer_response = client.post(
            f"/api/households/me/session-suggestions/{student_id}/defer",
            headers={"X-API-Key": "parent-key"},
        )
        snooze_response = client.post(
            f"/api/households/me/session-suggestions/{student_id}/snooze",
            headers={"X-API-Key": "parent-key"},
            json={"hours": 24},
        )

    assert accept_response.status_code == 200
    assert accept_response.json()["session_suggestions"][0]["status"] == "accepted"
    assert defer_response.status_code == 200
    assert defer_response.json()["session_suggestions"][0]["status"] == "deferred"
    assert snooze_response.status_code == 200
    assert snooze_response.json()["session_suggestions"] == []


def test_household_notification_snooze_hides_notification_from_immediate_overview(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    student_id = uuid4()
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)

    _seed_user(db_path, api_key="parent-key", role="household_admin", user_id="parent-1", display_name="Morgan")
    _seed_user(db_path, api_key="learner-key", role="learner", user_id="learner-user-1", learner_id=str(student_id), display_name="Avery")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(LearnerProfile.model_validate(build_profile(student_id, frustration="high", total_load=0.6)))
    SQLiteOutcomeStore(conn).upsert(OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"])))
    SQLiteKnowledgeComponentStore(conn).upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1")))

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
                },
            },
        )
        first_overview = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )
        first_notification_id = first_overview.json()["notifications"][0]["notification_id"]
        snooze_response = client.post(
            f"/api/households/me/notifications/{first_notification_id}/snooze",
            headers={"X-API-Key": "parent-key"},
            json={"hours": 24},
        )
    assert first_overview.status_code == 200
    assert snooze_response.status_code == 200
    assert all(
        item["notification_id"] != first_notification_id
        for item in snooze_response.json()["notifications"]
    )


def test_household_notification_dismiss_hides_notification_from_immediate_overview(tmp_path):
    db_path = str(tmp_path / "dibble.db")
    ensure_database(db_path)
    student_id = uuid4()
    settings = Settings(database_path=db_path, auth_enabled=True)
    app = create_app(settings)

    _seed_user(db_path, api_key="parent-key", role="household_admin", user_id="parent-1", display_name="Morgan")
    _seed_user(db_path, api_key="learner-key", role="learner", user_id="learner-user-1", learner_id=str(student_id), display_name="Avery")

    conn = create_connection(db_path)
    SQLiteProfileStore(conn).upsert(LearnerProfile.model_validate(build_profile(student_id, frustration="high", total_load=0.6)))
    SQLiteOutcomeStore(conn).upsert(OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"])))
    SQLiteKnowledgeComponentStore(conn).upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1")))

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
                },
            },
        )
        first_overview = client.get(
            "/api/households/me/overview",
            headers={"X-API-Key": "parent-key"},
        )
        first_notification_id = first_overview.json()["notifications"][0]["notification_id"]
        dismiss_response = client.post(
            f"/api/households/me/notifications/{first_notification_id}/dismiss",
            headers={"X-API-Key": "parent-key"},
        )

    assert first_overview.status_code == 200
    assert dismiss_response.status_code == 200
    assert all(
        item["notification_id"] != first_notification_id
        for item in dismiss_response.json()["notifications"]
    )
