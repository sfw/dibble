from uuid import UUID

from dibble.services.prompt_manager import PromptManager
from dibble.models.generation import RequestedContentType


def test_prompt_manager_uses_override_variant():
    manager = PromptManager(library_version="2.1", experiment_enabled=True, variant_override="guided_reflection")

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000123"),
        content_type=RequestedContentType.micro_explanation,
    )

    assert selection.template_name == "micro_explanation.guided_reflection"
    assert selection.template_version == "2.1"
    assert selection.template_variant == "guided_reflection"


def test_prompt_manager_buckets_supported_content_types_when_experiment_enabled():
    manager = PromptManager(library_version="1.0", experiment_enabled=True)

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000123"),
        content_type=RequestedContentType.worked_example,
    )

    assert selection.template_variant in {"baseline", "guided_reflection"}
    assert selection.template_name.startswith("worked_example.")


def test_prompt_manager_keeps_unspecialized_content_on_baseline():
    manager = PromptManager(library_version="1.0", experiment_enabled=True)

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000123"),
        content_type=RequestedContentType.remedial_micro_module,
    )

    assert selection.template_variant == "baseline"
    assert selection.template_name == "remedial_micro_module.baseline"
