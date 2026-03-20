"""Shared SQLite connection factory with WAL mode and recommended pragmas."""

from __future__ import annotations

import sqlite3


def create_connection(database_path: str) -> sqlite3.Connection:
    """Create a long-lived SQLite connection configured for concurrent use.

    - WAL journal mode allows concurrent readers alongside a single writer.
    - ``check_same_thread=False`` lets FastAPI's thread-pool workers share the
      connection safely (SQLite serialises writes internally).
    - ``foreign_keys=ON`` enforces referential integrity.
    - ``busy_timeout`` avoids immediate SQLITE_BUSY errors under contention.
    """
    conn = sqlite3.connect(database_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
