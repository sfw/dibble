"""Tracks whether remediation sessions actually resolve targeted misconceptions.

After a remediation session completes, subsequent learner observations and
mastery evidence should tell us whether the targeted misconception was
resolved.  This service evaluates recently completed remediation sessions
against post-remediation evidence and records
``misconception.remediation.outcome`` audit events.

This is the ADAPT-003 validation counterpart to the ADAPT-006
ProgressionOutcomeTracker: it tells us whether the misconception pipeline
is actually producing useful remediation rather than just elaborate detours.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dibble.services.protocols import AuditStore, RemediationSessionStore


@dataclass(frozen=True, slots=True)
class MisconceptionRemediationOutcome:
    """A single evaluated remediation session outcome."""

    session_id: str
    student_id: str
    target_kc_id: str
    focus_kc_ids: list[str] = field(default_factory=list)
    misconception_description: str = ""
    outcome: str = "inconclusive"  # resolved, unresolved, inconclusive
    mastery_at_completion: float | None = None
    mastery_at_evaluation: float | None = None
    post_completion_observation_count: int = 0
    post_completion_struggle_count: int = 0
    rationale: str = ""


# How far back to look for recently completed remediation sessions.
_LOOKBACK_DAYS = 21

# Minimum observations after session completion to produce a verdict.
_MIN_OBSERVATIONS = 2

# Mastery thresholds for verdict classification.
_RESOLVED_MASTERY_THRESHOLD = 0.68
_UNRESOLVED_MASTERY_CEILING = 0.50

# Struggle rate threshold: if more than half of post-remediation observations
# show struggle signals, the misconception likely persists.
_STRUGGLE_RATE_THRESHOLD = 0.5


@dataclass(slots=True)
class MisconceptionRemediationOutcomeTracker:
    """Evaluates whether completed remediation sessions resolved their targets."""

    audit_store: AuditStore
    remediation_session_store: RemediationSessionStore

    def evaluate_recent_sessions(
        self,
        *,
        student_id: str,
        current_kc_mastery: dict[str, float],
    ) -> list[MisconceptionRemediationOutcome]:
        """Look back at recently completed remediation sessions and evaluate outcomes.

        Returns only outcomes that have not already been recorded.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=_LOOKBACK_DAYS)

        sessions = self.remediation_session_store.list_recent_for_student(
            student_id=student_id, limit=20
        )

        # Filter to completed sessions within the lookback window.
        completed_sessions = [
            session
            for session in sessions
            if session.current_step_index is None and session.updated_at >= cutoff
        ]

        if not completed_sessions:
            return []

        # Find already-evaluated session ids.
        events = self.audit_store.list(limit=500)
        already_evaluated = {
            event.payload.get("session_id")
            for event in events
            if event.event_type == "misconception.remediation.outcome"
            and str(event.student_id) == student_id
        }

        # Find post-remediation observation events.
        observation_events = [
            event
            for event in events
            if event.event_type == "learner.observe"
            and str(event.student_id) == student_id
        ]

        outcomes: list[MisconceptionRemediationOutcome] = []
        for session in completed_sessions:
            if session.session_id in already_evaluated:
                continue

            completion_time = session.updated_at
            target_kc_ids = set(session.focus_kc_ids or [session.target_kc_id])

            # Find observations after session completion that touch session KCs.
            subsequent = [
                obs
                for obs in observation_events
                if _parse_timestamp(obs.created_at) > completion_time
                and _has_kc_overlap(obs.payload, target_kc_ids)
            ]

            struggle_count = sum(
                1 for obs in subsequent if _is_struggle_observation(obs.payload)
            )

            mastery_at_completion = self._session_completion_mastery(session)
            mastery_at_evaluation = _average_mastery(
                list(target_kc_ids), current_kc_mastery
            )

            outcome = self._evaluate(
                mastery_at_completion=mastery_at_completion,
                mastery_at_evaluation=mastery_at_evaluation,
                observation_count=len(subsequent),
                struggle_count=struggle_count,
            )

            outcomes.append(
                MisconceptionRemediationOutcome(
                    session_id=session.session_id,
                    student_id=student_id,
                    target_kc_id=session.target_kc_id,
                    focus_kc_ids=session.focus_kc_ids,
                    misconception_description=session.misconception_description,
                    outcome=outcome.verdict,
                    mastery_at_completion=mastery_at_completion,
                    mastery_at_evaluation=mastery_at_evaluation,
                    post_completion_observation_count=len(subsequent),
                    post_completion_struggle_count=struggle_count,
                    rationale=outcome.rationale,
                )
            )

        return outcomes

    def record_outcomes(self, outcomes: list[MisconceptionRemediationOutcome]) -> None:
        """Persist evaluated outcomes as audit events."""
        for outcome in outcomes:
            self.audit_store.append(
                event_type="misconception.remediation.outcome",
                status=outcome.outcome,
                student_id=outcome.student_id,
                payload={
                    "session_id": outcome.session_id,
                    "target_kc_id": outcome.target_kc_id,
                    "focus_kc_ids": outcome.focus_kc_ids,
                    "misconception_description": outcome.misconception_description,
                    "outcome": outcome.outcome,
                    "mastery_at_completion": outcome.mastery_at_completion,
                    "mastery_at_evaluation": outcome.mastery_at_evaluation,
                    "post_completion_observation_count": outcome.post_completion_observation_count,
                    "post_completion_struggle_count": outcome.post_completion_struggle_count,
                    "rationale": outcome.rationale,
                },
            )

    def _evaluate(
        self,
        *,
        mastery_at_completion: float | None,
        mastery_at_evaluation: float | None,
        observation_count: int,
        struggle_count: int,
    ) -> _EvalResult:
        if observation_count < _MIN_OBSERVATIONS:
            return _EvalResult(
                verdict="inconclusive",
                rationale=(
                    f"Only {observation_count} observation(s) since remediation "
                    f"completed; need at least {_MIN_OBSERVATIONS}."
                ),
            )

        if mastery_at_evaluation is None:
            return _EvalResult(
                verdict="inconclusive",
                rationale="No current mastery data for remediation target KCs.",
            )

        struggle_rate = struggle_count / observation_count if observation_count else 0.0

        # Strong resolution: high mastery and low struggle rate.
        if (
            mastery_at_evaluation >= _RESOLVED_MASTERY_THRESHOLD
            and struggle_rate < _STRUGGLE_RATE_THRESHOLD
        ):
            improvement_fragment = ""
            if mastery_at_completion is not None:
                delta = mastery_at_evaluation - mastery_at_completion
                if delta > 0.05:
                    improvement_fragment = (
                        f" (improved from {mastery_at_completion:.2f})"
                    )
            return _EvalResult(
                verdict="resolved",
                rationale=(
                    f"Target KC mastery at {mastery_at_evaluation:.2f}"
                    f"{improvement_fragment} with {struggle_count}/{observation_count} "
                    f"post-remediation struggles — misconception appears resolved."
                ),
            )

        # Clear non-resolution: low mastery or high struggle rate.
        if (
            mastery_at_evaluation < _UNRESOLVED_MASTERY_CEILING
            or struggle_rate >= _STRUGGLE_RATE_THRESHOLD
        ):
            struggle_fragment = ""
            if struggle_rate >= _STRUGGLE_RATE_THRESHOLD:
                struggle_fragment = (
                    f" and {struggle_count}/{observation_count} post-remediation "
                    f"observations show continued struggle"
                )
            return _EvalResult(
                verdict="unresolved",
                rationale=(
                    f"Target KC mastery at {mastery_at_evaluation:.2f}"
                    f"{struggle_fragment} — misconception may persist."
                ),
            )

        # Borderline: not enough signal to declare either way.
        return _EvalResult(
            verdict="inconclusive",
            rationale=(
                f"Target KC mastery at {mastery_at_evaluation:.2f} with "
                f"{struggle_count}/{observation_count} struggles; borderline."
            ),
        )

    def _session_completion_mastery(self, session) -> float | None:
        """Extract the mastery at the time the session completed."""
        if session.progression_average_observed_mastery is not None:
            return float(session.progression_average_observed_mastery)
        return None


@dataclass(frozen=True, slots=True)
class _EvalResult:
    verdict: str = "inconclusive"
    rationale: str = ""


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _has_kc_overlap(payload: dict, target_kc_ids: set[str]) -> bool:
    obs_kc_ids = payload.get("target_kc_ids")
    if not isinstance(obs_kc_ids, list) or not target_kc_ids:
        return False
    return any(str(kc) in target_kc_ids for kc in obs_kc_ids)


def _average_mastery(kc_ids: list[str], kc_mastery: dict[str, float]) -> float | None:
    values = [kc_mastery[kc] for kc in kc_ids if kc in kc_mastery]
    if not values:
        return None
    return sum(values) / len(values)


def _is_struggle_observation(payload: dict) -> bool:
    """Classify an observation as a struggle signal.

    Uses the same lightweight heuristic as the misconception behavioral
    evidence pass: high support, multiple errors, or multiple hints.
    """
    score = 0.0
    if str(payload.get("support_level", "")) == "high":
        score += 1.0
    if int(payload.get("error_count", 0)) >= 2:
        score += 1.0
    elif int(payload.get("error_count", 0)) >= 1:
        score += 0.5
    if int(payload.get("hints_used", 0)) >= 2:
        score += 1.0
    elif int(payload.get("hints_used", 0)) >= 1:
        score += 0.5
    if payload.get("completed") is not True:
        score += 1.0
    return score >= 2.0
