from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dibble.app import create_app
from dibble.config import Settings


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
