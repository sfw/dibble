"""Tests for the MisconceptionRemediationOutcomeTracker.

These tests verify that completed remediation sessions are correctly evaluated
against subsequent learner evidence to determine whether the targeted
misconception was resolved, unresolved, or inconclusive.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from dibble.models.remediation import (
    RemediationWorkflowSession,
    RemediationWorkflowStep,
    RemediationWorkflowSummary,
)
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.misconception_remediation_outcomes import (
    MisconceptionRemediationOutcomeTracker,
)
from dibble.services.remediation_session_store import SQLiteRemediationSessionStore
from dibble.storage import ensure_database


def _stores(tmp_path):
    db = str(tmp_path / "test.db")
    ensure_database(db)
    return SQLiteAuditStore(db), SQLiteRemediationSessionStore(db)


def _completed_session(
    store: SQLiteRemediationSessionStore,
    *,
    student_id: UUID,
    session_id: str | None = None,
    target_kc_id: str = "KC-1",
    focus_kc_ids: list[str] | None = None,
    misconception_description: str = "Confuses addition with multiplication",
    avg_mastery: float | None = None,
) -> RemediationWorkflowSession:
    """Create and persist a completed remediation session."""
    sid = session_id or str(uuid4())
    session = RemediationWorkflowSession(
        session_id=sid,
        student_id=student_id,
        target_kc_id=target_kc_id,
        focus_kc_ids=focus_kc_ids or [target_kc_id],
        misconception_description=misconception_description,
        rationale="Test remediation",
        steps=[
            RemediationWorkflowStep(
                phase="repair",
                title="Repair step",
                target_kc_ids=[target_kc_id],
                support_level="high",
                objective="Fix misconception",
                guidance="Practice carefully",
                recommended_content_type="practice_problem",
                status="completed",
                generated_content_id=str(uuid4()),
            ),
        ],
        current_step_index=None,  # completed
        progression_average_observed_mastery=avg_mastery,
        summary=RemediationWorkflowSummary(status="complete"),
    )
    return store.upsert(session)


def _observation_event(
    audit_store: SQLiteAuditStore,
    *,
    student_id: str,
    target_kc_ids: list[str],
    support_level: str = "low",
    error_count: int = 0,
    hints_used: int = 0,
    completed: bool = True,
):
    return audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=student_id,
        payload={
            "target_kc_ids": target_kc_ids,
            "support_level": support_level,
            "error_count": error_count,
            "hints_used": hints_used,
            "completed": completed,
        },
    )


def test_resolved_when_mastery_high_and_no_struggles(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student, avg_mastery=0.45)
    # 2 successful post-remediation observations
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.75},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "resolved"
    assert "resolved" in outcomes[0].rationale
    assert outcomes[0].mastery_at_evaluation == 0.75


def test_unresolved_when_mastery_low(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student, avg_mastery=0.3)
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.35},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "unresolved"
    assert "persist" in outcomes[0].rationale


def test_unresolved_when_struggle_rate_high(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student)
    # Both observations show struggle (high support + errors)
    _observation_event(
        audit_store,
        student_id=str(student),
        target_kc_ids=["KC-1"],
        support_level="high",
        error_count=2,
    )
    _observation_event(
        audit_store,
        student_id=str(student),
        target_kc_ids=["KC-1"],
        support_level="high",
        hints_used=2,
    )

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.60},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "unresolved"
    assert outcomes[0].post_completion_struggle_count == 2


def test_inconclusive_when_insufficient_observations(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student)
    # Only 1 observation (below minimum of 2)
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.9},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "inconclusive"


def test_idempotency_does_not_reevaluate(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student)
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])

    # First evaluation
    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.75},
    )
    assert len(outcomes) == 1
    tracker.record_outcomes(outcomes)

    # Second evaluation should return nothing
    outcomes_again = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.8},
    )
    assert len(outcomes_again) == 0


def test_record_outcomes_persists_audit_events(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student)
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.75},
    )
    tracker.record_outcomes(outcomes)

    all_events = audit_store.list(limit=100)
    outcome_events = [
        e for e in all_events if e.event_type == "misconception.remediation.outcome"
    ]
    assert len(outcome_events) == 1
    assert outcome_events[0].payload["outcome"] == "resolved"
    assert outcome_events[0].payload["target_kc_id"] == "KC-1"


def test_ignores_in_progress_sessions(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    # Create an in-progress session (current_step_index is not None)
    session = RemediationWorkflowSession(
        session_id=str(uuid4()),
        student_id=student,
        target_kc_id="KC-1",
        focus_kc_ids=["KC-1"],
        misconception_description="Test",
        rationale="Test",
        steps=[
            RemediationWorkflowStep(
                phase="repair",
                title="Repair",
                target_kc_ids=["KC-1"],
                support_level="high",
                objective="Fix",
                guidance="Practice",
                recommended_content_type="practice_problem",
                status="active",
            ),
        ],
        current_step_index=0,  # still in progress
    )
    session_store.upsert(session)

    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.9},
    )

    assert len(outcomes) == 0


def test_ignores_observations_for_different_kcs(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student, target_kc_id="KC-1")
    # Observations for a different KC
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-other"])
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-other"])

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.9},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "inconclusive"
    assert outcomes[0].post_completion_observation_count == 0


def test_resolved_shows_improvement_from_completion(tmp_path):
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(session_store, student_id=student, avg_mastery=0.35)
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.78},
    )

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "resolved"
    assert "improved from 0.35" in outcomes[0].rationale


def test_focus_kc_ids_used_for_matching(tmp_path):
    """When focus_kc_ids includes multiple KCs, observations on any
    of them should count."""
    audit_store, session_store = _stores(tmp_path)
    student = uuid4()
    tracker = MisconceptionRemediationOutcomeTracker(
        audit_store=audit_store, remediation_session_store=session_store
    )

    _completed_session(
        session_store,
        student_id=student,
        target_kc_id="KC-1",
        focus_kc_ids=["KC-1", "KC-prereq"],
    )
    # One observation on each focus KC
    _observation_event(audit_store, student_id=str(student), target_kc_ids=["KC-1"])
    _observation_event(
        audit_store, student_id=str(student), target_kc_ids=["KC-prereq"]
    )

    outcomes = tracker.evaluate_recent_sessions(
        student_id=str(student),
        current_kc_mastery={"KC-1": 0.72, "KC-prereq": 0.70},
    )

    assert len(outcomes) == 1
    assert outcomes[0].post_completion_observation_count == 2
    assert outcomes[0].outcome == "resolved"
