from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.services.runtime_telemetry import setup_runtime_telemetry


@pytest.fixture(autouse=True)
def restore_dibble_logger_state():
    logger = logging.getLogger("dibble")
    original_handlers = list(logger.handlers)
    original_filters = list(logger.filters)
    original_level = logger.level
    original_propagate = logger.propagate
    original_disabled = logger.disabled
    try:
        yield
    finally:
        for handler in list(logger.handlers):
            handler.close()
        logger.handlers = original_handlers
        logger.filters = original_filters
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        logger.disabled = original_disabled


def _build_client(tmp_path: Path, *, telemetry_level: str) -> TestClient:
    settings = Settings(
        database_path=str(tmp_path / "dibble-test.db"),
        telemetry_level=telemetry_level,
    )
    return TestClient(create_app(settings))


def test_telemetry_off_creates_logs_directory_without_writing_logs(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    logs_dir = setup_runtime_telemetry(Settings(telemetry_level="off"))

    logging.getLogger("dibble.test").warning("should not be persisted")

    assert logs_dir == tmp_path / ".dibble" / "logs"
    assert logs_dir.is_dir()
    assert list(logs_dir.iterdir()) == []


def test_normal_telemetry_writes_session_log_without_debug_payload(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    client = _build_client(tmp_path, telemetry_level="normal")

    response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(uuid4()),
            "learning_session_id": "learn-normal-1",
            "session_id": "socratic-normal-1",
            "target_kc_ids": ["KC-1"],
        },
    )

    assert response.status_code == 404

    log_text = (tmp_path / ".dibble" / "logs" / "learn-normal-1.log").read_text()
    assert "request.started" in log_text
    assert "request.completed" in log_text
    assert "request.payload" not in log_text


def test_debug_telemetry_writes_debug_payload_to_session_log(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    client = _build_client(tmp_path, telemetry_level="debug")

    response = client.post(
        "/api/assessments/socratic",
        json={
            "student_id": str(uuid4()),
            "learning_session_id": "learn-debug-1",
            "session_id": "socratic-debug-1",
            "target_kc_ids": ["KC-1"],
            "learner_response": "I think the fractions match.",
        },
    )

    assert response.status_code == 404

    log_text = (tmp_path / ".dibble" / "logs" / "learn-debug-1.log").read_text()
    assert "request.started" in log_text
    assert "request.payload" in log_text
    assert "I think the fractions match." in log_text


def test_sessionless_requests_are_written_to_system_log(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    client = _build_client(tmp_path, telemetry_level="normal")

    response = client.get("/health")

    assert response.status_code == 200

    log_text = (tmp_path / ".dibble" / "logs" / "system.log").read_text()
    assert "request.started" in log_text
    assert '"path": "/health"' in log_text
