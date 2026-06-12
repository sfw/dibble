from __future__ import annotations

from uuid import UUID

from dibble.services.data_rights import LearnerDataRightsService
from dibble.services.sqlite_connection import create_connection
from tests.support import build_profile


def _seed_learner_activity(client, student_id) -> None:
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="none", total_load=0.2),
    )
    session = client.post(f"/api/learners/{student_id}/session/start").json()
    client.post(
        f"/api/learners/{student_id}/observations",
        json={
            "response_time_ms": 4000,
            "completed": True,
            "learning_session_id": session["learning_session_id"],
        },
    )
    client.post(
        f"/api/learners/{student_id}/session/end",
        json={"learning_session_id": session["learning_session_id"]},
    )


def test_export_returns_profile_history_and_audits(client, student_id) -> None:
    _seed_learner_activity(client, student_id)

    response = client.get(f"/api/admin/learners/{student_id}/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["student_id"] == str(student_id)
    assert payload["profile"] is not None
    assert payload["profile"]["student_id"] == str(student_id)
    assert len(payload["observations"]) == 1
    event_types = {event["event_type"] for event in payload["audit_events"]}
    assert "learning.session.started" in event_types
    assert "learning.session.completed" in event_types


def test_export_for_unknown_learner_is_empty(client, student_id) -> None:
    response = client.get(f"/api/admin/learners/{student_id}/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] is None
    assert payload["audit_events"] == []


def test_hard_delete_removes_learner_everywhere(
    client, student_id, app_settings
) -> None:
    _seed_learner_activity(client, student_id)

    service = LearnerDataRightsService(
        connection=create_connection(app_settings.database_path)
    )
    report = service.hard_delete(student_id=UUID(str(student_id)))

    assert report.deleted_rows_by_table.get("learner_profiles") == 1
    assert report.deleted_rows_by_table.get("learner_observations") == 1
    assert report.deleted_rows_by_table.get("audit_events", 0) >= 2

    export = client.get(f"/api/admin/learners/{student_id}/export").json()
    assert export["profile"] is None
    assert export["observations"] == []
    assert export["audit_events"] == []


def test_hard_delete_of_family_learner_removes_user(client, app_settings) -> None:
    code = client.post("/api/admin/guardian-invites", json={}).json()["code"]
    section_id = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": code, "display_name": "Guardian"},
    ).json()["family_section_id"]
    learner = client.post(
        "/api/family/learners",
        json={"display_name": "Avery", "grade_level": "5", "section_id": section_id},
    ).json()

    service = LearnerDataRightsService(
        connection=create_connection(app_settings.database_path)
    )
    report = service.hard_delete(student_id=UUID(learner["learner_id"]))

    assert learner["user_id"] in report.deleted_user_ids
    assert report.deleted_rows_by_table.get("users") == 1
    assert report.deleted_rows_by_table.get("classroom_memberships") == 1

    roster = client.get(f"/api/family/learners?section_id={section_id}").json()
    assert roster == []
