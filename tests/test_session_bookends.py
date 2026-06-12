from __future__ import annotations

from uuid import uuid4

from tests.support import build_profile


def _start_session(client, student_id):
    response = client.post(f"/api/learners/{student_id}/session/start")
    assert response.status_code == 200
    return response.json()


def test_session_start_returns_goal_and_emits_event(client, student_id) -> None:
    payload = _start_session(client, student_id)

    assert payload["learning_session_id"].startswith("session-")
    assert payload["goal_display"]

    events = client.get("/api/audit/events").json()
    started = [
        event for event in events if event["event_type"] == "learning.session.started"
    ]
    assert len(started) == 1
    assert (
        started[0]["payload"]["learning_session_id"] == payload["learning_session_id"]
    )


def test_session_end_returns_recap_with_observation_counts(client, student_id) -> None:
    client.put(
        f"/api/learners/{student_id}/profile",
        json=build_profile(student_id, frustration="none", total_load=0.2),
    )
    session = _start_session(client, student_id)
    learning_session_id = session["learning_session_id"]

    for error_count in (0, 2):
        response = client.post(
            f"/api/learners/{student_id}/observations",
            json={
                "response_time_ms": 4000,
                "error_count": error_count,
                "completed": True,
                "learning_session_id": learning_session_id,
            },
        )
        assert response.status_code in {200, 201}

    recap = client.post(
        f"/api/learners/{student_id}/session/end",
        json={"learning_session_id": learning_session_id},
    )

    assert recap.status_code == 200
    body = recap.json()
    assert body["completed_activity_count"] == 2
    assert body["smooth_activity_count"] == 1
    assert "2 activities" in body["display_recap"]

    events = client.get("/api/audit/events").json()
    completed = [
        event for event in events if event["event_type"] == "learning.session.completed"
    ]
    assert len(completed) == 1


def test_session_end_with_no_activity_is_friendly(client, student_id) -> None:
    session = _start_session(client, student_id)

    recap = client.post(
        f"/api/learners/{student_id}/session/end",
        json={"learning_session_id": session["learning_session_id"]},
    ).json()

    assert recap["completed_activity_count"] == 0
    assert recap["display_recap"]


def test_defect_report_writes_audit_event(client, student_id) -> None:
    response = client.post(
        f"/api/learners/{student_id}/defect-report",
        json={
            "generation_id": str(uuid4()),
            "note": "The answer marked correct looks wrong.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"

    events = client.get("/api/audit/events").json()
    reports = [
        event for event in events if event["event_type"] == "content.defect.report"
    ]
    assert len(reports) == 1
    assert reports[0]["payload"]["note"] == "The answer marked correct looks wrong."


def test_session_events_feed_pilot_metrics(client, student_id) -> None:
    session = _start_session(client, student_id)
    client.post(
        f"/api/learners/{student_id}/session/end",
        json={"learning_session_id": session["learning_session_id"]},
    )
    client.post(
        f"/api/learners/{student_id}/defect-report",
        json={"generation_id": str(uuid4())},
    )

    metrics = client.get("/api/admin/pilot-metrics").json()

    learner = next(
        item for item in metrics["learners"] if item["student_id"] == str(student_id)
    )
    assert learner["sessions"]["sessions_started"] == 1
    assert learner["sessions"]["sessions_completed"] == 1
    assert learner["defect_report_count"] == 1
