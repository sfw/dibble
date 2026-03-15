from uuid import UUID

from dibble.services.prompt_manager import PromptManager
from dibble.models.generation import RequestedContentType
from dibble.services.socratic_prompt_selector import SocraticPromptSelector
from dibble.services.audit_store import SQLiteAuditStore
from dibble.storage import ensure_database


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


def test_prompt_manager_experiments_on_assessment_probes():
    manager = PromptManager(library_version="1.0", experiment_enabled=True)

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000123"),
        content_type=RequestedContentType.assessment_probe,
    )

    assert selection.template_variant in {"baseline", "causal_probe"}
    assert selection.template_name.startswith("assessment_probe.")


def test_prompt_manager_can_adaptively_select_assessment_probe_variant(tmp_path):
    database_path = str(tmp_path / "prompt-manager-selector.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    for score in (0.76, 0.82):
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            payload={
                "prompt_template_name": "assessment_probe.causal_probe",
                "prompt_template_variant": "causal_probe",
                "evidence_strength": "demonstrated",
                "evidence_score": score,
                "profile_update_applied": True,
            },
        )
    for score in (0.4, 0.44):
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            payload={
                "prompt_template_name": "assessment_probe.baseline",
                "prompt_template_variant": "baseline",
                "evidence_strength": "emerging",
                "evidence_score": score,
                "profile_update_applied": False,
            },
        )

    manager = PromptManager(
        library_version="1.0",
        experiment_enabled=True,
        adaptive_selection_enabled=True,
        socratic_prompt_selector=SocraticPromptSelector(audit_store),
    )

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000123"),
        content_type=RequestedContentType.assessment_probe,
    )

    assert selection.template_variant == "causal_probe"
    assert selection.template_name == "assessment_probe.causal_probe"
