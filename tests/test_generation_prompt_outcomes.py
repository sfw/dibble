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

    assert sample.downstream_observation_score is not None
    assert sample.downstream_observation_score > 0.7
    assert sample.run_summary_score is not None
    assert sample.run_calibration_signal == "positive"
    assert sample.run_calibration_confidence >= 0.7
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

    assert sample.downstream_observation_score is None
    assert sample.downstream_assessment_score is None
    assert sample.run_summary_score is None
    assert sample.run_calibration_signal == "insufficient"
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

    assert sample.downstream_observation_score is not None
    assert sample.downstream_observation_score > 0.7
    assert sample.run_calibration_signal == "positive"


def test_generation_prompt_outcome_scorer_prefers_same_learning_session_when_generation_id_missing(tmp_path):
    database_path = str(tmp_path / "generation-outcomes-session.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-1",
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.78,
            "validation_passed": True,
            "grounding_count": 1,
            "target_kc_ids": ["KC-1"],
        },
    )
    same_student_wrong_session = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "other-session",
            "observed_content_type": "micro_explanation",
            "task_type": "explanation",
            "target_kc_ids": ["KC-1"],
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.88,
            "confidence_calibration": 0.22,
            "help_seeking": "high",
        },
    )
    same_session = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-1",
            "observed_content_type": "micro_explanation",
            "task_type": "explanation",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.2,
            "confidence_calibration": 0.84,
            "help_seeking": "low",
        },
    )

    sample = GenerationPromptOutcomeScorer().score(
        generation_event=generation_event,
        candidate_observations=[same_student_wrong_session, same_session],
    )

    assert sample.downstream_observation_score is not None
    assert sample.downstream_observation_score > 0.75
    assert sample.run_summary_score is not None


def test_generation_prompt_outcome_scorer_uses_same_session_socratic_assessment(tmp_path):
    database_path = str(tmp_path / "generation-outcomes-assessment.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-2",
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.74,
            "validation_passed": True,
            "grounding_count": 1,
            "target_kc_ids": ["KC-1"],
        },
    )
    assessment_event = audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-2",
            "target_kc_ids": ["KC-1"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.82,
            "profile_update_applied": True,
        },
    )

    sample = GenerationPromptOutcomeScorer().score(
        generation_event=generation_event,
        candidate_observations=[],
        candidate_assessments=[assessment_event],
    )

    assert sample.downstream_assessment_score is not None
    assert sample.downstream_assessment_score > 0.8
    assert sample.run_summary_score is not None
    assert sample.run_calibration_signal == "positive"
    assert sample.composite_score > sample.quality_score


def test_generation_prompt_outcome_scorer_aggregates_multi_event_session_trace(tmp_path):
    database_path = str(tmp_path / "generation-outcomes-trace.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-trace",
            "content_type": "worked_example",
            "prompt_template_name": "worked_example.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.7,
            "validation_passed": True,
            "grounding_count": 1,
            "target_kc_ids": ["KC-1"],
        },
    )
    first_observation = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-trace",
            "observed_content_type": "worked_example",
            "task_type": "worked_example",
            "target_kc_ids": ["KC-1"],
            "engagement": "medium",
            "frustration": "low",
            "total_load": 0.35,
            "confidence_calibration": 0.72,
            "help_seeking": "low",
        },
    )
    second_observation = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-trace",
            "observed_content_type": "worked_example",
            "task_type": "worked_example",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.22,
            "confidence_calibration": 0.83,
            "help_seeking": "low",
        },
    )
    first_assessment = audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-trace",
            "target_kc_ids": ["KC-1"],
            "evidence_strength": "emerging",
            "evidence_score": 0.65,
            "profile_update_applied": False,
        },
    )
    second_assessment = audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-trace",
            "target_kc_ids": ["KC-1"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.84,
            "profile_update_applied": True,
        },
    )

    sample = GenerationPromptOutcomeScorer().score(
        generation_event=generation_event,
        candidate_observations=[first_observation, second_observation],
        candidate_assessments=[first_assessment, second_assessment],
    )

    assert sample.observation_match_count == 2
    assert sample.assessment_match_count == 2
    assert sample.downstream_observation_score is not None
    assert sample.downstream_observation_score > 0.7
    assert sample.downstream_assessment_score is not None
    assert sample.downstream_assessment_score > 0.7
    assert sample.run_summary_score is not None
    assert sample.run_event_count == 4
    assert sample.composite_score > sample.quality_score


def test_generation_prompt_outcome_scorer_uses_later_same_session_run_outcome(tmp_path):
    database_path = str(tmp_path / "generation-outcomes-session-run.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    first_generation = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-1",
            "learning_session_id": "learn-run-1",
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.72,
            "validation_passed": True,
            "grounding_count": 1,
            "target_kc_ids": ["KC-1"],
        },
    )
    second_generation = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-2",
            "learning_session_id": "learn-run-1",
            "content_type": "practice_problem",
            "prompt_template_name": "practice_problem.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.8,
            "validation_passed": True,
            "grounding_count": 1,
            "target_kc_ids": ["KC-1"],
        },
    )
    later_observation = audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-run-1",
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.24,
            "confidence_calibration": 0.84,
            "help_seeking": "low",
        },
    )
    later_assessment = audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-run-1",
            "target_kc_ids": ["KC-1"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.82,
            "profile_update_applied": True,
        },
    )

    sample = GenerationPromptOutcomeScorer().score(
        generation_event=first_generation,
        candidate_generations=[first_generation, second_generation],
        candidate_observations=[later_observation],
        candidate_assessments=[later_assessment],
    )

    assert sample.session_outcome_score is not None
    assert sample.session_outcome_score > 0.75
    assert sample.session_generation_depth == 1
    assert sample.session_outcome_event_count == 2
    assert sample.run_summary_score is not None
    assert sample.run_calibration_signal == "positive"
    assert sample.run_event_count == 2
    assert sample.composite_score > sample.quality_score
