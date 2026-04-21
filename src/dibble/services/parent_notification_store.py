from __future__ import annotations

import json
import sqlite3

from dibble.models.household import ParentNotification


class SQLiteParentNotificationStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, notification: ParentNotification) -> ParentNotification:
        existing = self._conn.execute(
            """
            SELECT payload FROM parent_notifications
            WHERE dedupe_key = ?
            """,
            (notification.dedupe_key,),
        ).fetchone()
        resolved = notification
        if existing is not None:
            existing_notification = ParentNotification.model_validate(
                json.loads(str(existing[0]))
            )
            resolved = notification.model_copy(
                update={
                    "notification_id": existing_notification.notification_id,
                    "created_at": existing_notification.created_at,
                    "status": (
                        existing_notification.status
                        if notification.status == "unread"
                        else notification.status
                    ),
                }
            )
        self._conn.execute(
            """
            INSERT INTO parent_notifications(
                notification_id, household_id, learner_id, dedupe_key, payload, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(notification_id) DO UPDATE SET
                household_id = excluded.household_id,
                learner_id = excluded.learner_id,
                dedupe_key = excluded.dedupe_key,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                resolved.notification_id,
                resolved.household_id,
                resolved.learner_id,
                resolved.dedupe_key,
                resolved.model_dump_json(),
                resolved.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return resolved

    def list_for_household(self, *, household_id: str) -> list[ParentNotification]:
        rows = self._conn.execute(
            """
            SELECT payload FROM parent_notifications
            WHERE household_id = ?
            ORDER BY updated_at DESC
            """,
            (household_id,),
        ).fetchall()
        return [
            ParentNotification.model_validate(json.loads(str(payload)))
            for (payload,) in rows
        ]

    def get(self, notification_id: str) -> ParentNotification | None:
        row = self._conn.execute(
            "SELECT payload FROM parent_notifications WHERE notification_id = ?",
            (notification_id,),
        ).fetchone()
        if row is None:
            return None
        return ParentNotification.model_validate(json.loads(str(row[0])))
