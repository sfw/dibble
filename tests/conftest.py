from __future__ import annotations

from uuid import uuid4

import logging
import pytest
from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


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


@pytest.fixture(autouse=True)
def isolate_home_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def app_settings(tmp_path):
    return Settings(database_path=str(tmp_path / "dibble-test.db"))


@pytest.fixture
def client(app_settings):
    app = create_app(app_settings)
    return TestClient(app)


@pytest.fixture
def student_id():
    return uuid4()


@pytest.fixture
def db_path(tmp_path) -> str:
    """Return a path to a freshly-initialised test database."""
    path = str(tmp_path / "test.db")
    ensure_database(path)
    return path


@pytest.fixture
def db_connection(db_path):
    """Return a shared SQLite connection to a test database."""
    conn = create_connection(db_path)
    yield conn
    conn.close()
