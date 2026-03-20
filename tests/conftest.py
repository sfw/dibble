from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


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
