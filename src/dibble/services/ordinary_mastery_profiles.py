from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from dibble.models.profile import OrdinaryMasterySummary
from dibble.models.telemetry import AuditEvent
from dibble.services.protocols import AuditStore
from dibble.services.recency import recency_weight


def _clamp(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


@dataclass(frozen=True, slots=True)
class OrdinaryMasteryProfileSnapshot:
    signal: str = "insufficient"
    confidence: float = 0.0
    matched_observation_count: int = 0
    matched_session_count: int = 0
    average_observed_mastery: float | None = None
    low_support_success_rate: float = 0.0
    high_support_dependency_rate: float = 0.0
    rationale: str | None = None


@dataclass(slots=True)
class OrdinaryMasteryProfileBuilder:
    recency_window_days: int = 28
    max_matched_observations: int = 10
    minimum_stable_observation_count: int = 4
    minimum_stable_session_count: int = 2

    def build_from_observation_event(
        self,
        *,
        observation_event: AuditEvent,
        observation_events: list[AuditEvent],
    ) -> OrdinaryMasteryProfileSnapshot | None:
        if observation_event.event_type != "learner.observe" or observation_event.student_id is None:
            return None
        if not self._supports_profile(observation_event):
            return None

        matched_events = self._matched_observation_events(
            observation_event=observation_event,
            observation_events=observation_events,
        )
        if not matched_events:
            return None

        reference_time = observation_event.created_at
        weights = [
            recency_weight(event.created_at, reference_time, lookback_days=self.recency_window_days)
            for event in matched_events
        ]
        mastery_scores = [self._mastery_score(event) for event in matched_events]
        total_weight = sum(weights) or 1.0
        average_observed_mastery = round(
            sum(score * w for score, w in zip(mastery_scores, weights)) / total_weight, 2
        )
        session_ids = {
            str(event.payload.get("learning_session_id"))
            for event in matched_events
            if event.payload.get("learning_session_id")
        }
        matched_session_count = len(session_ids) if session_ids else min(1, len(matched_events))
        low_support_success_rate = self._low_support_success_rate(events=matched_events, weights=weights)
        high_support_dependency_rate = self._high_support_dependency_rate(events=matched_events, weights=weights)
        signal = self._signal_label(
            matched_observation_count=len(matched_events),
            matched_session_count=matched_session_count,
            average_observed_mastery=average_observed_mastery,
            low_support_success_rate=low_support_success_rate,
            high_support_dependency_rate=high_support_dependency_rate,
        )
        confidence = self._confidence(
            signal=signal,
            matched_observation_count=len(matched_events),
            matched_session_count=matched_session_count,
            average_observed_mastery=average_observed_mastery,
        )
        return OrdinaryMasteryProfileSnapshot(
            signal=signal,
            confidence=confidence,
            matched_observation_count=len(matched_events),
            matched_session_count=matched_session_count,
            average_observed_mastery=average_observed_mastery,
            low_support_success_rate=low_support_success_rate,
            high_support_dependency_rate=high_support_dependency_rate,
            rationale=self._rationale(
                signal=signal,
                average_observed_mastery=average_observed_mastery,
                matched_observation_count=len(matched_events),
                matched_session_count=matched_session_count,
                low_support_success_rate=low_support_success_rate,
                high_support_dependency_rate=high_support_dependency_rate,
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
            and self._supports_profile(event)
            and self._targets_overlap(
                target_kc_ids=self._string_list(observation_event.payload.get("target_kc_ids")),
                observed_kc_ids=self._string_list(event.payload.get("target_kc_ids")),
                target_lo_ids=self._string_list(observation_event.payload.get("target_lo_ids")),
                observed_lo_ids=self._string_list(event.payload.get("target_lo_ids")),
            )
        ]
        matched.sort(key=lambda event: event.created_at, reverse=True)
        return matched[: self.max_matched_observations]

    def _supports_profile(self, event: AuditEvent) -> bool:
        if event.payload.get("observation_mastery_applied") is not True:
            return False
        if str(event.payload.get("task_type")) not in {"practice", "remediation"}:
            return False
        return bool(event.payload.get("target_kc_ids") or event.payload.get("target_lo_ids"))

    def _mastery_score(self, event: AuditEvent) -> float:
        value = event.payload.get("observation_inferred_mastery")
        if not isinstance(value, (int, float)):
            value = event.payload.get("observation_average_recent_mastery")
        return round(_clamp(float(value or 0.0)), 2)

    def _low_support_success_rate(
        self, *, events: list[AuditEvent], weights: list[float] | None = None,
    ) -> float:
        if weights is None:
            weights = [1.0] * len(events)
        total = sum(weights) or 1.0
        weighted_successes = sum(w for event, w in zip(events, weights) if self._is_low_support_success(event))
        return round(weighted_successes / total, 2)

    def _high_support_dependency_rate(
        self, *, events: list[AuditEvent], weights: list[float] | None = None,
    ) -> float:
        if weights is None:
            weights = [1.0] * len(events)
        total = sum(weights) or 1.0
        weighted_deps = sum(w for event, w in zip(events, weights) if self._is_high_support_dependency(event))
        return round(weighted_deps / total, 2)

    def _is_low_support_success(self, event: AuditEvent) -> bool:
        return (
            event.payload.get("completed") is True
            and event.payload.get("support_level") == "low"
            and int(event.payload.get("hints_used", 0)) <= 1
            and int(event.payload.get("error_count", 0)) <= 1
            and self._mastery_score(event) >= 0.64
        )

    def _is_high_support_dependency(self, event: AuditEvent) -> bool:
        return (
            event.payload.get("support_level") == "high"
            and (
                int(event.payload.get("hints_used", 0)) >= 2
                or int(event.payload.get("error_count", 0)) >= 1
                or self._mastery_score(event) < 0.66
            )
        )

    def _signal_label(
        self,
        *,
        matched_observation_count: int,
        matched_session_count: int,
        average_observed_mastery: float,
        low_support_success_rate: float,
        high_support_dependency_rate: float,
    ) -> str:
        if matched_observation_count < 2:
            return "insufficient"
        if high_support_dependency_rate >= 0.6 and low_support_success_rate <= 0.35:
            return "support_dependent"
        if (
            matched_observation_count >= self.minimum_stable_observation_count
            and matched_session_count >= self.minimum_stable_session_count
            and average_observed_mastery >= 0.72
            and low_support_success_rate >= 0.5
            and high_support_dependency_rate <= 0.25
        ):
            return "durable_mastery"
        if average_observed_mastery >= 0.62 and low_support_success_rate >= 0.3:
            return "emerging_mastery"
        if average_observed_mastery < 0.52:
            return "fragile"
        if matched_session_count >= 2 and high_support_dependency_rate <= 0.35:
            return "emerging_mastery"
        return "fragile"

    def _confidence(
        self,
        *,
        signal: str,
        matched_observation_count: int,
        matched_session_count: int,
        average_observed_mastery: float,
    ) -> float:
        signal_bonus = {
            "durable_mastery": 0.14,
            "emerging_mastery": 0.08,
            "support_dependent": 0.1,
            "fragile": 0.06,
            "insufficient": 0.0,
        }[signal]
        return round(
            _clamp(
                0.18
                + min(0.25, matched_observation_count * 0.05)
                + min(0.18, matched_session_count * 0.08)
                + signal_bonus
                + (abs(average_observed_mastery - 0.5) * 0.18),
                high=0.92,
            ),
            2,
        )

    def _rationale(
        self,
        *,
        signal: str,
        average_observed_mastery: float,
        matched_observation_count: int,
        matched_session_count: int,
        low_support_success_rate: float,
        high_support_dependency_rate: float,
    ) -> str:
        if signal == "durable_mastery":
            return (
                f"Recent ordinary practice evidence stayed strong across {matched_observation_count} observations "
                f"and {matched_session_count} sessions (average mastery {average_observed_mastery:.2f}, "
                f"low-support success rate {low_support_success_rate:.2f}), so future ordinary writeback can trust "
                "similar low-support successes a bit more."
            )
        if signal == "support_dependent":
            return (
                f"Recent ordinary practice evidence remained support-heavy across {matched_observation_count} observations "
                f"(high-support dependency rate {high_support_dependency_rate:.2f}), so future ordinary writeback should "
                "discount more scaffolded successes."
            )
        if signal == "emerging_mastery":
            return (
                f"Recent ordinary practice evidence is moving in the right direction across {matched_session_count} sessions "
                f"(average mastery {average_observed_mastery:.2f}), but durable mastery is not yet stable."
            )
        if signal == "fragile":
            return (
                f"Recent ordinary practice evidence remains inconsistent (average mastery {average_observed_mastery:.2f}, "
                f"low-support success rate {low_support_success_rate:.2f}), so durable mastery should stay conservative."
            )
        return (
            f"Only light ordinary practice evidence is available ({matched_observation_count} matching observations), "
            "so no durable mastery signal was formed."
        )

    def _targets_overlap(
        self,
        *,
        target_kc_ids: list[str],
        observed_kc_ids: list[str],
        target_lo_ids: list[str],
        observed_lo_ids: list[str],
    ) -> bool:
        return bool(set(target_kc_ids).intersection(observed_kc_ids) or set(target_lo_ids).intersection(observed_lo_ids))

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None]


@dataclass(slots=True)
class OrdinaryMasteryProfileRecorder:
    audit_store: AuditStore
    profile_builder: OrdinaryMasteryProfileBuilder = field(default_factory=OrdinaryMasteryProfileBuilder)
    max_events: int = 1200

    def record_from_observation_events(self, *, observation_events: list[AuditEvent]) -> list[AuditEvent]:
        if not observation_events:
            return []
        events = self.audit_store.list(limit=self.max_events)
        all_observation_events = [event for event in events if event.event_type == "learner.observe"]
        recorded: list[AuditEvent] = []
        for observation_event in observation_events:
            snapshot = self.profile_builder.build_from_observation_event(
                observation_event=observation_event,
                observation_events=all_observation_events,
            )
            if snapshot is None:
                continue
            recorded.append(
                self.audit_store.append(
                    event_type="learning.ordinary_mastery.profile",
                    status="success",
                    student_id=str(observation_event.student_id),
                    payload={
                        "source_observation_event_id": observation_event.event_id,
                        "target_kc_ids": self.profile_builder._string_list(observation_event.payload.get("target_kc_ids")),
                        "target_lo_ids": self.profile_builder._string_list(observation_event.payload.get("target_lo_ids")),
                        "profile_signal": snapshot.signal,
                        "profile_confidence": snapshot.confidence,
                        "matched_observation_count": snapshot.matched_observation_count,
                        "matched_session_count": snapshot.matched_session_count,
                        "average_observed_mastery": snapshot.average_observed_mastery,
                        "low_support_success_rate": snapshot.low_support_success_rate,
                        "high_support_dependency_rate": snapshot.high_support_dependency_rate,
                        "ordinary_mastery_profile_rationale": snapshot.rationale,
                    },
                )
            )
        return recorded


@dataclass(slots=True)
class OrdinaryMasterySignalService:
    audit_store: AuditStore
    max_events: int = 400

    def latest_for_student(
        self,
        *,
        student_id: UUID,
        target_kc_ids: list[str],
        target_lo_ids: list[str],
    ) -> OrdinaryMasterySummary:
        events = self.audit_store.list(limit=self.max_events)
        request_has_targets = bool(target_kc_ids or target_lo_ids)
        fallback_event: AuditEvent | None = None
        for event in events:
            if event.event_type != "learning.ordinary_mastery.profile" or event.student_id != student_id:
                continue
            if fallback_event is None and not request_has_targets:
                fallback_event = event
            if self._targets_overlap(
                target_kc_ids=target_kc_ids,
                observed_kc_ids=self._string_list(event.payload.get("target_kc_ids")),
                target_lo_ids=target_lo_ids,
                observed_lo_ids=self._string_list(event.payload.get("target_lo_ids")),
            ):
                return self._summary_from_event(event)
        return self._summary_from_event(fallback_event) if fallback_event is not None else OrdinaryMasterySummary()

    def _summary_from_event(self, event: AuditEvent) -> OrdinaryMasterySummary:
        return OrdinaryMasterySummary(
            signal=str(event.payload.get("profile_signal", "insufficient")),
            source="ordinary_mastery_profile",
            confidence=float(event.payload.get("profile_confidence", 0.0)),
            matched_observation_count=int(event.payload.get("matched_observation_count", 0)),
            matched_session_count=int(event.payload.get("matched_session_count", 0)),
            average_observed_mastery=(
                float(event.payload["average_observed_mastery"])
                if isinstance(event.payload.get("average_observed_mastery"), (int, float))
                else None
            ),
            low_support_success_rate=float(event.payload.get("low_support_success_rate", 0.0)),
            high_support_dependency_rate=float(event.payload.get("high_support_dependency_rate", 0.0)),
            rationale=(
                str(event.payload.get("ordinary_mastery_profile_rationale"))
                if event.payload.get("ordinary_mastery_profile_rationale") is not None
                else None
            ),
            updated_at=event.created_at,
        )

    def _targets_overlap(
        self,
        *,
        target_kc_ids: list[str],
        observed_kc_ids: list[str],
        target_lo_ids: list[str],
        observed_lo_ids: list[str],
    ) -> bool:
        return bool(set(target_kc_ids).intersection(observed_kc_ids) or set(target_lo_ids).intersection(observed_lo_ids))

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None]
