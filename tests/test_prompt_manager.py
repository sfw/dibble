from uuid import UUID

from dibble.services.prompt_manager import PromptManager
from dibble.models.generation import GenerationModeCalibration, RequestedContentType
from dibble.services.socratic_prompt_selector import SocraticPromptSelector
from dibble.services.generation_prompt_selector import GenerationPromptSelector
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def test_prompt_manager_uses_override_variant():
    manager = PromptManager(
        library_version="2.1",
        experiment_enabled=True,
        variant_override="guided_reflection",
    )

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
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
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


def test_prompt_manager_can_adaptively_select_generation_variant(tmp_path):
    database_path = str(tmp_path / "prompt-manager-generation-selector.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    for quality_score in (0.91, 0.96):
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
    for quality_score in (0.72, 0.74):
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

    manager = PromptManager(
        library_version="1.0",
        experiment_enabled=True,
        adaptive_selection_enabled=True,
        generation_prompt_selector=GenerationPromptSelector(audit_store),
    )

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000123"),
        content_type=RequestedContentType.worked_example,
    )

    assert selection.template_variant == "guided_reflection"
    assert selection.template_name == "worked_example.guided_reflection"


def test_prompt_manager_can_use_recent_socratic_steering_for_generation_variant(
    tmp_path,
):
    database_path = str(tmp_path / "prompt-manager-socratic-steering.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    manager = PromptManager(
        library_version="1.0",
        experiment_enabled=True,
        adaptive_selection_enabled=True,
        generation_prompt_selector=GenerationPromptSelector(audit_store),
    )

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000123"),
        content_type=RequestedContentType.practice_problem,
        mode_calibration=GenerationModeCalibration(
            session_source="session_controller",
            session_confidence=0.82,
            session_assessment_count=1,
            session_latest_prompt_style="scaffolded_step_back",
            session_latest_next_action="step_back",
            session_latest_evidence_strength="insufficient",
            socratic_steering_action="repair_then_model",
        ),
    )

    assert selection.template_variant == "guided_reflection"
    assert selection.template_name == "practice_problem.guided_reflection"


def test_prompt_manager_uses_guided_reflection_for_restate_then_apply_socratic_follow_up(
    tmp_path,
):
    database_path = str(tmp_path / "prompt-manager-socratic-restate.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    manager = PromptManager(
        library_version="1.0",
        experiment_enabled=True,
        adaptive_selection_enabled=True,
        generation_prompt_selector=GenerationPromptSelector(audit_store),
    )

    selection = manager.select(
        student_id=UUID("00000000-0000-0000-0000-000000000124"),
        content_type=RequestedContentType.practice_problem,
        mode_calibration=GenerationModeCalibration(
            session_source="session_controller",
            session_confidence=0.76,
            session_assessment_count=1,
            session_latest_prompt_style="clarification",
            session_latest_next_action="clarify",
            session_latest_evidence_strength="demonstrated",
            socratic_steering_action="restate_then_apply",
        ),
    )

    assert selection.template_variant == "guided_reflection"
    assert selection.template_name == "practice_problem.guided_reflection"
