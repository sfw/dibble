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
