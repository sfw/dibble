from __future__ import annotations

import sqlite3
from pathlib import Path


PROFILE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS learner_profiles (
    student_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CURRICULUM_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS curriculum_resources (
    resource_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    student_id TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

EMBEDDING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS curriculum_resource_embeddings (
    resource_id TEXT PRIMARY KEY,
    vector TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    source_updated_at TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);
"""

PROVIDER_HEALTH_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS provider_health_events (
    event_id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

AUTH_SESSION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    role TEXT NOT NULL,
    refresh_token_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    access_expires_at TEXT NOT NULL,
    refresh_expires_at TEXT NOT NULL,
    revoked_at TEXT
);
"""


def ensure_database(database_path: str) -> None:
    path = Path(database_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute(PROFILE_TABLE_SQL)
        connection.execute(CURRICULUM_TABLE_SQL)
        connection.execute(AUDIT_TABLE_SQL)
        connection.execute(EMBEDDING_TABLE_SQL)
        connection.execute(PROVIDER_HEALTH_TABLE_SQL)
        connection.execute(AUTH_SESSION_TABLE_SQL)
        connection.commit()
