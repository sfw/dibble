from __future__ import annotations

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.socratic_prompt_selector import SocraticPromptSelector
from dibble.storage import ensure_database


def test_socratic_prompt_selector_prefers_higher_performing_variant(tmp_path):
    database_path = str(tmp_path / "selector.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = SocraticPromptSelector(audit_store=audit_store, min_samples_per_variant=2)

    for score in (0.74, 0.81):
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
    for score in (0.42, 0.48):
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            payload={
                "prompt_template_name": "assessment_probe.baseline",
                "prompt_template_variant": "baseline",
                "evidence_strength": "emerging",
                "evidence_score": score,
                "profile_update_applied": True,
            },
        )

    assert selector.select_variant(fallback_variant="baseline") == "causal_probe"


def test_socratic_prompt_selector_falls_back_when_data_is_sparse(tmp_path):
    database_path = str(tmp_path / "selector-sparse.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = SocraticPromptSelector(audit_store=audit_store, min_samples_per_variant=2)

    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        payload={
            "prompt_template_name": "assessment_probe.causal_probe",
            "prompt_template_variant": "causal_probe",
            "evidence_strength": "demonstrated",
            "evidence_score": 0.8,
            "profile_update_applied": True,
        },
    )

    assert selector.select_variant(fallback_variant="baseline") == "baseline"
