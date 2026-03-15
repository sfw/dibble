from dibble.services.generation_run_summaries import GenerationRunSummaryBuilder
from dibble.services.generation_trace_linker import LinkedTraceEvent
from dibble.services.learning_session_outcomes import LearningSessionOutcome
from dibble.models.telemetry import AuditEvent


def _observation_event(*, engagement: str, frustration: str, load: float, confidence: float, help_seeking: str) -> AuditEvent:
    return AuditEvent(
        event_id="observation",
        event_type="learner.observe",
        status="success",
        payload={
            "engagement": engagement,
            "frustration": frustration,
            "total_load": load,
            "confidence_calibration": confidence,
            "help_seeking": help_seeking,
        },
    )


def _assessment_event(*, strength: str, evidence_score: float, profile_update_applied: bool) -> AuditEvent:
    return AuditEvent(
        event_id="assessment",
        event_type="assessment.socratic",
        status="success",
        payload={
            "evidence_strength": strength,
            "evidence_score": evidence_score,
            "profile_update_applied": profile_update_applied,
        },
    )


def test_generation_run_summary_builder_emits_positive_signal_for_strong_multi_source_run():
    builder = GenerationRunSummaryBuilder()

    summary = builder.build(
        linked_observations=[
            LinkedTraceEvent(
                event=_observation_event(
                    engagement="high",
                    frustration="low",
                    load=0.2,
                    confidence=0.84,
                    help_seeking="low",
                ),
                match_score=5.5,
                link_tier=3,
            ),
        ],
        linked_assessments=[
            LinkedTraceEvent(
                event=_assessment_event(
                    strength="demonstrated",
                    evidence_score=0.86,
                    profile_update_applied=True,
                ),
                match_score=4.2,
                link_tier=2,
            ),
        ],
        session_outcome=LearningSessionOutcome(
            session_outcome_score=0.83,
            subsequent_generation_count=1,
            outcome_event_count=2,
            outcome_event_ids=("session-observation", "session-assessment"),
        ),
    )

    assert summary.run_outcome_score is not None
    assert summary.run_outcome_score > 0.8
    assert summary.calibration_signal == "positive"
    assert summary.calibration_confidence >= 0.75
    assert summary.direct_source_count == 2
    assert summary.event_count == 4


def test_generation_run_summary_builder_marks_weak_low_confidence_runs_as_tentative():
    builder = GenerationRunSummaryBuilder()

    summary = builder.build(
        linked_observations=[
            LinkedTraceEvent(
                event=_observation_event(
                    engagement="medium",
                    frustration="medium",
                    load=0.55,
                    confidence=0.58,
                    help_seeking="medium",
                ),
                match_score=0.9,
                link_tier=0,
            ),
        ],
        linked_assessments=[],
        session_outcome=LearningSessionOutcome(),
    )

    assert summary.run_outcome_score is not None
    assert summary.calibration_signal == "tentative"
    assert summary.calibration_confidence < 0.35
    assert summary.event_count == 1


def test_generation_run_summary_builder_emits_negative_signal_for_consistently_poor_run():
    builder = GenerationRunSummaryBuilder()

    summary = builder.build(
        linked_observations=[
            LinkedTraceEvent(
                event=_observation_event(
                    engagement="low",
                    frustration="high",
                    load=0.88,
                    confidence=0.24,
                    help_seeking="high",
                ),
                match_score=5.0,
                link_tier=3,
            ),
        ],
        linked_assessments=[
            LinkedTraceEvent(
                event=_assessment_event(
                    strength="insufficient",
                    evidence_score=0.22,
                    profile_update_applied=False,
                ),
                match_score=4.0,
                link_tier=2,
            ),
        ],
        session_outcome=LearningSessionOutcome(
            session_outcome_score=0.3,
            subsequent_generation_count=1,
            outcome_event_count=1,
            outcome_event_ids=("session-assessment",),
        ),
    )

    assert summary.run_outcome_score is not None
    assert summary.run_outcome_score < 0.4
    assert summary.calibration_signal == "negative"
    assert summary.calibration_confidence >= 0.7
