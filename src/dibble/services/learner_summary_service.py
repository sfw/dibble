from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from dibble.models.profile import (
    LearnerCalibrationSummary,
    LearnerFlowSummary,
    LearnerProgressSummary,
    ProfileSummary,
    RecentLearnerActivity,
)
from dibble.services.learner_flow_service import LearnerFlowService
from dibble.services.learning_state_profiles import LearnerStateSignalService
from dibble.services.learning_trait_profiles import LearnerTraitProfileSignalService
from dibble.services.learner_strategy_profiles import LearnerStrategySignalService
from dibble.services.protocols import AuditStore, ProfileStore


@dataclass(slots=True)
class LearnerSummaryService:
    profile_store: ProfileStore
    audit_store: AuditStore
    strategy_signal_service: LearnerStrategySignalService
    state_signal_service: LearnerStateSignalService
    trait_profile_signal_service: LearnerTraitProfileSignalService
    learner_flow_service: LearnerFlowService | None = None
    max_events: int = 200

    def build_for_student(self, *, student_id: UUID) -> ProfileSummary | None:
        profile = self.profile_store.get(student_id)
        if profile is None:
            return None
        events = [event for event in self.audit_store.list(limit=self.max_events) if event.student_id == student_id]
        return ProfileSummary.from_profile(
            profile,
            calibration=self._latest_calibration(events),
            progress=self._latest_progress(events),
            strategy=self.strategy_signal_service.latest_for_student(student_id=student_id),
            state_profile=self.state_signal_service.latest_for_student(student_id=student_id),
            trait_profile=self.trait_profile_signal_service.latest_for_student(student_id=student_id),
            recent_activity=self._recent_activity(events),
            current_flow=(
                self.learner_flow_service.build_for_student(student_id=student_id)
                if self.learner_flow_service is not None
                else LearnerFlowSummary()
            ),
        )

    def _latest_calibration(self, events) -> LearnerCalibrationSummary:
        profile_event = next((event for event in events if event.event_type == "learning.calibration.profile"), None)
        if profile_event is not None:
            return LearnerCalibrationSummary(
                signal=str(profile_event.payload.get("profile_signal", "insufficient")),
                source="profile",
                average_run_outcome_score=self._maybe_float(profile_event.payload.get("average_run_outcome_score")),
                confidence=float(profile_event.payload.get("average_run_confidence", 0.0)),
                matched_run_count=int(profile_event.payload.get("matched_run_count", 0)),
                matched_session_count=int(profile_event.payload.get("matched_session_count", 0)),
                intent=self._maybe_str(profile_event.payload.get("intent")),
                content_type=self._maybe_str(profile_event.payload.get("content_type")),
                target_kc_ids=self._string_list(profile_event.payload.get("target_kc_ids")),
                target_lo_ids=self._string_list(profile_event.payload.get("target_lo_ids")),
                updated_at=profile_event.created_at,
            )

        summary_event = next((event for event in events if event.event_type == "learning.run.summary"), None)
        if summary_event is not None:
            return LearnerCalibrationSummary(
                signal=str(summary_event.payload.get("run_calibration_signal", "insufficient")),
                source="run_summary",
                average_run_outcome_score=self._maybe_float(summary_event.payload.get("run_summary_score")),
                confidence=float(summary_event.payload.get("run_calibration_confidence", 0.0)),
                matched_run_count=max(1, int(summary_event.payload.get("run_event_count", 0))),
                matched_session_count=1 if summary_event.payload.get("learning_session_id") else 0,
                intent=self._maybe_str(summary_event.payload.get("intent")),
                content_type=self._maybe_str(summary_event.payload.get("content_type")),
                target_kc_ids=self._string_list(summary_event.payload.get("target_kc_ids")),
                target_lo_ids=self._string_list(summary_event.payload.get("target_lo_ids")),
                updated_at=summary_event.created_at,
            )

        return LearnerCalibrationSummary()

    def _latest_progress(self, events) -> LearnerProgressSummary:
        progress_event = next((event for event in events if event.event_type == "learning.progress.profile"), None)
        if progress_event is None:
            return LearnerProgressSummary()
        return LearnerProgressSummary(
            signal=str(progress_event.payload.get("progress_signal", "insufficient")),
            source="profile",
            average_run_outcome_score=self._maybe_float(progress_event.payload.get("average_run_outcome_score")),
            confidence=float(progress_event.payload.get("average_run_confidence", 0.0)),
            matched_run_count=int(progress_event.payload.get("matched_run_count", 0)),
            matched_session_count=int(progress_event.payload.get("matched_session_count", 0)),
            positive_run_rate=float(progress_event.payload.get("positive_run_rate", 0.0)),
            negative_run_rate=float(progress_event.payload.get("negative_run_rate", 0.0)),
            recent_average_run_outcome_score=self._maybe_float(
                progress_event.payload.get("recent_average_run_outcome_score")
            ),
            prior_average_run_outcome_score=self._maybe_float(
                progress_event.payload.get("prior_average_run_outcome_score")
            ),
            progress_delta=float(progress_event.payload.get("progress_delta", 0.0)),
            updated_at=progress_event.created_at,
        )
    def _recent_activity(self, events) -> RecentLearnerActivity:
        return RecentLearnerActivity(
            generation_count=sum(1 for event in events if event.event_type == "content.generate"),
            observation_count=sum(1 for event in events if event.event_type == "learner.observe"),
            socratic_assessment_count=sum(1 for event in events if event.event_type == "assessment.socratic"),
            last_learning_session_id=self._latest_payload_value(events, "learning_session_id"),
            last_generation_id=self._latest_payload_value(events, "generation_id"),
            last_event_at=events[0].created_at if events else None,
        )

    def _latest_payload_value(self, events, key: str) -> str | None:
        for event in events:
            value = event.payload.get(key)
            if value:
                return str(value)
        return None

    def _maybe_float(self, value: object) -> float | None:
        return float(value) if value is not None else None

    def _maybe_str(self, value: object) -> str | None:
        return str(value) if value is not None else None

    def _string_list(self, value: object) -> list[str]:
        return [str(item) for item in value] if isinstance(value, list) else []
