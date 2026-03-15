from __future__ import annotations

from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_prompt_outcomes import GenerationPromptOutcomeScorer
from dibble.storage import ensure_database


def test_generation_prompt_outcome_scorer_uses_follow_up_observation(tmp_path):
    database_path = str(tmp_path / "generation-outcomes.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "content_type": "worked_example",
            "prompt_template_name": "worked_example.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.76,
            "validation_passed": True,
            "grounding_count": 1,
            "target_kc_ids": ["KC-1"],
        },
    )
    observation_event = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "observed_content_type": "worked_example",
            "task_type": "worked_example",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.28,
            "confidence_calibration": 0.82,
            "help_seeking": "low",
        },
    )

    scorer = GenerationPromptOutcomeScorer()
    sample = scorer.score(generation_event=generation_event, candidate_observations=[observation_event])

    assert sample.downstream_outcome_score is not None
    assert sample.downstream_outcome_score > 0.7
    assert sample.composite_score > sample.quality_score


def test_generation_prompt_outcome_scorer_returns_none_without_follow_up_observation(tmp_path):
    database_path = str(tmp_path / "generation-outcomes-none.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(uuid4()),
        payload={
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.baseline",
            "prompt_template_variant": "baseline",
            "quality_score": 0.81,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )

    sample = GenerationPromptOutcomeScorer().score(generation_event=generation_event, candidate_observations=[])

    assert sample.downstream_outcome_score is None
    assert sample.composite_score == 0.81


def test_generation_prompt_outcome_scorer_prefers_exact_generation_link_over_closest_time(tmp_path):
    database_path = str(tmp_path / "generation-outcomes-linked.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-exact",
            "content_type": "practice_problem",
            "prompt_template_name": "practice_problem.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.8,
            "validation_passed": True,
            "grounding_count": 1,
            "target_kc_ids": ["KC-1"],
        },
    )
    closer_but_unlinked = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "other-gen",
            "observed_content_type": "practice_problem",
            "task_type": "practice",
            "target_kc_ids": ["KC-2"],
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.9,
            "confidence_calibration": 0.2,
            "help_seeking": "high",
        },
    )
    exact_match = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-exact",
            "observed_content_type": "practice_problem",
            "task_type": "practice",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.3,
            "confidence_calibration": 0.78,
            "help_seeking": "low",
        },
    )

    sample = GenerationPromptOutcomeScorer().score(
        generation_event=generation_event,
        candidate_observations=[closer_but_unlinked, exact_match],
    )

    assert sample.downstream_outcome_score is not None
    assert sample.downstream_outcome_score > 0.7
