from __future__ import annotations

import json
import sqlite3

from dibble.models.household import Household


class SQLiteHouseholdStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, household: Household) -> Household:
        self._conn.execute(
            """
            INSERT INTO households(household_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(household_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                household.household_id,
                household.model_dump_json(),
                household.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return household

    def get(self, household_id: str) -> Household | None:
        row = self._conn.execute(
            "SELECT payload FROM households WHERE household_id = ?",
            (household_id,),
        ).fetchone()
        if row is None:
            return None
        return Household.model_validate(json.loads(str(row[0])))

    def get_by_parent_user_id(self, parent_user_id: str) -> Household | None:
        rows = self._conn.execute("SELECT payload FROM households").fetchall()
        for (payload,) in rows:
            household = Household.model_validate(json.loads(str(payload)))
            if any(
                profile.parent_user_id == parent_user_id
                for profile in household.parent_profiles
            ):
                return household
        return None
