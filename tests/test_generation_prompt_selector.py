from __future__ import annotations

from dibble.models.generation import RequestedContentType
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_prompt_selector import GenerationPromptSelector
from dibble.storage import ensure_database


def test_generation_prompt_selector_prefers_higher_quality_variant(tmp_path):
    database_path = str(tmp_path / "generation-selector.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(audit_store=audit_store, min_samples_per_variant=2)

    for quality_score in (0.92, 0.95):
        audit_store.append(
            event_type="content.generate",
            status="success",
            payload={
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": quality_score,
                "validation_passed": True,
                "grounding_count": 1,
            },
        )
    for quality_score in (0.71, 0.74):
        audit_store.append(
            event_type="content.generate",
            status="success",
            payload={
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": quality_score,
                "validation_passed": True,
                "grounding_count": 1,
            },
        )

    assert (
        selector.select_variant(content_type=RequestedContentType.worked_example, fallback_variant="baseline")
        == "guided_reflection"
    )


def test_generation_prompt_selector_falls_back_when_samples_are_sparse(tmp_path):
    database_path = str(tmp_path / "generation-selector-sparse.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(audit_store=audit_store, min_samples_per_variant=2)

    audit_store.append(
        event_type="content.generate",
        status="success",
        payload={
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.94,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )

    assert (
        selector.select_variant(content_type=RequestedContentType.micro_explanation, fallback_variant="baseline")
        == "baseline"
    )


def test_generation_prompt_selector_can_prefer_better_downstream_outcome(tmp_path):
    database_path = str(tmp_path / "generation-selector-outcomes.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(audit_store=audit_store, min_samples_per_variant=2)
    student_a = "00000000-0000-0000-0000-000000000101"
    student_b = "00000000-0000-0000-0000-000000000102"

    for student_id in (student_a, student_b):
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "content_type": "practice_problem",
                "prompt_template_name": "practice_problem.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": 0.82,
                "validation_passed": True,
                "grounding_count": 1,
            },
        )
        audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=student_id,
            payload={
                "engagement": "high",
                "frustration": "low",
                "total_load": 0.25,
                "confidence_calibration": 0.8,
                "help_seeking": "low",
            },
        )

    for student_id in ("00000000-0000-0000-0000-000000000201", "00000000-0000-0000-0000-000000000202"):
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "content_type": "practice_problem",
                "prompt_template_name": "practice_problem.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": 0.9,
                "validation_passed": True,
                "grounding_count": 1,
            },
        )
        audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=student_id,
            payload={
                "engagement": "low",
                "frustration": "high",
                "total_load": 0.88,
                "confidence_calibration": 0.32,
                "help_seeking": "high",
            },
        )

    assert (
        selector.select_variant(content_type=RequestedContentType.practice_problem, fallback_variant="baseline")
        == "guided_reflection"
    )
