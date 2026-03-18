from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dibble.models.generation import GenerationRequest, RouteCalibrationSummary
from dibble.models.telemetry import AuditEvent
from dibble.services.generation_prompt_outcomes import GenerationPromptOutcomeScorer
from dibble.services.learning_calibration_profiles import (
    LearningCalibrationProfileResolver,
)
from dibble.services.learning_progress_profiles import LearningProgressProfileResolver
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class RouterCalibrationSignalService:
    audit_store: AuditStore
    outcome_scorer: GenerationPromptOutcomeScorer = field(
        default_factory=GenerationPromptOutcomeScorer
    )
    profile_resolver: LearningCalibrationProfileResolver = field(
        default_factory=LearningCalibrationProfileResolver
    )
    progress_profile_resolver: LearningProgressProfileResolver = field(
        default_factory=LearningProgressProfileResolver
    )
    max_events: int = 500
    max_matched_runs: int = 4
    recency_window_hours: int = 12
    minimum_confidence_for_stable_signal: float = 0.55
    progress_trend_delta_threshold: float = 0.08

    def signal_for(
        self, *, student_id: UUID, request: GenerationRequest
    ) -> RouteCalibrationSummary:
        events = self.audit_store.list(limit=self.max_events)
        progress_profile_events = [
            event
            for event in events
            if event.event_type == "learning.progress.profile"
            and event.student_id == student_id
        ]
        matched_progress_profiles = (
            self.progress_profile_resolver.matched_profile_events(
                profile_events=progress_profile_events,
                request=request,
            )
        )
        if matched_progress_profiles:
            return self._aggregate_progress_profile_events(matched_progress_profiles)
        profile_events = [
            event
            for event in events
            if event.event_type == "learning.calibration.profile"
            and event.student_id == student_id
        ]
        matched_profiles = self.profile_resolver.matched_profile_events(
            profile_events=profile_events, request=request
        )
        if matched_profiles:
            return self._aggregate_profile_events(matched_profiles)
        summary_events = [
            event
            for event in events
            if event.event_type == "learning.run.summary"
            and event.student_id == student_id
        ]
        matched_summaries = self._matched_summary_events(
            summary_events=summary_events, request=request
        )
        if matched_summaries:
            return self._aggregate_summary_events(matched_summaries)
        generation_events = [
            event for event in events if event.event_type == "content.generate"
        ]
        observation_events = [
            event
            for event in events
            if event.event_type == "learner.observe" and event.student_id == student_id
        ]
        assessment_events = [
            event
            for event in events
            if event.event_type == "assessment.socratic"
            and event.student_id == student_id
        ]
        matched_generations = self._matched_generations(
            generation_events=generation_events,
            student_id=student_id,
            request=request,
        )
        if not matched_generations:
            return RouteCalibrationSummary()

        stable_samples = []
        for event in matched_generations:
            sample = self.outcome_scorer.score(
                generation_event=event,
                candidate_generations=generation_events,
                candidate_observations=observation_events,
                candidate_assessments=assessment_events,
            )
            if sample.run_summary_score is not None:
                stable_samples.append(sample)
        if not stable_samples:
            return RouteCalibrationSummary()

        average_run_outcome_score = round(
            sum(sample.run_summary_score or 0.0 for sample in stable_samples)
            / len(stable_samples),
            2,
        )
        average_confidence = round(
            sum(sample.run_calibration_confidence for sample in stable_samples)
            / len(stable_samples),
            2,
        )
        positive_run_rate = round(
            sum(
                1
                for sample in stable_samples
                if sample.run_calibration_signal == "positive"
            )
            / len(stable_samples),
            2,
        )
        negative_run_rate = round(
            sum(
                1
                for sample in stable_samples
                if sample.run_calibration_signal == "negative"
            )
            / len(stable_samples),
            2,
        )
        return RouteCalibrationSummary(
            signal=self._signal_label(
                average_run_outcome_score=average_run_outcome_score,
                average_confidence=average_confidence,
                positive_run_rate=positive_run_rate,
                negative_run_rate=negative_run_rate,
            ),
            source="derived",
            confidence=average_confidence,
            average_run_outcome_score=average_run_outcome_score,
            matched_run_count=len(stable_samples),
            positive_run_rate=positive_run_rate,
            negative_run_rate=negative_run_rate,
            progress_signal="stable",
        )

    def _aggregate_progress_profile_events(
        self, profile_events: list[AuditEvent]
    ) -> RouteCalibrationSummary:
        total_run_count = sum(
            max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        )
        if total_run_count <= 0:
            return RouteCalibrationSummary()
        average_run_outcome_score = round(
            sum(
                float(event.payload.get("average_run_outcome_score", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        average_confidence = round(
            sum(
                float(event.payload.get("average_run_confidence", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        positive_run_rate = round(
            sum(
                float(event.payload.get("positive_run_rate", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        negative_run_rate = round(
            sum(
                float(event.payload.get("negative_run_rate", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        progress_delta = round(
            sum(
                float(event.payload.get("progress_delta", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        return RouteCalibrationSummary(
            signal=self._signal_label(
                average_run_outcome_score=average_run_outcome_score,
                average_confidence=average_confidence,
                positive_run_rate=positive_run_rate,
                negative_run_rate=negative_run_rate,
            ),
            source="progress_profile",
            confidence=average_confidence,
            average_run_outcome_score=average_run_outcome_score,
            matched_run_count=total_run_count,
            positive_run_rate=positive_run_rate,
            negative_run_rate=negative_run_rate,
            progress_signal=self._progress_signal_label(
                average_confidence=average_confidence,
                progress_delta=progress_delta,
            ),
            progress_delta=progress_delta,
        )

    def _aggregate_profile_events(
        self, profile_events: list[AuditEvent]
    ) -> RouteCalibrationSummary:
        total_run_count = sum(
            max(1, int(event.payload.get("matched_run_count", 0)))
            for event in profile_events
        )
        if total_run_count <= 0:
            return RouteCalibrationSummary()
        average_run_outcome_score = round(
            sum(
                float(event.payload.get("average_run_outcome_score", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        average_confidence = round(
            sum(
                float(event.payload.get("average_run_confidence", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        positive_run_rate = round(
            sum(
                float(event.payload.get("positive_run_rate", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        negative_run_rate = round(
            sum(
                float(event.payload.get("negative_run_rate", 0.0))
                * max(1, int(event.payload.get("matched_run_count", 0)))
                for event in profile_events
            )
            / total_run_count,
            2,
        )
        return RouteCalibrationSummary(
            signal=self._signal_label(
                average_run_outcome_score=average_run_outcome_score,
                average_confidence=average_confidence,
                positive_run_rate=positive_run_rate,
                negative_run_rate=negative_run_rate,
            ),
            source="profile",
            confidence=average_confidence,
            average_run_outcome_score=average_run_outcome_score,
            matched_run_count=total_run_count,
            positive_run_rate=positive_run_rate,
            negative_run_rate=negative_run_rate,
            progress_signal="stable",
        )

    def _matched_summary_events(
        self,
        *,
        summary_events: list[AuditEvent],
        request: GenerationRequest,
    ) -> list[AuditEvent]:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(
            hours=max(1, self.recency_window_hours)
        )
        scored_matches: list[tuple[int, float, AuditEvent]] = []
        for event in summary_events:
            if event.created_at < recent_cutoff:
                continue
            match_tier = self._request_match_tier(
                request=request, payload=event.payload
            )
            match_score = self._request_match_score(
                request=request, payload=event.payload
            )
            if match_tier <= 0 or match_score <= 0.0:
                continue
            scored_matches.append((match_tier, match_score, event))
        if not scored_matches:
            return []
        strongest_tier = max(tier for tier, _, _ in scored_matches)
        latest_by_generation: dict[str, tuple[float, AuditEvent]] = {}
        for tier, match_score, event in scored_matches:
            if tier != strongest_tier:
                continue
            generation_id = str(
                event.payload.get("generation_id")
                or event.payload.get("source_generation_event_id")
            )
            current = latest_by_generation.get(generation_id)
            if current is None or (match_score, event.created_at) > (
                current[0],
                current[1].created_at,
            ):
                latest_by_generation[generation_id] = (match_score, event)
        matched = list(latest_by_generation.values())
        matched.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return [event for _, event in matched[: self.max_matched_runs]]

    def _aggregate_summary_events(
        self, summary_events: list[AuditEvent]
    ) -> RouteCalibrationSummary:
        average_run_outcome_score = round(
            sum(
                float(event.payload.get("run_summary_score", 0.0))
                for event in summary_events
            )
            / len(summary_events),
            2,
        )
        average_confidence = round(
            sum(
                float(event.payload.get("run_calibration_confidence", 0.0))
                for event in summary_events
            )
            / len(summary_events),
            2,
        )
        positive_run_rate = round(
            sum(
                1
                for event in summary_events
                if event.payload.get("run_calibration_signal") == "positive"
            )
            / len(summary_events),
            2,
        )
        negative_run_rate = round(
            sum(
                1
                for event in summary_events
                if event.payload.get("run_calibration_signal") == "negative"
            )
            / len(summary_events),
            2,
        )
        return RouteCalibrationSummary(
            signal=self._signal_label(
                average_run_outcome_score=average_run_outcome_score,
                average_confidence=average_confidence,
                positive_run_rate=positive_run_rate,
                negative_run_rate=negative_run_rate,
            ),
            source="run_summary",
            confidence=average_confidence,
            average_run_outcome_score=average_run_outcome_score,
            matched_run_count=len(summary_events),
            positive_run_rate=positive_run_rate,
            negative_run_rate=negative_run_rate,
            progress_signal="stable",
        )

    def _matched_generations(
        self,
        *,
        generation_events: list[AuditEvent],
        student_id: UUID,
        request: GenerationRequest,
    ) -> list[AuditEvent]:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(
            hours=max(1, self.recency_window_hours)
        )
        scored_matches: list[tuple[int, float, AuditEvent]] = []
        for event in generation_events:
            if event.student_id != student_id:
                continue
            if event.created_at < recent_cutoff:
                continue
            match_tier = self._request_match_tier(
                request=request, payload=event.payload
            )
            match_score = self._request_match_score(
                request=request, payload=event.payload
            )
            if match_tier <= 0 or match_score <= 0.0:
                continue
            scored_matches.append((match_tier, match_score, event))
        if not scored_matches:
            return []
        strongest_tier = max(tier for tier, _, _ in scored_matches)
        strongest_matches = [
            (match_score, event)
            for tier, match_score, event in scored_matches
            if tier == strongest_tier
        ]
        strongest_matches.sort(
            key=lambda item: (item[0], item[1].created_at), reverse=True
        )
        return [event for _, event in strongest_matches[: self.max_matched_runs]]

    def _request_match_score(
        self, *, request: GenerationRequest, payload: dict[str, object]
    ) -> float:
        score = 0.0

        if (
            request.learning_session_id
            and payload.get("learning_session_id") == request.learning_session_id
        ):
            score += 4.0

        score += (
            self._overlap_score(request.target_kc_ids, payload.get("target_kc_ids"))
            * 3.0
        )
        score += (
            self._overlap_score(request.target_lo_ids, payload.get("target_lo_ids"))
            * 2.0
        )

        if payload.get("intent") == request.intent.value:
            score += 0.75

        if (
            not request.target_kc_ids
            and not request.target_lo_ids
            and payload.get("intent") == request.intent.value
        ):
            score += 0.25

        return score

    def _request_match_tier(
        self, *, request: GenerationRequest, payload: dict[str, object]
    ) -> int:
        if (
            request.learning_session_id
            and payload.get("learning_session_id") == request.learning_session_id
        ):
            return 3
        if (
            self._overlap_score(request.target_kc_ids, payload.get("target_kc_ids"))
            > 0.0
        ):
            return 2
        if (
            self._overlap_score(request.target_lo_ids, payload.get("target_lo_ids"))
            > 0.0
        ):
            return 2
        if payload.get("intent") == request.intent.value:
            return 1
        return 0

    def _signal_label(
        self,
        *,
        average_run_outcome_score: float,
        average_confidence: float,
        positive_run_rate: float,
        negative_run_rate: float,
    ) -> str:
        if average_confidence < self.minimum_confidence_for_stable_signal:
            return "tentative"
        if positive_run_rate >= 0.6 and average_run_outcome_score >= 0.7:
            return "positive"
        if negative_run_rate >= 0.5 and average_run_outcome_score <= 0.5:
            return "negative"
        return "mixed"

    def _progress_signal_label(
        self,
        *,
        average_confidence: float,
        progress_delta: float,
    ) -> str:
        if average_confidence < self.minimum_confidence_for_stable_signal:
            return "tentative"
        if progress_delta >= self.progress_trend_delta_threshold:
            return "improving"
        if progress_delta <= -self.progress_trend_delta_threshold:
            return "declining"
        return "stable"

    def _overlap_score(self, left: list[str], right: object) -> float:
        left_values = {str(item) for item in left}
        right_values = (
            {str(item) for item in right} if isinstance(right, list) else set()
        )
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(
            len(left_values), len(right_values)
        )
