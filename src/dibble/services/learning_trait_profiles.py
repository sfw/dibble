from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from dibble.models.profile import CognitiveTraitScore, LearnerTraitProfileSummary
from dibble.models.telemetry import AuditEvent
from dibble.services.protocols import AuditStore


def _clamp(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


@dataclass(frozen=True, slots=True)
class LearningTraitProfileSnapshot:
    signal: str = "insufficient"
    matched_observation_count: int = 0
    matched_session_count: int = 0
    processing_speed: CognitiveTraitScore | None = None
    working_memory: CognitiveTraitScore | None = None
    spatial_reasoning: CognitiveTraitScore | None = None
    trait_stability: float = 0.0
    challenge_tolerance: float = 0.0
    rationale: str | None = None


@dataclass(slots=True)
class LearningTraitProfileBuilder:
    recency_window_days: int = 21
    max_matched_observations: int = 16
    minimum_session_count_for_stable_signal: int = 2
    minimum_observation_count_for_stable_signal: int = 4

    def build_from_observation_event(
        self,
        *,
        observation_event: AuditEvent,
        observation_events: list[AuditEvent],
        state_profile_event: AuditEvent | None = None,
    ) -> LearningTraitProfileSnapshot | None:
        if observation_event.event_type != "learner.observe" or observation_event.student_id is None:
            return None
        matched_events = self._matched_observation_events(
            observation_event=observation_event,
            observation_events=observation_events,
        )
        if not matched_events:
            return None

        session_ids = {
            str(event.payload.get("learning_session_id"))
            for event in matched_events
            if event.payload.get("learning_session_id")
        }
        matched_session_count = len(session_ids) if session_ids else min(1, len(matched_events))
        context = self._state_profile_context(state_profile_event)
        processing_speed = self._processing_speed(matched_events, context=context)
        working_memory = self._working_memory(matched_events, context=context)
        spatial_reasoning = self._spatial_reasoning(matched_events, context=context)
        trait_stability = self._trait_stability(
            events=matched_events,
            matched_session_count=matched_session_count,
            traits=[processing_speed, working_memory, spatial_reasoning],
        )
        challenge_tolerance = self._challenge_tolerance(matched_events, context=context)

        return LearningTraitProfileSnapshot(
            signal=self._signal_label(
                matched_observation_count=len(matched_events),
                matched_session_count=matched_session_count,
                traits=[processing_speed, working_memory, spatial_reasoning],
                trait_stability=trait_stability,
            ),
            matched_observation_count=len(matched_events),
            matched_session_count=matched_session_count,
            processing_speed=processing_speed,
            working_memory=working_memory,
            spatial_reasoning=spatial_reasoning,
            trait_stability=trait_stability,
            challenge_tolerance=challenge_tolerance,
            rationale=self._rationale(
                observation_count=len(matched_events),
                session_count=matched_session_count,
                context=context,
            ),
        )

    def _matched_observation_events(
        self,
        *,
        observation_event: AuditEvent,
        observation_events: list[AuditEvent],
    ) -> list[AuditEvent]:
        recent_cutoff = observation_event.created_at - timedelta(days=max(1, self.recency_window_days))
        matched = [
            event
            for event in observation_events
            if event.event_type == "learner.observe"
            and event.student_id == observation_event.student_id
            and recent_cutoff <= event.created_at <= observation_event.created_at
        ]
        matched.sort(key=lambda event: event.created_at, reverse=True)
        return matched[: self.max_matched_observations]

    def _processing_speed(self, events: list[AuditEvent], *, context: dict[str, float | str]) -> CognitiveTraitScore:
        ratios = [
            float(event.payload.get("response_time_ms", 0)) / max(1.0, float(event.payload.get("expected_duration_ms", 15000) or 15000))
            for event in events
        ]
        completion_rate = sum(1 for event in events if bool(event.payload.get("completed", True))) / len(events)
        pause_pressure = sum(float(event.payload.get("pause_count", 0.0)) for event in events) / len(events)
        state_speed_bonus = 0.04 if context.get("state_signal") == "independence_ready" else 0.02 if context.get("state_signal") == "recovering" else -0.04 if context.get("state_signal") == "support_needed" else 0.0
        score = (
            0.7
            - max((sum(ratios) / len(ratios)) - 1.0, 0.0) * 0.32
            + (completion_rate * 0.16)
            - min(pause_pressure, 4.0) * 0.03
            + state_speed_bonus
        )
        confidence = min(0.88, 0.34 + (len(events) * 0.04) + (float(context.get("state_confidence", 0.0)) * 0.18))
        return CognitiveTraitScore(value=round(_clamp(score, low=0.1, high=0.95), 2), confidence=round(confidence, 2))

    def _working_memory(self, events: list[AuditEvent], *, context: dict[str, float | str]) -> CognitiveTraitScore:
        challenge_events = [
            event
            for event in events
            if event.payload.get("task_type") in {"practice", "assessment"}
            and event.payload.get("support_level") == "low"
        ]
        relevant = challenge_events or events
        hints = sum(float(event.payload.get("hints_used", 0.0)) for event in relevant) / len(relevant)
        errors = sum(float(event.payload.get("error_count", 0.0)) for event in relevant) / len(relevant)
        switches = sum(float(event.payload.get("modality_switches", 0.0)) for event in relevant) / len(relevant)
        calibration = float(context.get("confidence_calibration", 0.5))
        load_penalty = max(0.0, float(context.get("total_load", 0.4)) - 0.55) * 0.12
        score = (
            0.58
            + (sum(1 for event in relevant if bool(event.payload.get("completed", True))) / len(relevant) * 0.14)
            + (calibration * 0.08)
            - min(hints, 4.0) * 0.05
            - min(errors, 4.0) * 0.05
            - min(switches, 4.0) * 0.03
            - load_penalty
        )
        confidence = min(
            0.86,
            0.32 + (len(relevant) * 0.05) + (float(context.get("state_confidence", 0.0)) * 0.15),
        )
        return CognitiveTraitScore(value=round(_clamp(score, low=0.1, high=0.95), 2), confidence=round(confidence, 2))

    def _spatial_reasoning(self, events: list[AuditEvent], *, context: dict[str, float | str]) -> CognitiveTraitScore | None:
        relevant = [
            event
            for event in events
            if event.payload.get("task_type") in {"worked_example", "explanation", "remediation"}
        ]
        if not relevant:
            return None
        completion_rate = sum(1 for event in relevant if bool(event.payload.get("completed", True))) / len(relevant)
        errors = sum(float(event.payload.get("error_count", 0.0)) for event in relevant) / len(relevant)
        switches = sum(float(event.payload.get("modality_switches", 0.0)) for event in relevant) / len(relevant)
        engagement_bonus = 0.05 if context.get("engagement") == "high" else 0.02 if context.get("engagement") == "medium" else -0.02
        score = (
            0.54
            + (completion_rate * 0.18)
            + engagement_bonus
            - min(errors, 3.0) * 0.06
            - min(switches, 3.0) * 0.04
        )
        confidence = min(
            0.82,
            0.28 + (len(relevant) * 0.08) + (float(context.get("state_confidence", 0.0)) * 0.14),
        )
        return CognitiveTraitScore(value=round(_clamp(score, low=0.1, high=0.95), 2), confidence=round(confidence, 2))

    def _signal_label(
        self,
        *,
        matched_observation_count: int,
        matched_session_count: int,
        traits: list[CognitiveTraitScore | None],
        trait_stability: float,
    ) -> str:
        available = [trait for trait in traits if trait is not None]
        if not available:
            return "insufficient"
        average_confidence = sum(trait.confidence for trait in available) / len(available)
        if (
            matched_session_count < self.minimum_session_count_for_stable_signal
            or matched_observation_count < self.minimum_observation_count_for_stable_signal
        ):
            return "tentative"
        if average_confidence < 0.55:
            return "tentative"
        if trait_stability < 0.52:
            return "tentative"
        return "stable"

    def _trait_stability(
        self,
        *,
        events: list[AuditEvent],
        matched_session_count: int,
        traits: list[CognitiveTraitScore | None],
    ) -> float:
        available = [trait for trait in traits if trait is not None]
        if not available:
            return 0.0
        ratios = [
            float(event.payload.get("response_time_ms", 0.0))
            / max(1.0, float(event.payload.get("expected_duration_ms", 15000) or 15000))
            for event in events
        ]
        speed_spread = 0.0 if not ratios else min(1.0, max(ratios) - min(ratios))
        outcomes = [
            (
                (0.4 if bool(event.payload.get("completed", True)) else 0.0)
                + (0.3 if float(event.payload.get("error_count", 0.0)) == 0 else 0.0)
                + (0.3 if float(event.payload.get("hints_used", 0.0)) == 0 else 0.0)
            )
            for event in events
        ]
        outcome_spread = 0.0 if not outcomes else min(1.0, max(outcomes) - min(outcomes))
        average_confidence = sum(trait.confidence for trait in available) / len(available)
        return round(
            _clamp(
                0.18
                + min(0.18, len(events) * 0.03)
                + min(0.14, matched_session_count * 0.04)
                + (average_confidence * 0.28)
                - (speed_spread * 0.18)
                - (outcome_spread * 0.14)
            ),
            2,
        )

    def _challenge_tolerance(self, events: list[AuditEvent], *, context: dict[str, float | str]) -> float:
        relevant = [
            event
            for event in events
            if event.payload.get("task_type") in {"practice", "assessment"}
            and event.payload.get("support_level") == "low"
        ]
        active = relevant or events
        completion_rate = sum(1 for event in active if bool(event.payload.get("completed", True))) / len(active)
        hints = sum(float(event.payload.get("hints_used", 0.0)) for event in active) / len(active)
        errors = sum(float(event.payload.get("error_count", 0.0)) for event in active) / len(active)
        load_penalty = max(0.0, float(context.get("total_load", 0.4)) - 0.55) * 0.18
        calibration_bonus = float(context.get("confidence_calibration", 0.5)) * 0.12
        return round(
            _clamp(
                0.28
                + (completion_rate * 0.28)
                + calibration_bonus
                - min(hints, 4.0) * 0.07
                - min(errors, 4.0) * 0.08
                - load_penalty
            ),
            2,
        )

    def _state_profile_context(self, state_profile_event: AuditEvent | None) -> dict[str, float | str]:
        if state_profile_event is None:
            return {}
        return {
            "state_signal": str(state_profile_event.payload.get("state_profile_signal", "insufficient")),
            "state_confidence": float(state_profile_event.payload.get("average_run_confidence", 0.0)),
            "engagement": str(state_profile_event.payload.get("engagement", "medium")),
            "total_load": float(state_profile_event.payload.get("total_load", 0.4)),
            "confidence_calibration": float(state_profile_event.payload.get("confidence_calibration", 0.5)),
        }

    def _rationale(
        self,
        *,
        observation_count: int,
        session_count: int,
        context: dict[str, float | str],
    ) -> str:
        state_signal = context.get("state_signal")
        if state_signal in {"support_needed", "independence_ready", "recovering"}:
            return (
                f"Recent learner observations across {session_count} sessions were compacted into a durable trait profile "
                f"and calibrated against {state_signal.replace('_', ' ')} state evidence."
            )
        return (
            f"Recent learner observations across {observation_count} observations and {session_count} sessions "
            "were compacted into a durable cognitive-trait profile."
        )


@dataclass(slots=True)
class LearningTraitProfileRecorder:
    audit_store: AuditStore
    profile_builder: LearningTraitProfileBuilder = field(default_factory=LearningTraitProfileBuilder)
    max_events: int = 1200

    def record_from_observation_events(self, *, observation_events: list[AuditEvent]) -> list[AuditEvent]:
        if not observation_events:
            return []
        events = self.audit_store.list(limit=self.max_events)
        all_observation_events = [event for event in events if event.event_type == "learner.observe"]
        state_profile_events = [event for event in events if event.event_type == "learning.state.profile"]
        recorded: list[AuditEvent] = []
        for observation_event in observation_events:
            if observation_event.event_type != "learner.observe" or observation_event.student_id is None:
                continue
            state_profile_event = self._latest_state_profile(
                student_id=str(observation_event.student_id),
                state_profile_events=state_profile_events,
            )
            snapshot = self.profile_builder.build_from_observation_event(
                observation_event=observation_event,
                observation_events=all_observation_events,
                state_profile_event=state_profile_event,
            )
            if snapshot is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.cognitive_trait.profile",
                    status="success",
                    student_id=str(observation_event.student_id),
                    payload={
                        "source_observation_event_id": observation_event.event_id,
                        "matched_observation_count": snapshot.matched_observation_count,
                        "matched_session_count": snapshot.matched_session_count,
                        "profile_signal": snapshot.signal,
                        "processing_speed": self._dump_trait(snapshot.processing_speed),
                        "working_memory": self._dump_trait(snapshot.working_memory),
                        "spatial_reasoning": self._dump_trait(snapshot.spatial_reasoning),
                        "trait_stability": snapshot.trait_stability,
                        "challenge_tolerance": snapshot.challenge_tolerance,
                        "trait_profile_rationale": snapshot.rationale,
                    },
                )
            )
        return recorded

    def _latest_state_profile(
        self,
        *,
        student_id: str,
        state_profile_events: list[AuditEvent],
    ) -> AuditEvent | None:
        for event in state_profile_events:
            if str(event.student_id) == student_id:
                return event
        return None

    def _dump_trait(self, trait: CognitiveTraitScore | None) -> dict[str, object] | None:
        if trait is None:
            return None
        return {
            "value": trait.value,
            "confidence": trait.confidence,
            "assessed_at": trait.assessed_at.isoformat(),
        }


@dataclass(slots=True)
class LearnerTraitProfileSignalService:
    audit_store: AuditStore
    max_events: int = 400

    def latest_for_student(self, *, student_id: UUID) -> LearnerTraitProfileSummary:
        events = self.audit_store.list(limit=self.max_events)
        event = next(
            (
                item
                for item in events
                if item.event_type == "learning.cognitive_trait.profile" and item.student_id == student_id
            ),
            None,
        )
        if event is None:
            return LearnerTraitProfileSummary()
        return LearnerTraitProfileSummary(
            signal=str(event.payload.get("profile_signal", "insufficient")),
            source="trait_profile",
            matched_observation_count=int(event.payload.get("matched_observation_count", 0)),
            matched_session_count=int(event.payload.get("matched_session_count", 0)),
            processing_speed=self._trait_from_payload(event.payload.get("processing_speed")),
            working_memory=self._trait_from_payload(event.payload.get("working_memory")),
            spatial_reasoning=self._trait_from_payload(event.payload.get("spatial_reasoning")),
            trait_stability=float(event.payload.get("trait_stability", 0.0)),
            challenge_tolerance=float(event.payload.get("challenge_tolerance", 0.0)),
            rationale=str(event.payload.get("trait_profile_rationale"))
            if event.payload.get("trait_profile_rationale") is not None
            else None,
            updated_at=event.created_at,
        )

    def _trait_from_payload(self, value: object) -> CognitiveTraitScore | None:
        if not isinstance(value, dict):
            return None
        return CognitiveTraitScore.model_validate(value)
