from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from dibble.models.generation import GeneratedContent


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class SQLiteGeneratedContentStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def upsert(self, *, cache_key: str, content: GeneratedContent) -> GeneratedContent:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO generated_content(
                    generation_id,
                    cache_key,
                    student_id,
                    content_type,
                    request_context,
                    workflow_summary_payload,
                    response_payload,
                    quality_payload,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    generation_id = excluded.generation_id,
                    student_id = excluded.student_id,
                    content_type = excluded.content_type,
                    request_context = excluded.request_context,
                    workflow_summary_payload = excluded.workflow_summary_payload,
                    response_payload = excluded.response_payload,
                    quality_payload = excluded.quality_payload,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    content.generation_id,
                    cache_key,
                    str(content.student_id),
                    content.content_type,
                    json.dumps(content.request_context),
                    (
                        content.workflow_summary.model_dump_json()
                        if content.workflow_summary is not None
                        else None
                    ),
                    content.response.model_dump_json(),
                    content.quality.model_dump_json(),
                    content.created_at.isoformat(),
                    content.expires_at.isoformat()
                    if content.expires_at is not None
                    else None,
                ),
            )
            connection.commit()
        return content

    def get_fresh(
        self, *, cache_key: str, now: datetime | None = None
    ) -> GeneratedContent | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT generation_id, student_id, content_type, request_context, workflow_summary_payload, response_payload, quality_payload, created_at, expires_at
                FROM generated_content
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()

        if row is None:
            return None

        generation_content = self._content_from_row(row)
        expires_at_value = generation_content.expires_at
        comparison_time = now or datetime.now(timezone.utc)
        if expires_at_value is not None and expires_at_value <= comparison_time:
            return None
        return generation_content

    def get(self, *, generation_id: str) -> GeneratedContent | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT generation_id, student_id, content_type, request_context, workflow_summary_payload, response_payload, quality_payload, created_at, expires_at
                FROM generated_content
                WHERE generation_id = ?
                """,
                (generation_id,),
            ).fetchone()
        if row is None:
            return None
        return self._content_from_row(row)

    def refresh(self, *, content: GeneratedContent) -> GeneratedContent:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE generated_content
                SET
                    student_id = ?,
                    content_type = ?,
                    request_context = ?,
                    workflow_summary_payload = ?,
                    response_payload = ?,
                    quality_payload = ?,
                    created_at = ?,
                    expires_at = ?
                WHERE generation_id = ?
                """,
                (
                    str(content.student_id),
                    content.content_type,
                    json.dumps(content.request_context),
                    (
                        content.workflow_summary.model_dump_json()
                        if content.workflow_summary is not None
                        else None
                    ),
                    content.response.model_dump_json(),
                    content.quality.model_dump_json(),
                    content.created_at.isoformat(),
                    content.expires_at.isoformat()
                    if content.expires_at is not None
                    else None,
                    content.generation_id,
                ),
            )
            connection.commit()
        return content

    def list_recent(self, *, limit: int = 50) -> list[GeneratedContent]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT generation_id, student_id, content_type, request_context, workflow_summary_payload, response_payload, quality_payload, created_at, expires_at
                FROM generated_content
                ORDER BY created_at DESC, generation_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._content_from_row(row) for row in rows]

    def list_recent_for_student(
        self,
        *,
        student_id: str,
        limit: int = 20,
        offset: int = 0,
        include_predictive_warm: bool = False,
    ) -> list[GeneratedContent]:
        with sqlite3.connect(self.database_path) as connection:
            if include_predictive_warm:
                rows = connection.execute(
                    """
                    SELECT generation_id, student_id, content_type, request_context, workflow_summary_payload, response_payload, quality_payload, created_at, expires_at
                    FROM generated_content
                    WHERE student_id = ?
                    ORDER BY created_at DESC, generation_id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (student_id, limit, offset),
                ).fetchall()
                return [self._content_from_row(row) for row in rows]

            rows = connection.execute(
                """
                SELECT generation_id, student_id, content_type, request_context, workflow_summary_payload, response_payload, quality_payload, created_at, expires_at
                FROM generated_content
                WHERE student_id = ?
                ORDER BY created_at DESC, generation_id DESC
                LIMIT ? OFFSET ?
                """,
                (student_id, (limit + offset) * 4, 0),
            ).fetchall()

        entries = [self._content_from_row(row) for row in rows]
        filtered = [
            entry
            for entry in entries
            if not bool(entry.request_context.get("is_predictive_warm"))
        ]
        return filtered[offset : offset + limit]

    def expire_predictive_content(
        self,
        *,
        student_id: str | None,
        target_kc_ids: list[str],
        target_lo_ids: list[str],
        learning_session_id: str | None = None,
        now: datetime | None = None,
        limit: int = 200,
    ) -> int:
        if student_id is None:
            return 0

        comparison_time = now or datetime.now(timezone.utc)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT generation_id, request_context, expires_at
                FROM generated_content
                WHERE student_id = ?
                ORDER BY created_at DESC, generation_id DESC
                LIMIT ?
                """,
                (student_id, limit),
            ).fetchall()

            generation_ids = [
                str(generation_id)
                for generation_id, request_context_json, expires_at in rows
                if _matches_predictive_invalidation(
                    request_context_json=request_context_json,
                    expires_at=expires_at,
                    target_kc_ids=target_kc_ids,
                    target_lo_ids=target_lo_ids,
                    learning_session_id=learning_session_id,
                    comparison_time=comparison_time,
                )
            ]
            if not generation_ids:
                return 0

            placeholders = ", ".join("?" for _ in generation_ids)
            connection.execute(
                f"""
                UPDATE generated_content
                SET expires_at = ?
                WHERE generation_id IN ({placeholders})
                """,
                (comparison_time.isoformat(), *generation_ids),
            )
            connection.commit()
        return len(generation_ids)

    def stats(self, *, now: datetime | None = None) -> dict[str, int]:
        comparison_time = now or datetime.now(timezone.utc)
        with sqlite3.connect(self.database_path) as connection:
            total_entries = connection.execute(
                "SELECT count(*) FROM generated_content"
            ).fetchone()[0]
            fresh_entries = connection.execute(
                """
                SELECT count(*) FROM generated_content
                WHERE expires_at IS NULL OR expires_at > ?
                """,
                (comparison_time.isoformat(),),
            ).fetchone()[0]

        return {
            "total_entries": int(total_entries),
            "fresh_entries": int(fresh_entries),
            "expired_entries": int(total_entries - fresh_entries),
        }

    def _content_from_row(self, row) -> GeneratedContent:
        (
            generation_id,
            student_id,
            content_type,
            request_context_json,
            workflow_summary_payload,
            response_payload,
            quality_payload,
            created_at,
            expires_at,
        ) = row
        return GeneratedContent.model_validate(
            {
                "generation_id": generation_id,
                "student_id": student_id,
                "content_type": content_type,
                "request_context": json.loads(request_context_json),
                "workflow_summary": (
                    json.loads(workflow_summary_payload)
                    if workflow_summary_payload is not None
                    else None
                ),
                "response": json.loads(response_payload),
                "quality": json.loads(quality_payload),
                "created_at": created_at,
                "expires_at": expires_at,
            }
        )


def _matches_predictive_invalidation(
    *,
    request_context_json: str,
    expires_at: str | None,
    target_kc_ids: list[str],
    target_lo_ids: list[str],
    learning_session_id: str | None,
    comparison_time: datetime,
) -> bool:
    expires_at_value = _parse_datetime(expires_at)
    if expires_at_value is not None and expires_at_value <= comparison_time:
        return False

    request_context = json.loads(request_context_json)
    if not bool(request_context.get("is_predictive_warm")):
        return False
    if (
        learning_session_id is not None
        and request_context.get("learning_session_id") != learning_session_id
    ):
        return False

    content_target_kc_ids = _string_list(request_context.get("target_kc_ids"))
    content_target_lo_ids = _string_list(request_context.get("target_lo_ids"))
    if not target_kc_ids and not target_lo_ids:
        return True
    if set(content_target_kc_ids).intersection(target_kc_ids):
        return True
    if set(content_target_lo_ids).intersection(target_lo_ids):
        return True
    return False


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
