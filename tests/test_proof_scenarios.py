from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from scripts.rehearse_proof_scenarios import (
    RehearsalError,
    assert_reuse_hit,
    content_quality_sample,
    operator_markdown_report,
    require_real_provider,
    run_longitudinal_fraction_recovery,
)
from scripts.live_household_proof import file_evidence, household_signature
from scripts.validate_proof_scenarios import (
    load_scenarios,
    load_timelines,
    validate_all,
    validate_timeline_assets,
)


SCENARIO_DIR = Path(__file__).resolve().parents[1] / "proof" / "scenarios"
TIMELINE_DIR = Path(__file__).resolve().parents[1] / "proof" / "timelines"
CANONICAL_SCENARIO_IDS = {
    "new_household_onboarding",
    "adaptive_modality_change",
    "parent_governed_autonomy",
    "cross_session_planning_revision",
    "shared_library_reuse_without_privacy_leakage",
}


def test_canonical_proof_scenarios_are_present() -> None:
    scenario_ids = {
        scenario["scenario_id"] for scenario in load_scenarios(SCENARIO_DIR)
    }

    assert scenario_ids == CANONICAL_SCENARIO_IDS


def test_proof_scenarios_validate_privacy_and_rehearsal_shape() -> None:
    assert validate_all(SCENARIO_DIR) == []


def test_longitudinal_proof_timelines_are_present() -> None:
    timeline_ids = {
        timeline["timeline_id"] for timeline in load_timelines(TIMELINE_DIR)
    }

    assert timeline_ids == {"longitudinal_fraction_recovery"}


def test_longitudinal_proof_timelines_validate_privacy_and_review_shape() -> None:
    assert validate_timeline_assets(TIMELINE_DIR) == []


def test_longitudinal_day_3_reuse_claim_has_runner_assertion() -> None:
    timeline = load_timelines(TIMELINE_DIR)[0]
    day_3 = next(
        phase
        for phase in timeline["phases"]
        if phase["phase_id"] == "session-3-recovery"
    )
    source = inspect.getsource(run_longitudinal_fraction_recovery)

    assert "cache_hit=true" in " ".join(day_3["system_expectations"])
    assert "assert_reuse_hit(peer_reusable" in source


def test_reuse_hit_assertion_requires_cache_hit_signal() -> None:
    assert_reuse_hit({"quality": {"cache_hit": True}}, learner_alias="blair")

    with pytest.raises(RehearsalError, match="cache/library hit"):
        assert_reuse_hit({"quality": {"cache_hit": False}}, learner_alias="blair")


def test_real_provider_requirement_rejects_mock_fallback() -> None:
    readiness = {
        "mock_fallback_enabled": True,
        "checks": [
            {
                "key": "llm_provider",
                "status": "pass",
                "summary": "Primary LLM provider credentials are configured.",
            }
        ],
    }

    with pytest.raises(RehearsalError, match="MOCK_FALLBACK=false"):
        require_real_provider(readiness)


def test_operator_markdown_report_summarizes_live_evidence() -> None:
    report = {
        "generated_at": "2026-05-04T00:00:00+00:00",
        "base_url": "http://localhost:8000",
        "household_id": "household-1",
        "run_stamp": "abc123",
        "initial_readiness": {
            "status": "ready",
            "deployment_mode": "household_container",
            "llm_provider_status": "pass",
            "llm_provider_summary": "Primary LLM provider credentials are configured.",
            "mock_fallback_enabled": False,
            "cloud_library_enabled": False,
        },
        "scenarios": [
            {
                "scenario_id": "new_household_onboarding",
                "result": "overview shows 2 learners",
            }
        ],
        "multi_household_evidence": [
            {
                "label": "operator_household_1",
                "household_name": "Operator Review Household",
                "learner_count": 4,
                "readiness": {"status": "ready"},
                "privacy_audit": {"entry_count": 2, "forbidden_hit_count": 0},
                "scenario_results": [
                    {
                        "scenario_id": "adaptive_modality_change",
                        "result": "text -> diagram",
                    }
                ],
            }
        ],
        "timelines": [
            {
                "timeline_id": "longitudinal_fraction_recovery",
                "title": "Longitudinal fraction recovery household rehearsal",
                "phases": [
                    {
                        "phase_id": "day-0-baseline",
                        "review_checkpoint": {
                            "ready_status": "ready",
                            "pending_approval_count": 1,
                            "planning_revision_count": 0,
                            "recent_signal_count": 0,
                        },
                        "proof_signal": "Governance was visible.",
                    }
                ],
                "content_quality_samples": [
                    {
                        "phase_id": "session-3-recovery",
                        "learner_alias": "blair",
                        "generation_id": "gen-1",
                        "modality": "diagram",
                        "cache_hit": True,
                        "review_checklist": {
                            "curriculum_fit": "Does it teach the target?"
                        },
                    }
                ],
                "privacy_audit": {"entry_count": 1, "forbidden_field_hits": []},
            }
        ],
        "live_container_evidence": {
            "restart": {
                "persistence_preserved": True,
                "pre_restart_signature": {
                    "canonical": {"household_id": "household-1"},
                    "operator_household_1": {"household_id": "household-2"},
                },
            },
            "backup": {"path": "backup.db", "size_bytes": 4096, "sha256": "abc"},
            "restore": {
                "restore_preserved_state": True,
                "post_restore_ready_status": "ready",
            },
        },
    }

    markdown = operator_markdown_report(report)

    assert "Live Household Proof Report" in markdown
    assert "How To Read This Report" in markdown
    assert "Multi-Household Evidence" in markdown
    assert "operator_household_1" in markdown
    assert "curriculum_fit" in markdown
    assert "Restart preserved household state: True" in markdown
    assert "Privacy audit: entries=1, forbidden_hits=0" in markdown


def test_content_quality_sample_includes_review_checklist() -> None:
    sample = content_quality_sample(
        phase_id="session-1",
        learner_alias="avery",
        generation={
            "generation_id": "gen-1",
            "content_type": "worked_example",
            "quality": {"cache_hit": False},
            "workflow_summary": {"learning_session_id": "session-1"},
            "request_context": {"modality_plugin_id": "diagram"},
        },
        review_note="Review this sample.",
    )

    assert sample["modality"] == "diagram"
    assert set(sample["review_checklist"]) == {
        "curriculum_fit",
        "misconception_targeting",
        "age_fit",
        "privacy",
        "actionability",
    }


def test_live_proof_helpers_capture_stable_evidence(tmp_path: Path) -> None:
    db = tmp_path / "dibble.db"
    db.write_bytes(b"household-proof")
    overview = {
        "household": {"household_id": "hh-1", "display_name": "Pilot"},
        "learners": [{"learner_id": "b"}, {"learner_id": "a"}],
        "pending_approvals": [{"approval_id": "approval-1"}],
        "session_suggestions": [{}, {}],
    }

    signature = household_signature(overview)
    evidence = file_evidence(db)

    assert signature["learner_ids"] == ["a", "b"]
    assert signature["pending_approval_count"] == 1
    assert evidence["size_bytes"] == len(b"household-proof")
    assert len(evidence["sha256"]) == 64
