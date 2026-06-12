from __future__ import annotations

from dibble.services.access_control import allows_role
from dibble.services.auth import hash_credential


def test_guardian_role_implies_teacher_and_parent_surfaces() -> None:
    assert allows_role("guardian", ["teacher"])
    assert allows_role("guardian", ["parent"])
    assert allows_role("guardian", ["learner"])
    assert not allows_role("guardian", ["admin"])
    # A plain teacher does not gain guardian-specific access.
    assert not allows_role("teacher", ["guardian"])


def test_invite_register_and_family_learners_full_path(client) -> None:
    invite = client.post(
        "/api/admin/guardian-invites", json={"family_name": "Stone family"}
    )
    assert invite.status_code == 200
    code = invite.json()["code"]

    register = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": code, "display_name": "Jordan Stone"},
    )
    assert register.status_code == 200
    payload = register.json()
    assert payload["role"] == "guardian"
    assert payload["credential"]
    section_id = payload["family_section_id"]

    learners = []
    for name, grade in (("Avery", "4"), ("Sam", "6")):
        created = client.post(
            "/api/family/learners",
            json={"display_name": name, "grade_level": grade, "section_id": section_id},
        )
        assert created.status_code == 200
        body = created.json()
        assert body["pin"]
        assert body["learner_id"]
        learners.append(body)

    roster = client.get(f"/api/family/learners?section_id={section_id}")
    assert roster.status_code == 200
    names = {entry["display_name"] for entry in roster.json()}
    assert names == {"Avery", "Sam"}
    grades = {entry["grade_level"] for entry in roster.json()}
    assert grades == {"4", "6"}


def test_invite_cannot_be_reused(client) -> None:
    code = client.post("/api/admin/guardian-invites", json={}).json()["code"]
    first = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": code, "display_name": "First Guardian"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": code, "display_name": "Second Guardian"},
    )

    assert second.status_code == 400
    assert second.headers.get("X-Dibble-Error-Code") == "guardian_invite_invalid"


def test_unknown_invite_code_is_rejected(client) -> None:
    response = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": "NOPE-0000", "display_name": "Guardian"},
    )

    assert response.status_code == 400


def test_family_unit_caps_at_three_learners(client) -> None:
    code = client.post("/api/admin/guardian-invites", json={}).json()["code"]
    section_id = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": code, "display_name": "Guardian"},
    ).json()["family_section_id"]

    for index in range(3):
        created = client.post(
            "/api/family/learners",
            json={
                "display_name": f"Kid {index}",
                "grade_level": "5",
                "section_id": section_id,
            },
        )
        assert created.status_code == 200

    fourth = client.post(
        "/api/family/learners",
        json={"display_name": "Kid 3", "grade_level": "5", "section_id": section_id},
    )

    assert fourth.status_code == 400
    assert fourth.headers.get("X-Dibble-Error-Code") == "family_learner_invalid"


def test_learner_pin_authenticates(client, app_settings) -> None:
    from dibble.bootstrap import build_application_services

    code = client.post("/api/admin/guardian-invites", json={}).json()["code"]
    section_id = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": code, "display_name": "Guardian"},
    ).json()["family_section_id"]
    created = client.post(
        "/api/family/learners",
        json={"display_name": "Avery", "grade_level": "5", "section_id": section_id},
    ).json()

    services = build_application_services(
        app_settings, settings_loader=lambda: app_settings
    )
    user = services.user_store.get_by_passphrase_hash(hash_credential(created["pin"]))

    assert user is not None
    assert user.role == "learner"
    assert user.learner_id == created["learner_id"]


def test_guardian_can_run_placement_for_created_learner(client) -> None:
    client.put(
        "/api/knowledge-components/kc-anchor-g5",
        json={
            "kc_id": "kc-anchor-g5",
            "name": "Anchor KC",
            "outcome_id": "lo-anchor",
            "grade_level": "5",
            "subject": "mathematics",
            "tags": ["anchor"],
        },
    )
    code = client.post("/api/admin/guardian-invites", json={}).json()["code"]
    section_id = client.post(
        "/api/auth/register-guardian",
        json={"invite_code": code, "display_name": "Guardian"},
    ).json()["family_section_id"]
    learner = client.post(
        "/api/family/learners",
        json={"display_name": "Avery", "grade_level": "5", "section_id": section_id},
    ).json()

    placement = client.post(
        f"/api/learners/{learner['learner_id']}/placement",
        json={"grade_band": "5"},
    )

    assert placement.status_code == 200
    assert placement.json()["status"] in {"active", "completed"}
