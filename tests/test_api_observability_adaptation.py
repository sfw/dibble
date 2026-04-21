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
        LearnerProfile.model_validate(build_profile(student_id, frustration="low", total_load=0.3))
    )
    SQLiteOutcomeStore(conn).upsert(
        OutcomeUpsert.model_validate(build_outcome("CURR-1", knowledge_component_ids=["KC-1"]))
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
        household_id = setup_response.json()["household"]["household_id"]
        relationship_response = client.get(
            f"/api/observability/adaptation/autonomous-teacher/{household_id}/{student_id}",
            headers={"X-API-Key": "admin-key"},
        )

    assert overview_response.status_code == 200
    assert modality_response.status_code == 200
    assert relationship_response.status_code == 200
    modality_payload = modality_response.json()
    relationship_payload = relationship_response.json()
    assert modality_payload["selected_plugin_id"] in {"text", "diagram", "narrative"}
    assert modality_payload["candidate_scores"]
    assert "adaptation_state" in relationship_payload
    assert "latest_decision_trace" in relationship_payload
