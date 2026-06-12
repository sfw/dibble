"""Session bookends and in-context defect reports for the learner loop.

Explicit session start (with a per-session goal derived from the progression
read model) and session end (with a recap derived from the session's
observations) give unsupervised homeschool use a daily rhythm, and emit the
``learning.session.*`` audit events the pilot metrics aggregate. The defect
report writes ``content.defect.report`` events — the fastest
verification-gap detector during the pilot. (POC roadmap 2.3)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from dibble.models.session_bookends import (
    DefectReportResponse,
    SessionRecap,
    SessionStartResponse,
)
from dibble.services.pilot_metrics import (
    DEFECT_REPORT_EVENT_TYPE,
    SESSION_COMPLETED_EVENT_TYPE,
    SESSION_STARTED_EVENT_TYPE,
)
from dibble.services.protocols import AuditStore, ObservationStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionBookendService:
    audit_store: AuditStore
    learner_progression_service: object  # LearnerProgressionService
    observation_store: ObservationStore | None = None

    def start_session(self, *, student_id: UUID) -> SessionStartResponse:
        focus_title = self._focus_outcome_title(student_id)
        if focus_title:
            goal_display = f"Today: 3 practice rounds on {focus_title}."
        else:
            goal_display = "Today: complete your first activity so Dibble can learn where to start."
        learning_session_id = f"session-{uuid4().hex[:10]}"
        self.audit_store.append(
            event_type=SESSION_STARTED_EVENT_TYPE,
            status="success",
            student_id=str(student_id),
            payload={
                "learning_session_id": learning_session_id,
                "goal_display": goal_display,
                "focus_outcome_title": focus_title,
            },
        )
        return SessionStartResponse(
            learning_session_id=learning_session_id,
            goal_display=goal_display,
            focus_outcome_title=focus_title,
        )

    def end_session(
        self, *, student_id: UUID, learning_session_id: str
    ) -> SessionRecap:
        completed = 0
        smooth = 0
        if self.observation_store is not None:
            observations = self.observation_store.list_recent(
                student_id=str(student_id), limit=200
            )
            session_observations = [
                observation
                for observation in observations
                if observation.learning_session_id == learning_session_id
            ]
            completed = sum(
                1 for observation in session_observations if observation.completed
            )
            smooth = sum(
                1
                for observation in session_observations
                if observation.completed and observation.error_count == 0
            )
        recap = SessionRecap(
            learning_session_id=learning_session_id,
            completed_activity_count=completed,
            smooth_activity_count=smooth,
            display_recap=self._display_recap(completed=completed, smooth=smooth),
        )
        self.audit_store.append(
            event_type=SESSION_COMPLETED_EVENT_TYPE,
            status="success",
            student_id=str(student_id),
            payload={
                "learning_session_id": learning_session_id,
                "completed_activity_count": completed,
                "smooth_activity_count": smooth,
            },
        )
        return recap

    def record_defect_report(
        self,
        *,
        student_id: UUID,
        generation_id: str,
        learning_session_id: str | None = None,
        note: str | None = None,
        reported_role: str | None = None,
    ) -> DefectReportResponse:
        self.audit_store.append(
            event_type=DEFECT_REPORT_EVENT_TYPE,
            status="open",
            student_id=str(student_id),
            payload={
                "generation_id": generation_id,
                "learning_session_id": learning_session_id,
                "note": note,
                "reported_role": reported_role,
            },
        )
        return DefectReportResponse()

    def _focus_outcome_title(self, student_id: UUID) -> str | None:
        try:
            summary = self.learner_progression_service.build_for_student(  # type: ignore[attr-defined]
                student_id=student_id
            )
        except Exception:  # noqa: BLE001 - a goal is nice-to-have, never blocking
            logger.warning("Could not build progression goal", exc_info=True)
            return None
        if summary is None:
            return None
        current = summary.current_outcome or summary.next_outcome
        return current.title if current is not None else None

    def _display_recap(self, *, completed: int, smooth: int) -> str:
        if completed == 0:
            return "Session wrapped up. See you next time!"
        activity_word = "activity" if completed == 1 else "activities"
        if smooth == completed:
            return (
                f"Nice work today! You finished {completed} {activity_word} "
                f"and everything went smoothly."
            )
        return (
            f"Nice work today! You finished {completed} {activity_word} — "
            f"{smooth} went smoothly, and the tricky ones are how we learn."
        )
