"""Split multi-block practice responses and cache surplus questions.

When the LLM generates 2-3 practice_problem blocks in a single response,
only the first is delivered to the learner.  The remaining blocks are stored
as individual ``GeneratedContent`` entries so they can be served instantly
on the next continue request, buying time before the next LLM generation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from dibble.models.generation import (
    GeneratedBlock,
    GeneratedContent,
    GenerationRequest,
)
from dibble.models.profile import LearnerProfile
from dibble.services.protocols import GeneratedContentStore

logger = logging.getLogger(__name__)


class SurplusPracticeCache:
    """Manages splitting and caching of surplus practice blocks."""

    def __init__(
        self,
        generated_content_store: GeneratedContentStore,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.store = generated_content_store
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def split_practice_blocks(
        blocks: list[GeneratedBlock],
    ) -> tuple[list[GeneratedBlock], list[GeneratedBlock]]:
        """Separate *blocks* into delivery blocks and surplus practice blocks.

        Returns ``(delivery, surplus)`` where *delivery* contains all
        non-practice blocks plus the **first** ``practice_problem`` block,
        and *surplus* contains any remaining ``practice_problem`` blocks.
        """
        non_practice: list[GeneratedBlock] = []
        practice: list[GeneratedBlock] = []
        for block in blocks:
            if block.kind == "practice_problem":
                practice.append(block)
            else:
                non_practice.append(block)

        if len(practice) <= 1:
            return blocks, []

        delivery = non_practice + practice[:1]
        surplus = practice[1:]
        return delivery, surplus

    def cache_surplus(
        self,
        *,
        surplus_blocks: list[GeneratedBlock],
        non_practice_blocks: list[GeneratedBlock],
        parent_content: GeneratedContent,
        profile: LearnerProfile,
        request: GenerationRequest,
    ) -> int:
        """Store each surplus practice block as a separate cache entry.

        Each entry wraps the surplus block alongside the original
        non-practice blocks (e.g. the summary) so the learner still sees
        context when the surplus is served.

        Returns the number of surplus entries stored.
        """
        if not surplus_blocks or self.cache_ttl_seconds <= 0:
            return 0

        stored = 0
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.cache_ttl_seconds)

        for index, practice_block in enumerate(surplus_blocks):
            cache_key = self._surplus_cache_key(
                student_id=profile.student_id,
                learning_session_id=request.learning_session_id,
                sequence_index=index,
            )
            blocks = list(non_practice_blocks) + [practice_block]
            response = parent_content.response.model_copy(
                update={
                    "blocks": blocks,
                    "generation_id": str(uuid4()),
                }
            )
            request_context = dict(parent_content.request_context)
            request_context["is_surplus_practice"] = True
            request_context["is_predictive_warm"] = True
            request_context["source_generation_id"] = parent_content.generation_id
            request_context["surplus_sequence_index"] = index

            content = GeneratedContent(
                generation_id=response.generation_id or str(uuid4()),
                student_id=profile.student_id,
                content_type=parent_content.content_type,
                request_context=request_context,
                response=response,
                quality=parent_content.quality.model_copy(
                    update={"cache_hit": False}
                ),
                created_at=now,
                expires_at=expires_at,
            )
            self.store.upsert(cache_key=cache_key, content=content)
            stored += 1

        logger.debug(
            "Cached %d surplus practice blocks for student %s (session %s)",
            stored,
            profile.student_id,
            request.learning_session_id,
        )
        return stored

    def pop_surplus(
        self,
        *,
        student_id: UUID,
        learning_session_id: str | None,
    ) -> GeneratedContent | None:
        """Retrieve and expire the next surplus practice block, if any."""
        cache_key = self._surplus_cache_key(
            student_id=student_id,
            learning_session_id=learning_session_id,
            sequence_index=0,
        )
        content = self.store.get_fresh(cache_key=cache_key)
        if content is None:
            return None

        # Expire the entry so it is not served again.
        expired = content.model_copy(
            update={"expires_at": datetime.now(timezone.utc)}
        )
        self.store.refresh(content=expired)

        # Promote sequence_index=1 → 0 so the next pop finds it.
        self._promote_surplus(
            student_id=student_id,
            learning_session_id=learning_session_id,
        )

        logger.debug(
            "Popped surplus practice block %s for student %s",
            content.generation_id,
            student_id,
        )
        return content

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _promote_surplus(
        self,
        *,
        student_id: UUID,
        learning_session_id: str | None,
    ) -> None:
        """Shift surplus entries down by one so index 1 becomes index 0."""
        index = 1
        while True:
            old_key = self._surplus_cache_key(
                student_id=student_id,
                learning_session_id=learning_session_id,
                sequence_index=index,
            )
            entry = self.store.get_fresh(cache_key=old_key)
            if entry is None:
                break
            # Expire old slot.
            self.store.refresh(
                content=entry.model_copy(
                    update={"expires_at": datetime.now(timezone.utc)}
                )
            )
            # Re-store at index - 1 with a fresh generation_id to avoid
            # unique constraint conflicts.
            new_key = self._surplus_cache_key(
                student_id=student_id,
                learning_session_id=learning_session_id,
                sequence_index=index - 1,
            )
            new_gen_id = str(uuid4())
            new_context = dict(entry.request_context)
            new_context["surplus_sequence_index"] = index - 1
            new_response = entry.response.model_copy(
                update={"generation_id": new_gen_id}
            )
            promoted = entry.model_copy(
                update={
                    "generation_id": new_gen_id,
                    "request_context": new_context,
                    "response": new_response,
                    "expires_at": entry.expires_at,
                }
            )
            self.store.upsert(cache_key=new_key, content=promoted)
            index += 1

    @staticmethod
    def _surplus_cache_key(
        *,
        student_id: UUID,
        learning_session_id: str | None,
        sequence_index: int,
    ) -> str:
        session = learning_session_id or "none"
        return f"surplus:{student_id}:{session}:{sequence_index}"
