from __future__ import annotations

from tests.support import (
    build_outcome,
    build_knowledge_component,
    build_profile,
)


def test_generation_history_returns_paginated_response(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/outcomes/CURR-1", json=build_outcome())
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Fractions basics"),
    )

    client.post(
        "/api/content/generate",
        json={
            "student_id": str(student_id),
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "intent": "practice",
        },
    )

    response = client.get(f"/api/learners/{student_id}/history/generations")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "offset" in payload
    assert "limit" in payload
    assert "has_more" in payload
    assert payload["offset"] == 0
    assert payload["limit"] == 20
    assert len(payload["items"]) >= 1
    assert payload["has_more"] is False


def test_generation_history_respects_limit_and_offset(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))
    client.put("/api/curriculum/outcomes/CURR-1", json=build_outcome())
    kc_ids = [f"KC-{i}" for i in range(1, 6)]
    for kc_id in kc_ids:
        client.put(
            f"/api/knowledge-components/{kc_id}",
            json=build_knowledge_component(kc_id, name=f"Topic {kc_id}"),
        )

    for kc_id in kc_ids:
        client.post(
            "/api/content/generate",
            json={
                "student_id": str(student_id),
                "target_kc_ids": [kc_id],
                "target_lo_ids": ["LO-1"],
                "intent": "practice",
            },
        )

    first_page = client.get(
        f"/api/learners/{student_id}/history/generations?limit=2&offset=0"
    ).json()
    assert len(first_page["items"]) == 2
    assert first_page["offset"] == 0
    assert first_page["limit"] == 2
    assert first_page["has_more"] is True

    second_page = client.get(
        f"/api/learners/{student_id}/history/generations?limit=2&offset=2"
    ).json()
    assert len(second_page["items"]) == 2
    assert second_page["offset"] == 2
    assert second_page["has_more"] is True

    third_page = client.get(
        f"/api/learners/{student_id}/history/generations?limit=2&offset=4"
    ).json()
    assert len(third_page["items"]) == 1
    assert third_page["offset"] == 4
    assert third_page["has_more"] is False

    all_ids = [
        e["generation_id"]
        for e in first_page["items"] + second_page["items"] + third_page["items"]
    ]
    assert len(set(all_ids)) == 5


def test_generation_history_clamps_limit(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))

    over_max = client.get(
        f"/api/learners/{student_id}/history/generations?limit=200"
    ).json()
    assert over_max["limit"] == 100

    under_min = client.get(
        f"/api/learners/{student_id}/history/generations?limit=0"
    ).json()
    assert under_min["limit"] == 1


def test_socratic_history_returns_paginated_response(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))

    response = client.get(f"/api/learners/{student_id}/history/socratic-sessions")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "offset" in payload
    assert "limit" in payload
    assert "has_more" in payload
    assert payload["items"] == []
    assert payload["has_more"] is False


def test_remediation_history_returns_paginated_response(client, student_id):
    client.put(f"/api/learners/{student_id}/profile", json=build_profile(student_id))

    response = client.get(f"/api/learners/{student_id}/history/remediation-sessions")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "offset" in payload
    assert "limit" in payload
    assert "has_more" in payload
    assert payload["items"] == []
    assert payload["has_more"] is False
