"""Tests for the surplus practice block cache."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GeneratedBlock,
    GeneratedContent,
    GenerationMetadata,
    GenerationRequest,
    GenerationResponse,
    InterventionType,
    MultipleChoiceInteraction,
    MultipleChoiceOption,
)
from dibble.models.profile import LearnerProfile
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.surplus_practice_cache import SurplusPracticeCache
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


STUDENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture()
def store(tmp_path):
    db_path = str(tmp_path / "surplus.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    return SQLiteGeneratedContentStore(conn)


@pytest.fixture()
def cache(store):
    return SurplusPracticeCache(store, cache_ttl_seconds=3600)


def _practice_block(title: str = "Q1") -> GeneratedBlock:
    return GeneratedBlock(
        kind="practice_problem",
        title=title,
        body="Solve this.",
        interaction=MultipleChoiceInteraction(
            prompt="What is 2+2?",
            options=[
                MultipleChoiceOption(option_id="A", label="A", body="3"),
                MultipleChoiceOption(option_id="B", label="B", body="4"),
            ],
            correct_option_id="B",
        ),
    )


def _summary_block() -> GeneratedBlock:
    return GeneratedBlock(kind="summary", title="Summary", body="Context here.")


def _parent_content(
    blocks: list[GeneratedBlock],
    student_id: UUID = STUDENT_ID,
) -> GeneratedContent:
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    metadata = GenerationMetadata(
        quality_score=0.8, validation_passed=True, grounding_count=0
    )
    gen_id = str(uuid4())
    response = GenerationResponse(
        student_id=student_id,
        route=route,
        blocks=blocks,
        curriculum_context=["fractions"],
        grounding=[],
        safety_notes=[],
        generation_id=gen_id,
        generation_metadata=metadata,
    )
    now = datetime.now(timezone.utc)
    return GeneratedContent(
        generation_id=gen_id,
        student_id=student_id,
        content_type="practice_problem",
        request_context={
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "learning_session_id": "session-1",
        },
        response=response,
        quality=metadata,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _request(student_id: UUID = STUDENT_ID) -> GenerationRequest:
    return GenerationRequest(
        student_id=student_id,
        target_kc_ids=["KC-1"],
        learning_session_id="session-1",
    )


def _profile(student_id: UUID = STUDENT_ID) -> LearnerProfile:
    return LearnerProfile(student_id=student_id, grade_level="7")


# ------------------------------------------------------------------
# split_practice_blocks
# ------------------------------------------------------------------


class TestSplitPracticeBlocks:
    def test_single_practice_unchanged(self):
        blocks = [_summary_block(), _practice_block("Q1")]
        delivery, surplus = SurplusPracticeCache.split_practice_blocks(blocks)
        assert delivery == blocks
        assert surplus == []

    def test_two_practice_splits(self):
        blocks = [_summary_block(), _practice_block("Q1"), _practice_block("Q2")]
        delivery, surplus = SurplusPracticeCache.split_practice_blocks(blocks)
        assert len(delivery) == 2  # summary + Q1
        assert delivery[0].kind == "summary"
        assert delivery[1].title == "Q1"
        assert len(surplus) == 1
        assert surplus[0].title == "Q2"

    def test_three_practice_splits(self):
        blocks = [
            _summary_block(),
            _practice_block("Q1"),
            _practice_block("Q2"),
            _practice_block("Q3"),
        ]
        delivery, surplus = SurplusPracticeCache.split_practice_blocks(blocks)
        assert len(delivery) == 2
        assert len(surplus) == 2
        assert surplus[0].title == "Q2"
        assert surplus[1].title == "Q3"

    def test_no_practice_unchanged(self):
        blocks = [_summary_block(), GeneratedBlock(kind="instruction", title="I", body="text")]
        delivery, surplus = SurplusPracticeCache.split_practice_blocks(blocks)
        assert delivery == blocks
        assert surplus == []

    def test_only_practice_no_summary(self):
        blocks = [_practice_block("Q1"), _practice_block("Q2")]
        delivery, surplus = SurplusPracticeCache.split_practice_blocks(blocks)
        assert len(delivery) == 1
        assert delivery[0].title == "Q1"
        assert len(surplus) == 1


# ------------------------------------------------------------------
# cache_surplus + pop_surplus
# ------------------------------------------------------------------


class TestCacheAndPop:
    def test_cache_and_pop_returns_surplus(self, cache):
        summary = _summary_block()
        surplus_blocks = [_practice_block("Q2")]
        parent = _parent_content([summary, _practice_block("Q1")])
        req = _request()
        profile = _profile()

        cache.cache_surplus(
            surplus_blocks=surplus_blocks,
            non_practice_blocks=[summary],
            parent_content=parent,
            profile=profile,
            request=req,
        )

        popped = cache.pop_surplus(
            student_id=STUDENT_ID,
            learning_session_id="session-1",
        )
        assert popped is not None
        assert popped.generation_id != parent.generation_id
        practice_blocks = [b for b in popped.response.blocks if b.kind == "practice_problem"]
        assert len(practice_blocks) == 1
        assert practice_blocks[0].title == "Q2"

    def test_pop_returns_none_when_empty(self, cache):
        popped = cache.pop_surplus(
            student_id=STUDENT_ID,
            learning_session_id="session-1",
        )
        assert popped is None

    def test_pop_consumes_entry(self, cache):
        summary = _summary_block()
        surplus_blocks = [_practice_block("Q2")]
        parent = _parent_content([summary, _practice_block("Q1")])

        cache.cache_surplus(
            surplus_blocks=surplus_blocks,
            non_practice_blocks=[summary],
            parent_content=parent,
            profile=_profile(),
            request=_request(),
        )

        first = cache.pop_surplus(student_id=STUDENT_ID, learning_session_id="session-1")
        assert first is not None
        second = cache.pop_surplus(student_id=STUDENT_ID, learning_session_id="session-1")
        assert second is None

    def test_multiple_surplus_served_in_order(self, cache):
        summary = _summary_block()
        surplus_blocks = [_practice_block("Q2"), _practice_block("Q3")]
        parent = _parent_content([summary, _practice_block("Q1")])

        cache.cache_surplus(
            surplus_blocks=surplus_blocks,
            non_practice_blocks=[summary],
            parent_content=parent,
            profile=_profile(),
            request=_request(),
        )

        first = cache.pop_surplus(student_id=STUDENT_ID, learning_session_id="session-1")
        assert first is not None
        q2_blocks = [b for b in first.response.blocks if b.kind == "practice_problem"]
        assert q2_blocks[0].title == "Q2"

        second = cache.pop_surplus(student_id=STUDENT_ID, learning_session_id="session-1")
        assert second is not None
        q3_blocks = [b for b in second.response.blocks if b.kind == "practice_problem"]
        assert q3_blocks[0].title == "Q3"

        third = cache.pop_surplus(student_id=STUDENT_ID, learning_session_id="session-1")
        assert third is None


# ------------------------------------------------------------------
# Invalidation piggyback
# ------------------------------------------------------------------


class TestInvalidation:
    def test_surplus_has_predictive_warm_flag(self, cache):
        summary = _summary_block()
        surplus_blocks = [_practice_block("Q2")]
        parent = _parent_content([summary, _practice_block("Q1")])

        cache.cache_surplus(
            surplus_blocks=surplus_blocks,
            non_practice_blocks=[summary],
            parent_content=parent,
            profile=_profile(),
            request=_request(),
        )

        popped = cache.pop_surplus(student_id=STUDENT_ID, learning_session_id="session-1")
        assert popped is not None
        assert popped.request_context.get("is_predictive_warm") is True
        assert popped.request_context.get("is_surplus_practice") is True


# ------------------------------------------------------------------
# Session isolation
# ------------------------------------------------------------------


class TestSessionIsolation:
    def test_different_session_not_served(self, cache):
        summary = _summary_block()
        surplus_blocks = [_practice_block("Q2")]
        parent = _parent_content([summary, _practice_block("Q1")])

        cache.cache_surplus(
            surplus_blocks=surplus_blocks,
            non_practice_blocks=[summary],
            parent_content=parent,
            profile=_profile(),
            request=_request(),
        )

        popped = cache.pop_surplus(
            student_id=STUDENT_ID,
            learning_session_id="different-session",
        )
        assert popped is None


# ------------------------------------------------------------------
# TTL
# ------------------------------------------------------------------


class TestTTL:
    def test_zero_ttl_does_not_cache(self, store):
        no_cache = SurplusPracticeCache(store, cache_ttl_seconds=0)
        summary = _summary_block()
        surplus_blocks = [_practice_block("Q2")]
        parent = _parent_content([summary, _practice_block("Q1")])

        stored = no_cache.cache_surplus(
            surplus_blocks=surplus_blocks,
            non_practice_blocks=[summary],
            parent_content=parent,
            profile=_profile(),
            request=_request(),
        )
        assert stored == 0
