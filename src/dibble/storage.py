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

KNOWLEDGE_COMPONENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_components (
    kc_id TEXT PRIMARY KEY,
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

GENERATED_CONTENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS generated_content (
    generation_id TEXT PRIMARY KEY,
    cache_key TEXT NOT NULL UNIQUE,
    student_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    request_context TEXT NOT NULL,
    response_payload TEXT NOT NULL,
    quality_payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);
"""

OBSERVATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS learner_observations (
    observation_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

SOCRATIC_SESSION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS socratic_assessment_sessions (
    session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

PREDICTIVE_WARM_QUEUE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS predictive_warm_queue (
    task_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    request_payload TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_error TEXT
);
"""


def ensure_database(database_path: str) -> None:
    path = Path(database_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute(PROFILE_TABLE_SQL)
        connection.execute(CURRICULUM_TABLE_SQL)
        connection.execute(KNOWLEDGE_COMPONENT_TABLE_SQL)
        connection.execute(AUDIT_TABLE_SQL)
        connection.execute(EMBEDDING_TABLE_SQL)
        connection.execute(PROVIDER_HEALTH_TABLE_SQL)
        connection.execute(AUTH_SESSION_TABLE_SQL)
        connection.execute(GENERATED_CONTENT_TABLE_SQL)
        connection.execute(OBSERVATION_TABLE_SQL)
        connection.execute(SOCRATIC_SESSION_TABLE_SQL)
        connection.execute(PREDICTIVE_WARM_QUEUE_TABLE_SQL)
        connection.commit()
