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
                    response_payload,
                    quality_payload,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    generation_id = excluded.generation_id,
                    student_id = excluded.student_id,
                    content_type = excluded.content_type,
                    request_context = excluded.request_context,
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
                    content.response.model_dump_json(),
                    content.quality.model_dump_json(),
                    content.created_at.isoformat(),
                    content.expires_at.isoformat() if content.expires_at is not None else None,
                ),
            )
            connection.commit()
        return content

    def get_fresh(self, *, cache_key: str, now: datetime | None = None) -> GeneratedContent | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT generation_id, student_id, content_type, request_context, response_payload, quality_payload, created_at, expires_at
                FROM generated_content
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()

        if row is None:
            return None

        (
            generation_id,
            student_id,
            content_type,
            request_context_json,
            response_payload,
            quality_payload,
            created_at,
            expires_at,
        ) = row

        expires_at_value = _parse_datetime(expires_at)
        comparison_time = now or datetime.now(timezone.utc)
        if expires_at_value is not None and expires_at_value <= comparison_time:
            return None

        response = GeneratedContent.model_validate(
            {
                "generation_id": generation_id,
                "student_id": student_id,
                "content_type": content_type,
                "request_context": json.loads(request_context_json),
                "response": json.loads(response_payload),
                "quality": json.loads(quality_payload),
                "created_at": created_at,
                "expires_at": expires_at,
            }
        )
        return response

    def list_recent(self, *, limit: int = 50) -> list[GeneratedContent]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT generation_id, student_id, content_type, request_context, response_payload, quality_payload, created_at, expires_at
                FROM generated_content
                ORDER BY created_at DESC, generation_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            GeneratedContent.model_validate(
                {
                    "generation_id": generation_id,
                    "student_id": student_id,
                    "content_type": content_type,
                    "request_context": json.loads(request_context_json),
                    "response": json.loads(response_payload),
                    "quality": json.loads(quality_payload),
                    "created_at": created_at,
                    "expires_at": expires_at,
                }
            )
            for (
                generation_id,
                student_id,
                content_type,
                request_context_json,
                response_payload,
                quality_payload,
                created_at,
                expires_at,
            ) in rows
        ]
