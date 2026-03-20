"""Thread-local SQLite connection pool with WAL mode."""

from __future__ import annotations

import sqlite3
import threading


class ConnectionPool:
    """Vends one ``sqlite3.Connection`` per thread, all pointed at the same DB.

    WAL journal mode lets these per-thread connections read concurrently.
    Each connection is created lazily on first access and reused for the
    lifetime of the thread.
    """

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._local = threading.local()

    @property
    def connection(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = _open(self._database_path)
            self._local.conn = conn
        return conn

    # Allow stores to call pool.execute(...) / pool.fetchone(...) etc.
    # so the migration from self._conn to self._pool is a minimal rename.
    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor:  # type: ignore[assignment]
        return self.connection.execute(sql, parameters)

    def commit(self) -> None:
        self.connection.commit()


def _open(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def create_connection(database_path: str) -> ConnectionPool:
    """Create a thread-safe connection pool for the given database.

    Returns a ``ConnectionPool`` whose ``.execute()`` and ``.commit()``
    methods forward to a per-thread ``sqlite3.Connection``.  This is a
    drop-in replacement for a raw ``sqlite3.Connection`` in store classes.
    """
    return ConnectionPool(database_path)
