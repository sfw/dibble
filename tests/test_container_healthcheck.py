from __future__ import annotations

from scripts.container_healthcheck import readiness_is_acceptable, readiness_status


def test_container_healthcheck_accepts_only_ready_by_default() -> None:
    assert readiness_is_acceptable({"status": "ready"}) is True
    assert readiness_is_acceptable({"status": "setup_required"}) is False
    assert readiness_is_acceptable({"status": "not_ready"}) is False
    assert readiness_is_acceptable({"status": "degraded"}) is False


def test_container_healthcheck_rejects_missing_or_non_string_status() -> None:
    assert readiness_status({}) is None
    assert readiness_is_acceptable({}) is False
    assert readiness_is_acceptable({"status": 200}) is False


def test_container_healthcheck_can_be_explicitly_relaxed() -> None:
    assert readiness_is_acceptable(
        {"status": "degraded"},
        allowed_statuses={"ready", "degraded"},
    )
