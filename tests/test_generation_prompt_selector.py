from __future__ import annotations

from dibble.models.generation import GenerationModeCalibration, RequestedContentType
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_prompt_selector import GenerationPromptSelector
from dibble.storage import ensure_database


def test_generation_prompt_selector_prefers_higher_quality_variant(tmp_path):
    database_path = str(tmp_path / "generation-selector.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

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
        selector.select_variant(
            content_type=RequestedContentType.worked_example,
            fallback_variant="baseline",
        )
        == "guided_reflection"
    )


def test_generation_prompt_selector_falls_back_when_samples_are_sparse(tmp_path):
    database_path = str(tmp_path / "generation-selector-sparse.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

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
        selector.select_variant(
            content_type=RequestedContentType.micro_explanation,
            fallback_variant="baseline",
        )
        == "baseline"
    )


def test_generation_prompt_selector_can_prefer_better_downstream_outcome(tmp_path):
    database_path = str(tmp_path / "generation-selector-outcomes.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )
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

    for student_id in (
        "00000000-0000-0000-0000-000000000201",
        "00000000-0000-0000-0000-000000000202",
    ):
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
        selector.select_variant(
            content_type=RequestedContentType.practice_problem,
            fallback_variant="baseline",
        )
        == "guided_reflection"
    )


def test_generation_prompt_selector_can_prefer_variant_with_stronger_same_session_assessment(
    tmp_path,
):
    database_path = str(tmp_path / "generation-selector-assessment.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000030{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"learn-session-guided-{suffix}",
                "content_type": "micro_explanation",
                "prompt_template_name": "micro_explanation.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": 0.74,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"learn-session-guided-{suffix}",
                "target_kc_ids": ["KC-1"],
                "evidence_strength": "demonstrated",
                "evidence_score": 0.84,
                "profile_update_applied": True,
            },
        )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000040{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"learn-session-baseline-{suffix}",
                "content_type": "micro_explanation",
                "prompt_template_name": "micro_explanation.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": 0.82,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"learn-session-baseline-{suffix}",
                "target_kc_ids": ["KC-1"],
                "evidence_strength": "insufficient",
                "evidence_score": 0.28,
                "profile_update_applied": False,
            },
        )

    assert (
        selector.select_variant(
            content_type=RequestedContentType.micro_explanation,
            fallback_variant="baseline",
        )
        == "guided_reflection"
    )


def test_generation_prompt_selector_can_prefer_deeper_session_trace(tmp_path):
    database_path = str(tmp_path / "generation-selector-trace-depth.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000050{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"trace-guided-{suffix}",
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": 0.78,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        for evidence_score in (0.8, 0.8):
            audit_store.append(
                event_type="assessment.socratic",
                status="success",
                student_id=student_id,
                payload={
                    "learning_session_id": f"trace-guided-{suffix}",
                    "target_kc_ids": ["KC-1"],
                    "evidence_strength": "demonstrated",
                    "evidence_score": evidence_score,
                    "profile_update_applied": True,
                },
            )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000060{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"trace-baseline-{suffix}",
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": 0.78,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"trace-baseline-{suffix}",
                "target_kc_ids": ["KC-1"],
                "evidence_strength": "demonstrated",
                "evidence_score": 0.8,
                "profile_update_applied": True,
            },
        )

    assert (
        selector.select_variant(
            content_type=RequestedContentType.worked_example,
            fallback_variant="baseline",
        )
        == "guided_reflection"
    )


def test_generation_prompt_selector_uses_session_arc_to_break_support_loop(tmp_path):
    database_path = str(tmp_path / "generation-selector-session-arc.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

    assert (
        selector.select_variant(
            content_type=RequestedContentType.practice_problem,
            fallback_variant="guided_reflection",
            mode_calibration=GenerationModeCalibration(
                session_source="session_controller",
                session_confidence=0.78,
                session_assessment_count=2,
                session_stuck_loop_risk="high",
                session_arc_action="reprobe_new_angle",
                socratic_steering_action="clarify_then_check",
            ),
        )
        == "baseline"
    )


def test_generation_prompt_selector_steers_guided_reflection_for_reliable_overload_signals(
    tmp_path,
):
    database_path = str(tmp_path / "generation-selector-state-steer.db")
    ensure_database(database_path)
    selector = GenerationPromptSelector(
        audit_store=SQLiteAuditStore(database_path), min_samples_per_variant=2
    )

    variant = selector.select_variant(
        content_type=RequestedContentType.practice_problem,
        fallback_variant="baseline",
        mode_calibration=GenerationModeCalibration(
            state_profile_signal="support_needed",
            state_profile_source="state_profile",
            state_profile_load_reliability=0.82,
            state_profile_overload_risk=0.84,
        ),
    )

    assert variant == "guided_reflection"


def test_generation_prompt_selector_steers_baseline_for_stable_trait_release(tmp_path):
    database_path = str(tmp_path / "generation-selector-trait-steer.db")
    ensure_database(database_path)
    selector = GenerationPromptSelector(
        audit_store=SQLiteAuditStore(database_path), min_samples_per_variant=2
    )

    variant = selector.select_variant(
        content_type=RequestedContentType.worked_example,
        fallback_variant="guided_reflection",
        mode_calibration=GenerationModeCalibration(
            trait_profile_signal="stable",
            trait_profile_source="trait_profile",
            trait_profile_trait_stability=0.8,
            trait_profile_challenge_tolerance=0.72,
            trait_profile_challenge_evidence_strength=0.76,
        ),
    )

    assert variant == "baseline"


def test_generation_prompt_selector_prefers_variant_with_stronger_persisted_run_summaries(
    tmp_path,
):
    database_path = str(tmp_path / "generation-selector-persisted-summary.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

    for suffix, quality_score, run_score, signal in (
        ("1", 0.72, 0.86, "positive"),
        ("2", 0.74, 0.84, "positive"),
    ):
        student_id = f"00000000-0000-0000-0000-00000000070{suffix}"
        generation_event = audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"guided-{suffix}",
                "learning_session_id": f"persisted-guided-{suffix}",
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": quality_score,
                "validation_passed": True,
                "grounding_count": 1,
            },
        )
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "source_generation_event_id": generation_event.event_id,
                "generation_id": f"guided-{suffix}",
                "run_summary_score": run_score,
                "run_calibration_signal": signal,
                "run_calibration_confidence": 0.82,
                "run_direct_source_count": 2,
                "run_event_count": 4,
            },
        )

    for suffix, quality_score, run_score, signal in (
        ("1", 0.88, 0.42, "negative"),
        ("2", 0.87, 0.4, "negative"),
    ):
        student_id = f"00000000-0000-0000-0000-00000000080{suffix}"
        generation_event = audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"baseline-{suffix}",
                "learning_session_id": f"persisted-baseline-{suffix}",
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": quality_score,
                "validation_passed": True,
                "grounding_count": 1,
            },
        )
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=student_id,
            payload={
                "source_generation_event_id": generation_event.event_id,
                "generation_id": f"baseline-{suffix}",
                "run_summary_score": run_score,
                "run_calibration_signal": signal,
                "run_calibration_confidence": 0.81,
                "run_direct_source_count": 2,
                "run_event_count": 4,
            },
        )

    assert (
        selector.select_variant(
            content_type=RequestedContentType.worked_example,
            fallback_variant="baseline",
        )
        == "guided_reflection"
    )


def test_generation_prompt_selector_can_prefer_better_cross_generation_session_outcome(
    tmp_path,
):
    database_path = str(tmp_path / "generation-selector-session-run.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000070{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"guided-start-{suffix}",
                "learning_session_id": f"guided-run-{suffix}",
                "content_type": "micro_explanation",
                "prompt_template_name": "micro_explanation.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": 0.72,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"guided-next-{suffix}",
                "learning_session_id": f"guided-run-{suffix}",
                "content_type": "practice_problem",
                "prompt_template_name": "practice_problem.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": 0.78,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"guided-run-{suffix}",
                "target_kc_ids": ["KC-1"],
                "evidence_strength": "demonstrated",
                "evidence_score": 0.84,
                "profile_update_applied": True,
            },
        )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000080{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"baseline-start-{suffix}",
                "learning_session_id": f"baseline-run-{suffix}",
                "content_type": "micro_explanation",
                "prompt_template_name": "micro_explanation.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": 0.8,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"baseline-next-{suffix}",
                "learning_session_id": f"baseline-run-{suffix}",
                "content_type": "practice_problem",
                "prompt_template_name": "practice_problem.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": 0.79,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"baseline-run-{suffix}",
                "target_kc_ids": ["KC-1"],
                "evidence_strength": "insufficient",
                "evidence_score": 0.24,
                "profile_update_applied": False,
            },
        )

    assert (
        selector.select_variant(
            content_type=RequestedContentType.micro_explanation,
            fallback_variant="baseline",
        )
        == "guided_reflection"
    )


def test_generation_prompt_selector_can_use_durable_socratic_profile_signal(tmp_path):
    database_path = str(tmp_path / "generation-selector-durable-socratic.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(audit_store=audit_store)

    variant = selector.select_variant(
        content_type=RequestedContentType.practice_problem,
        fallback_variant="baseline",
        mode_calibration=GenerationModeCalibration(
            socratic_profile_source="socratic_assessment_history",
            socratic_profile_confidence=0.72,
            socratic_profile_signal="model_then_release",
        ),
    )

    assert variant == "guided_reflection"


def test_generation_prompt_selector_can_prefer_stronger_positive_run_signal(tmp_path):
    database_path = str(tmp_path / "generation-selector-run-signal.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    selector = GenerationPromptSelector(
        audit_store=audit_store, min_samples_per_variant=2
    )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000090{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"guided-{suffix}",
                "learning_session_id": f"guided-signal-{suffix}",
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.guided_reflection",
                "prompt_template_variant": "guided_reflection",
                "quality_score": 0.78,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=student_id,
            payload={
                "generation_id": f"guided-{suffix}",
                "learning_session_id": f"guided-signal-{suffix}",
                "observed_content_type": "worked_example",
                "task_type": "worked_example",
                "target_kc_ids": ["KC-1"],
                "engagement": "high",
                "frustration": "low",
                "total_load": 0.22,
                "confidence_calibration": 0.84,
                "help_seeking": "low",
            },
        )
        audit_store.append(
            event_type="assessment.socratic",
            status="success",
            student_id=student_id,
            payload={
                "learning_session_id": f"guided-signal-{suffix}",
                "target_kc_ids": ["KC-1"],
                "evidence_strength": "demonstrated",
                "evidence_score": 0.86,
                "profile_update_applied": True,
            },
        )

    for suffix in ("1", "2"):
        student_id = f"00000000-0000-0000-0000-00000000100{suffix}"
        audit_store.append(
            event_type="content.generate",
            status="success",
            student_id=student_id,
            payload={
                "content_type": "worked_example",
                "prompt_template_name": "worked_example.baseline",
                "prompt_template_variant": "baseline",
                "quality_score": 0.82,
                "validation_passed": True,
                "grounding_count": 1,
                "target_kc_ids": ["KC-1"],
            },
        )
        audit_store.append(
            event_type="learner.observe",
            status="success",
            student_id=student_id,
            payload={
                "engagement": "medium",
                "frustration": "medium",
                "total_load": 0.55,
                "confidence_calibration": 0.58,
                "help_seeking": "medium",
            },
        )

    assert (
        selector.select_variant(
            content_type=RequestedContentType.worked_example,
            fallback_variant="baseline",
        )
        == "guided_reflection"
    )
