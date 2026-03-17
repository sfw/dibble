from uuid import uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationRequest,
    GroundingReference,
    InterventionType,
)
from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.llm_client import LLMClientError
from dibble.services.llm_provider import LLMOrchestrationProvider
from dibble.services.generated_content_store import SQLiteGeneratedContentStore
from dibble.services.predictive_warm_queue_store import SQLitePredictiveWarmQueueStore
from dibble.services.provider_health import SQLiteProviderHealthStore
from dibble.services.telemetry import TelemetryService
from dibble.storage import ensure_database
from tests.support import build_profile


class AlwaysFailsClient:
    def complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        raise LLMClientError("boom")

    def stream_complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        raise LLMClientError("boom")


class SucceedsClient:
    def complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        class Result:
            content = (
                '{"blocks":['
                '{"kind":"summary","title":"Backup","body":"Recovered output."},'
                '{"kind":"instruction","title":"Try it","body":"Use the backup provider."}'
                "]}"
            )

        return Result()

    def stream_complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        yield '{"block_index":0,"kind":"summary","title":"Backup","body_delta":"Recovered output.","done":true}\n'


def test_telemetry_snapshot_includes_provider_health(tmp_path):
    database_path = str(tmp_path / "provider-health.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    generated_content_store = SQLiteGeneratedContentStore(database_path)
    health_store = SQLiteProviderHealthStore(database_path)
    provider = LLMOrchestrationProvider(
        clients=[("primary", AlwaysFailsClient()), ("secondary", SucceedsClient())],
        health_store=health_store,
        circuit_breaker_threshold=1,
        circuit_breaker_cooldown_seconds=30.0,
        fallback_provider=None,
    )
    telemetry = TelemetryService(audit_store, generated_content_store, health_store)
    profile = LearnerProfile.model_validate(build_profile(uuid4()))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent="remediation",
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.step_back,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="high",
        reasons=["test"],
    )

    provider.generate(
        profile,
        request,
        route,
        [
            GroundingReference(
                resource_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                score=1.0,
                matched_terms=["equivalent fractions"],
                excerpt="Use visual fraction models to explain why equivalent fractions name the same amount.",
            )
        ],
    )

    snapshot = telemetry.snapshot()

    assert snapshot.provider_failure_events >= 1
    assert snapshot.provider_circuit_open_events >= 1
    assert snapshot.provider_statuses[0].provider_name == "primary"


def test_telemetry_snapshot_includes_cache_metrics(tmp_path):
    database_path = str(tmp_path / "cache-metrics.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    generated_content_store = SQLiteGeneratedContentStore(database_path)
    queue_store = SQLitePredictiveWarmQueueStore(database_path)
    telemetry = TelemetryService(audit_store, generated_content_store, predictive_warm_queue_store=queue_store)
    deferred_task = queue_store.enqueue(
        request=GenerationRequest(
            student_id=uuid4(),
            learning_session_id="session-telemetry",
            target_kc_ids=["KC-1"],
            intent="practice",
            requested_content_type="practice_problem",
            predictive_warm=True,
            warm_reason="practice follow-up",
            source_generation_id="gen-1",
        )
    )
    claimed = queue_store.claim_pending(limit=1)
    assert deferred_task is not None
    assert claimed
    queue_store.defer_retry(task_id=claimed[0].task_id, error="provider timeout")
    pending_urgent_task = queue_store.enqueue(
        request=GenerationRequest(
            student_id=uuid4(),
            learning_session_id="session-telemetry",
            target_kc_ids=["KC-2"],
            intent="assessment",
            requested_content_type="assessment_probe",
            predictive_warm=True,
            warm_reason="transfer check after bridge",
            source_generation_id="gen-2",
        )
    )
    stale_processing_task = queue_store.enqueue(
        request=GenerationRequest(
            student_id=uuid4(),
            learning_session_id="session-telemetry",
            target_kc_ids=["KC-3"],
            intent="assessment",
            requested_content_type="assessment_probe",
            predictive_warm=True,
            warm_reason="transfer check after bridge",
            source_generation_id="gen-3",
        )
    )
    assert pending_urgent_task is not None
    assert stale_processing_task is not None
    stale_claim = queue_store.claim_tasks(task_ids=[stale_processing_task.task_id])
    assert stale_claim

    from datetime import datetime, timedelta, timezone
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        connection.execute(
            """
            UPDATE predictive_warm_queue
            SET updated_at = ?
            WHERE task_id = ?
            """,
            (stale_time, stale_processing_task.task_id),
        )
        connection.commit()

    audit_store.append(
        event_type="content.moderation",
        status="success",
        payload={
            "stage": "request",
            "blocked": True,
            "request_blocked": True,
            "response_rewritten": False,
            "fallback_applied": True,
            "provider_invoked": False,
            "stream_buffered": False,
            "categories": ["privacy_risk", "academic_integrity"],
            "stream_emitted": True,
        },
    )
    audit_store.append(
        event_type="content.generate",
        status="success",
        payload={
            "cache_hit": True,
            "delivery_mode": "generated",
            "validation_issue_count": 0,
            "prompt_template_name": "micro_explanation.baseline",
        },
    )
    audit_store.append(
        event_type="content.warm",
        status="success",
        payload={"total_requests": 2, "cache_hits": 1, "cache_misses": 1},
    )
    audit_store.append(
        event_type="content.warm.predictive",
        status="success",
        payload={"predicted_request_count": 3, "cache_hits": 2, "cache_misses": 1, "supplemental_tasks": 1},
    )
    audit_store.append(
        event_type="content.cache.invalidate",
        status="success",
        payload={"expired_entries": 2},
    )
    audit_store.append(
        event_type="content.warm.predictive.process",
        status="success",
        payload={
            "attempted_tasks": 1,
            "claimed_tasks": 1,
            "completed_tasks": 1,
            "retried_tasks": 1,
            "requeued_tasks": 1,
            "expired_tasks": 2,
            "dropped_tasks": 0,
        },
    )
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        payload={"progress_signal": "improving"},
    )
    audit_store.append(
        event_type="learning.progress.profile",
        status="success",
        payload={"progress_signal": "declining"},
    )

    snapshot = telemetry.snapshot()

    assert snapshot.cache_hit_generations == 1
    assert snapshot.moderation_events == 1
    assert snapshot.moderation_stream_events == 1
    assert snapshot.moderation_blocked_requests == 1
    assert snapshot.moderation_rewritten_responses == 0
    assert snapshot.moderation_provider_bypass_events == 1
    assert snapshot.moderation_buffered_stream_rewrites == 0
    assert snapshot.moderation_category_counts[0].category == "academic_integrity"
    assert snapshot.moderation_category_counts[0].event_count == 1
    assert snapshot.warm_requests == 5
    assert snapshot.predictive_warm_events == 1
    assert snapshot.predictive_warm_requests == 3
    assert snapshot.predictive_warm_process_events == 1
    assert snapshot.predictive_cache_invalidations == 2
    assert snapshot.expired_predictive_warm_tasks == 2
    assert snapshot.supplemental_inline_predictive_warm_tasks == 1
    assert snapshot.learning_progress_profile_events == 2
    assert snapshot.improving_progress_signals == 1
    assert snapshot.declining_progress_signals == 1
    assert snapshot.pending_predictive_warm_tasks == 1
    assert snapshot.deferred_predictive_warm_tasks == 1
    assert snapshot.aged_routine_predictive_warm_tasks == 0
    assert snapshot.eligible_predictive_warm_tasks == 1
    assert snapshot.blocked_predictive_warm_tasks == 1
    assert snapshot.stale_processing_predictive_warm_tasks == 1
    assert snapshot.urgent_predictive_warm_tasks == 2
    assert snapshot.next_predictive_warm_task_eta_seconds is not None
    assert snapshot.next_predictive_warm_task_eta_seconds == 0
    assert snapshot.retried_predictive_warm_tasks == 1
    assert snapshot.requeued_predictive_warm_tasks == 1
    assert snapshot.dropped_predictive_warm_tasks == 0
    assert snapshot.generated_content_entries == 0
    assert snapshot.prompt_template_usages[0].template_name == "micro_explanation.baseline"
    assert snapshot.prompt_template_usages[0].event_count == 1


def test_telemetry_snapshot_includes_generation_prompt_outcomes(tmp_path):
    database_path = str(tmp_path / "generation-prompt-telemetry.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    telemetry = TelemetryService(audit_store)
    student_id = str(uuid4())

    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-1",
            "content_type": "worked_example",
            "quality_score": 0.78,
            "validation_passed": True,
            "grounding_count": 1,
            "prompt_template_name": "worked_example.guided_reflection",
            "prompt_template_variant": "guided_reflection",
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-1",
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.25,
            "confidence_calibration": 0.82,
            "help_seeking": "low",
        },
    )
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-1",
            "evidence_strength": "demonstrated",
            "evidence_score": 0.81,
            "profile_update_applied": True,
        },
    )

    snapshot = telemetry.snapshot()

    assert len(snapshot.generation_prompt_performances) == 1
    performance = snapshot.generation_prompt_performances[0]
    assert performance.template_name == "worked_example.guided_reflection"
    assert performance.content_type == "worked_example"
    assert performance.average_composite_outcome > performance.average_quality_score
    assert performance.average_run_outcome_score > performance.average_quality_score
    assert performance.average_run_signal_confidence >= 0.7
    assert performance.run_summary_rate == 1.0
    assert performance.positive_run_signal_rate == 1.0
    assert performance.downstream_observation_rate == 1.0
    assert performance.downstream_assessment_rate == 1.0
    assert performance.session_outcome_rate == 0.0
    assert performance.average_observation_trace_count == 1.0
    assert performance.average_assessment_trace_count == 1.0
    assert performance.average_session_generation_depth == 0.0


def test_telemetry_snapshot_includes_cross_generation_session_outcomes(tmp_path):
    database_path = str(tmp_path / "generation-session-telemetry.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    telemetry = TelemetryService(audit_store)
    student_id = str(uuid4())

    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-2",
            "content_type": "micro_explanation",
            "quality_score": 0.72,
            "validation_passed": True,
            "grounding_count": 1,
            "prompt_template_name": "micro_explanation.guided_reflection",
            "prompt_template_variant": "guided_reflection",
        },
    )
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-2",
            "content_type": "practice_problem",
            "quality_score": 0.78,
            "validation_passed": True,
            "grounding_count": 1,
            "prompt_template_name": "practice_problem.guided_reflection",
            "prompt_template_variant": "guided_reflection",
        },
    )
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        student_id=student_id,
        payload={
            "learning_session_id": "learn-session-2",
            "evidence_strength": "demonstrated",
            "evidence_score": 0.83,
            "profile_update_applied": True,
        },
    )

    snapshot = telemetry.snapshot()

    performance = next(
        item
        for item in snapshot.generation_prompt_performances
        if item.template_name == "micro_explanation.guided_reflection"
    )
    assert performance.session_outcome_rate == 1.0
    assert performance.run_summary_rate == 1.0
    assert performance.positive_run_signal_rate == 1.0
    assert performance.average_session_generation_depth == 1.0


def test_telemetry_snapshot_reports_persisted_run_summary_coverage(tmp_path):
    database_path = str(tmp_path / "generation-persisted-summary-telemetry.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    telemetry = TelemetryService(audit_store)
    student_id = str(uuid4())

    generation_event = audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=student_id,
        payload={
            "generation_id": "gen-telemetry-persisted",
            "learning_session_id": "learn-session-persisted",
            "content_type": "worked_example",
            "quality_score": 0.76,
            "validation_passed": True,
            "grounding_count": 1,
            "prompt_template_name": "worked_example.guided_reflection",
            "prompt_template_variant": "guided_reflection",
        },
    )
    audit_store.append(
        event_type="learning.run.summary",
        status="success",
        student_id=student_id,
        payload={
            "source_generation_event_id": generation_event.event_id,
            "generation_id": "gen-telemetry-persisted",
            "run_summary_score": 0.84,
            "run_calibration_signal": "positive",
            "run_calibration_confidence": 0.8,
            "run_direct_source_count": 2,
            "run_event_count": 4,
        },
    )

    snapshot = telemetry.snapshot()

    performance = snapshot.generation_prompt_performances[0]
    assert performance.run_summary_rate == 1.0
    assert performance.persisted_run_summary_rate == 1.0
    assert performance.average_run_outcome_score == 0.84


def test_telemetry_snapshot_includes_socratic_assessment_metrics(tmp_path):
    database_path = str(tmp_path / "socratic-telemetry.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    telemetry = TelemetryService(audit_store)

    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        payload={
            "evidence_strength": "demonstrated",
            "evidence_score": 0.78,
            "next_action": "advance",
            "profile_update_applied": True,
            "prompt_style": "transfer_check",
            "prompt_template_name": "assessment_probe.causal_probe",
            "prompt_template_variant": "causal_probe",
        },
    )
    audit_store.append(
        event_type="assessment.socratic",
        status="success",
        payload={
            "evidence_strength": "insufficient",
            "evidence_score": 0.24,
            "next_action": "step_back",
            "profile_update_applied": False,
            "prompt_style": "scaffolded_step_back",
            "prompt_template_name": "assessment_probe.baseline",
            "prompt_template_variant": "baseline",
        },
    )

    snapshot = telemetry.snapshot()

    assert snapshot.socratic_assessment_events == 2
    assert snapshot.socratic_profile_updates == 1
    assert snapshot.socratic_demonstrated_events == 1
    assert snapshot.socratic_step_back_events == 1
    assert snapshot.average_socratic_evidence_score == 0.51
    assert len(snapshot.socratic_prompt_performances) == 2
    assert snapshot.socratic_prompt_performances[0].template_name.startswith("assessment_probe.")
    assert snapshot.socratic_prompt_performances[0].event_count == 1
