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

STRAND_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS strands (
    strand_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

OUTCOME_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

OUTCOME_EMBEDDING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS outcome_embeddings (
    outcome_id TEXT PRIMARY KEY,
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
    workflow_summary_payload TEXT,
    response_payload TEXT NOT NULL,
    quality_payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);
"""

CURRICULUM_CONTENT_LIBRARY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS curriculum_content_library (
    cache_key TEXT PRIMARY KEY,
    content_key_payload TEXT NOT NULL,
    content_payload TEXT NOT NULL,
    storage_scope TEXT NOT NULL,
    source_generation_id TEXT,
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

REMEDIATION_SESSION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS remediation_workflow_sessions (
    session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

WITHIN_SESSION_CONTROLLER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS within_session_controller_states (
    learning_session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

LEARNER_GOAL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS learner_goals (
    goal_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    status TEXT NOT NULL,
    active_trajectory_id TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

TRAJECTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS learner_trajectories (
    trajectory_id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SESSION_CONTROL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_control_states (
    learning_session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    goal_id TEXT,
    trajectory_id TEXT,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CLASSROOM_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS classrooms (
    classroom_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

COURSE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS courses (
    course_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

ASSIGNMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    teacher_id TEXT NOT NULL,
    section_id TEXT,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

MASTERY_SNAPSHOT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mastery_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    overall_kc_mastery REAL NOT NULL,
    overall_lo_mastery REAL NOT NULL,
    kc_count INTEGER NOT NULL,
    lo_count INTEGER NOT NULL,
    mastered_kc_count INTEGER NOT NULL,
    struggling_kc_count INTEGER NOT NULL,
    engagement TEXT NOT NULL,
    frustration TEXT NOT NULL,
    total_load REAL NOT NULL,
    created_at TEXT NOT NULL
);
"""

PREDICTIVE_WARM_QUEUE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS predictive_warm_queue (
    task_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    request_payload TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    priority_class TEXT NOT NULL DEFAULT 'routine',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    next_attempt_at TEXT,
    last_error TEXT,
    claim_owner TEXT,
    claim_mode TEXT,
    claim_reason TEXT,
    claimed_at TEXT,
    stale_recovered INTEGER NOT NULL DEFAULT 0
);
"""


USER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT,
    role TEXT NOT NULL,
    api_key_hash TEXT UNIQUE,
    passphrase_hash TEXT UNIQUE,
    learner_id TEXT,
    section_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CLASSROOM_MEMBERSHIP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS classroom_memberships (
    classroom_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (classroom_id, user_id, role)
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
        connection.execute(CURRICULUM_CONTENT_LIBRARY_TABLE_SQL)
        connection.execute(OBSERVATION_TABLE_SQL)
        connection.execute(SOCRATIC_SESSION_TABLE_SQL)
        connection.execute(REMEDIATION_SESSION_TABLE_SQL)
        connection.execute(WITHIN_SESSION_CONTROLLER_TABLE_SQL)
        connection.execute(LEARNER_GOAL_TABLE_SQL)
        connection.execute(TRAJECTORY_TABLE_SQL)
        connection.execute(SESSION_CONTROL_TABLE_SQL)
        connection.execute(COURSE_TABLE_SQL)
        connection.execute(CLASSROOM_TABLE_SQL)
        connection.execute(CLASSROOM_MEMBERSHIP_TABLE_SQL)
        connection.execute(ASSIGNMENT_TABLE_SQL)
        connection.execute(MASTERY_SNAPSHOT_TABLE_SQL)
        connection.execute(PREDICTIVE_WARM_QUEUE_TABLE_SQL)
        connection.execute(USER_TABLE_SQL)
        connection.execute(STRAND_TABLE_SQL)
        connection.execute(OUTCOME_TABLE_SQL)
        connection.execute(OUTCOME_EMBEDDING_TABLE_SQL)
        _ensure_sqlite_columns(
            connection,
            table_name="generated_content",
            columns={
                "workflow_summary_payload": "TEXT",
            },
        )
        _ensure_sqlite_columns(
            connection,
            table_name="users",
            columns={
                "section_ids": "TEXT NOT NULL DEFAULT '[]'",
            },
        )
        _ensure_sqlite_columns(
            connection,
            table_name="predictive_warm_queue",
            columns={
                "priority_class": "TEXT NOT NULL DEFAULT 'routine'",
                "attempt_count": "INTEGER NOT NULL DEFAULT 0",
                "next_attempt_at": "TEXT",
                "claim_owner": "TEXT",
                "claim_mode": "TEXT",
                "claim_reason": "TEXT",
                "claimed_at": "TEXT",
                "stale_recovered": "INTEGER NOT NULL DEFAULT 0",
            },
        )
        _migrate_curriculum_resources_to_outcomes(connection)
        connection.commit()


def _ensure_sqlite_columns(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing = {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_sql in columns.items():
        if column_name in existing:
            continue
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )


def _migrate_curriculum_resources_to_outcomes(
    connection: sqlite3.Connection,
) -> None:
    """Copy curriculum_resources rows into outcomes if outcomes is empty."""
    # Check if curriculum_resources table exists.
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "curriculum_resources" not in tables:
        return

    outcome_count = connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    if outcome_count > 0:
        return

    resource_count = connection.execute(
        "SELECT COUNT(*) FROM curriculum_resources"
    ).fetchone()[0]
    if resource_count == 0:
        return

    import json

    rows = connection.execute(
        "SELECT resource_id, payload, updated_at FROM curriculum_resources"
    ).fetchall()
    for resource_id, payload_json, updated_at in rows:
        payload = json.loads(payload_json)
        # Map old field names to new field names.
        payload["outcome_id"] = payload.pop("resource_id", resource_id)
        if "body" in payload:
            payload["description"] = payload.pop("body")
        payload.pop("source_type", None)
        payload.pop("learning_objective_ids", None)
        if "strand_id" not in payload:
            payload["strand_id"] = ""
        connection.execute(
            """
            INSERT INTO outcomes(outcome_id, payload, updated_at)
            VALUES (?, ?, ?)
            """,
            (payload["outcome_id"], json.dumps(payload), updated_at),
        )
