from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_household_container_artifacts_define_persistent_runtime() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    compose = (ROOT / "deploy" / "household" / "docker-compose.yml").read_text()
    env_example = (ROOT / "deploy" / "household" / ".env.example").read_text()

    assert "DIBBLE_DEPLOYMENT_MODE=household_container" in dockerfile
    assert "DIBBLE_DATABASE_PATH=/data/dibble.db" in dockerfile
    assert 'VOLUME ["/data"]' in dockerfile
    assert "scripts/container_healthcheck.py" in dockerfile
    assert "scripts/container_healthcheck.py" in compose
    assert "dibble-household-data:/data" in compose
    assert "DIBBLE_FRONTEND_DIST_PATH: /app/frontend/dist" in compose
    assert "DIBBLE_CLOUD_LIBRARY_ENABLED=false" in env_example
    assert "DIBBLE_AUTH_ENABLED=true" in env_example


def test_pilot_docs_cover_required_pivot_artifacts() -> None:
    deployment_doc = (
        ROOT / "docs" / "deployment" / "household-container.md"
    ).read_text()
    scenario_doc = (ROOT / "docs" / "proof" / "scenarios.md").read_text()
    modality_doc = (ROOT / "docs" / "proof" / "modality-decision.md").read_text()
    pilot_runbook = (ROOT / "docs" / "runbooks" / "pilot-readiness.md").read_text()

    assert "/data/dibble.db" in deployment_doc
    assert "`/ready`" in deployment_doc
    assert "new_household_onboarding" in scenario_doc
    assert "text`, `narrative`, and `diagram` are sufficient" in modality_doc
    assert "Stop Conditions" in pilot_runbook
    assert "Cloud-library remote publish: off" in pilot_runbook
