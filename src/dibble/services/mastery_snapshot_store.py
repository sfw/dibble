from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.mastery_history import MasterySnapshot


class SQLiteMasterySnapshotStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def record(
        self,
        *,
        student_id: str,
        overall_kc_mastery: float,
        overall_lo_mastery: float,
        kc_count: int,
        lo_count: int,
        mastered_kc_count: int,
        struggling_kc_count: int,
        engagement: str,
        frustration: str,
        total_load: float,
    ) -> MasterySnapshot:
        snapshot_id = str(uuid4())
        now = datetime.now(timezone.utc)
        snapshot = MasterySnapshot(
            snapshot_id=snapshot_id,
            student_id=student_id,
            overall_kc_mastery=overall_kc_mastery,
            overall_lo_mastery=overall_lo_mastery,
            kc_count=kc_count,
            lo_count=lo_count,
            mastered_kc_count=mastered_kc_count,
            struggling_kc_count=struggling_kc_count,
            engagement=engagement,
            frustration=frustration,
            total_load=total_load,
            created_at=now,
        )
        self._conn.execute(
            """
            INSERT INTO mastery_snapshots(
                snapshot_id, student_id,
                overall_kc_mastery, overall_lo_mastery,
                kc_count, lo_count,
                mastered_kc_count, struggling_kc_count,
                engagement, frustration, total_load,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                student_id,
                round(overall_kc_mastery, 4),
                round(overall_lo_mastery, 4),
                kc_count,
                lo_count,
                mastered_kc_count,
                struggling_kc_count,
                engagement,
                frustration,
                round(total_load, 4),
                now.isoformat(),
            ),
        )
        self._conn.commit()
        return snapshot

    def list_for_student(
        self,
        *,
        student_id: str,
        days: int = 30,
        limit: int = 500,
    ) -> list[MasterySnapshot]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
        rows = self._conn.execute(
            """
            SELECT snapshot_id, student_id,
                   overall_kc_mastery, overall_lo_mastery,
                   kc_count, lo_count,
                   mastered_kc_count, struggling_kc_count,
                   engagement, frustration, total_load,
                   created_at
            FROM mastery_snapshots
            WHERE student_id = ? AND created_at >= ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (student_id, cutoff.isoformat(), limit),
        ).fetchall()
        return [self._row_to_snapshot(row) for row in rows]

    def _row_to_snapshot(self, row: tuple) -> MasterySnapshot:
        return MasterySnapshot(
            snapshot_id=row[0],
            student_id=row[1],
            overall_kc_mastery=row[2],
            overall_lo_mastery=row[3],
            kc_count=row[4],
            lo_count=row[5],
            mastered_kc_count=row[6],
            struggling_kc_count=row[7],
            engagement=row[8],
            frustration=row[9],
            total_load=row[10],
            created_at=datetime.fromisoformat(row[11]),
        )
