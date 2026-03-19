from __future__ import annotations

import sqlite3

from dibble.models.classroom_membership import (
    ClassroomMembership,
    ClassroomMembershipRole,
    ClassroomMembershipUpsert,
)


class SQLiteClassroomMembershipStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(
        self, membership: ClassroomMembershipUpsert
    ) -> ClassroomMembership:
        persisted = ClassroomMembership(**membership.model_dump())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO classroom_memberships(classroom_id, user_id, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(classroom_id, user_id, role) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (
                    persisted.classroom_id,
                    persisted.user_id,
                    persisted.role.value,
                    persisted.created_at.isoformat(),
                    persisted.updated_at.isoformat(),
                ),
            )
            connection.commit()
        return persisted

    def replace_for_classroom(
        self,
        *,
        classroom_id: str,
        role: ClassroomMembershipRole,
        user_ids: list[str],
    ) -> list[ClassroomMembership]:
        normalized = sorted(set(user_ids))
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "DELETE FROM classroom_memberships WHERE classroom_id = ? AND role = ?",
                (classroom_id, role.value),
            )
            for user_id in normalized:
                membership = ClassroomMembership(
                    classroom_id=classroom_id,
                    user_id=user_id,
                    role=role,
                )
                connection.execute(
                    """
                    INSERT INTO classroom_memberships(classroom_id, user_id, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        membership.classroom_id,
                        membership.user_id,
                        membership.role.value,
                        membership.created_at.isoformat(),
                        membership.updated_at.isoformat(),
                    ),
                )
            connection.commit()
        return [
            ClassroomMembership(
                classroom_id=classroom_id,
                user_id=user_id,
                role=role,
            )
            for user_id in normalized
        ]

    def replace_for_user(
        self,
        *,
        user_id: str,
        role: ClassroomMembershipRole,
        classroom_ids: list[str],
    ) -> list[ClassroomMembership]:
        normalized = sorted(set(classroom_ids))
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "DELETE FROM classroom_memberships WHERE user_id = ? AND role = ?",
                (user_id, role.value),
            )
            for classroom_id in normalized:
                membership = ClassroomMembership(
                    classroom_id=classroom_id,
                    user_id=user_id,
                    role=role,
                )
                connection.execute(
                    """
                    INSERT INTO classroom_memberships(classroom_id, user_id, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        membership.classroom_id,
                        membership.user_id,
                        membership.role.value,
                        membership.created_at.isoformat(),
                        membership.updated_at.isoformat(),
                    ),
                )
            connection.commit()
        return [
            ClassroomMembership(
                classroom_id=classroom_id,
                user_id=user_id,
                role=role,
            )
            for classroom_id in normalized
        ]

    def list_classroom_user_ids(
        self,
        classroom_id: str,
        *,
        role: ClassroomMembershipRole | None = None,
    ) -> list[str]:
        query = "SELECT user_id FROM classroom_memberships WHERE classroom_id = ?"
        params: list[str] = [classroom_id]
        if role is not None:
            query += " AND role = ?"
            params.append(role.value)
        query += " ORDER BY user_id ASC"
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [str(row[0]) for row in rows]

    def list_user_classroom_ids(
        self,
        user_id: str,
        *,
        role: ClassroomMembershipRole | None = None,
    ) -> list[str]:
        query = "SELECT classroom_id FROM classroom_memberships WHERE user_id = ?"
        params: list[str] = [user_id]
        if role is not None:
            query += " AND role = ?"
            params.append(role.value)
        query += " ORDER BY classroom_id ASC"
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [str(row[0]) for row in rows]

    def delete_for_user(self, user_id: str) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "DELETE FROM classroom_memberships WHERE user_id = ?",
                (user_id,),
            )
            connection.commit()
