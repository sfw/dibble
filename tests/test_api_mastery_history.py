from __future__ import annotations

from uuid import uuid4

from tests.support import assert_machine_readable_error, build_classroom, build_profile


def test_mastery_history_returns_empty_for_new_learner(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    response = client.get(f"/api/learners/{student_id}/mastery-history")
    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == str(student_id)
    assert body["days"] == 30
    assert body["snapshot_count"] == 0
    assert body["snapshots"] == []


def test_mastery_history_404_for_unknown_learner(client):
    sid = uuid4()
    response = client.get(f"/api/learners/{sid}/mastery-history")
    assert_machine_readable_error(
        response, status_code=404, code="learner_profile_not_found"
    )


def test_mastery_history_populated_after_observation(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.post(
        f"/api/learners/{student_id}/observations",
        json={
            "response_time_ms": 3000,
            "hints_used": 0,
            "error_count": 0,
            "pause_count": 1,
            "modality_switches": 0,
            "completed": True,
            "task_type": "practice",
            "support_level": "low",
        },
    )
    response = client.get(f"/api/learners/{student_id}/mastery-history")
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_count"] >= 1
    snapshot = body["snapshots"][0]
    assert snapshot["student_id"] == str(student_id)
    assert "overall_kc_mastery" in snapshot
    assert "overall_lo_mastery" in snapshot
    assert "kc_count" in snapshot
    assert "engagement" in snapshot
    assert "frustration" in snapshot
    assert "created_at" in snapshot


def test_mastery_history_respects_days_param(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.post(
        f"/api/learners/{student_id}/observations",
        json={
            "response_time_ms": 3000,
            "hints_used": 0,
            "error_count": 0,
            "pause_count": 0,
            "modality_switches": 0,
            "completed": True,
            "task_type": "practice",
            "support_level": "low",
        },
    )
    response = client.get(f"/api/learners/{student_id}/mastery-history?days=7")
    assert response.status_code == 200
    body = response.json()
    assert body["days"] == 7
    assert body["snapshot_count"] >= 1


def test_mastery_history_clamps_days(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    response = client.get(f"/api/learners/{student_id}/mastery-history?days=0")
    assert response.status_code == 200
    assert response.json()["days"] == 1

    response = client.get(f"/api/learners/{student_id}/mastery-history?days=999")
    assert response.status_code == 200
    assert response.json()["days"] == 365


def test_classroom_mastery_trends_empty(client, student_id):
    client.put(
        "/api/teachers/classrooms/CLASS-1",
        json=build_classroom("CLASS-1", student_ids=[]),
    )
    response = client.get("/api/teachers/classrooms/CLASS-1/mastery-trends")
    assert response.status_code == 200
    body = response.json()
    assert body["classroom_id"] == "CLASS-1"
    assert body["learner_count"] == 0
    assert body["learner_trends"] == []
    assert body["classroom_average_snapshots"] == []


def test_classroom_mastery_trends_with_learner_data(client, student_id):
    sid = str(student_id)
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.post(
        f"/api/learners/{student_id}/observations",
        json={
            "response_time_ms": 3000,
            "hints_used": 0,
            "error_count": 0,
            "pause_count": 0,
            "modality_switches": 0,
            "completed": True,
            "task_type": "practice",
            "support_level": "low",
        },
    )
    client.put(
        "/api/teachers/classrooms/CLASS-1",
        json=build_classroom("CLASS-1", student_ids=[sid]),
    )
    response = client.get("/api/teachers/classrooms/CLASS-1/mastery-trends")
    assert response.status_code == 200
    body = response.json()
    assert body["learner_count"] == 1
    assert len(body["learner_trends"]) == 1
    trend = body["learner_trends"][0]
    assert trend["student_id"] == sid
    assert trend["snapshot_count"] >= 1
    assert len(body["classroom_average_snapshots"]) >= 1


def test_classroom_mastery_trends_404_unknown_classroom(client):
    response = client.get("/api/teachers/classrooms/NONEXISTENT/mastery-trends")
    assert_machine_readable_error(response, status_code=404, code="classroom_not_found")


def test_classroom_mastery_trends_respects_days_param(client, student_id):
    client.put(
        "/api/teachers/classrooms/CLASS-1",
        json=build_classroom("CLASS-1", student_ids=[]),
    )
    response = client.get("/api/teachers/classrooms/CLASS-1/mastery-trends?days=7")
    assert response.status_code == 200
    assert response.json()["days"] == 7
