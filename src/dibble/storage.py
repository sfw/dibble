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


def ensure_database(database_path: str) -> None:
    path = Path(database_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute(PROFILE_TABLE_SQL)
        connection.execute(CURRICULUM_TABLE_SQL)
        connection.execute(AUDIT_TABLE_SQL)
        connection.execute(EMBEDDING_TABLE_SQL)
        connection.commit()
