from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dibble.models.generation import GenerationRequest
from dibble.services.protocols import AuditStore


@dataclass(frozen=True, slots=True)
class WithinSessionAdaptationSummary:
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = 0.0
    support_bias: int = 0
    sequence_action: str = "monitor"
    primary_kc_id: str | None = None
    matched_observation_count: int = 0
    matched_assessment_count: int = 0
    rationale: str | None = None


@dataclass(slots=True)
class WithinSessionAdaptationService:
    audit_store: AuditStore
    max_events: int = 500
    recency_window_hours: int = 6

    def adaptation_for(self, *, student_id: UUID, request: GenerationRequest) -> WithinSessionAdaptationSummary:
        if request.learning_session_id is None:
            return WithinSessionAdaptationSummary()

        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, self.recency_window_hours))
        events = [
            event
            for event in self.audit_store.list(limit=self.max_events)
            if event.student_id is not None
            and str(event.student_id) == str(student_id)
            and event.created_at >= recent_cutoff
            and event.payload.get("learning_session_id") == request.learning_session_id
            and event.event_type in {"learner.observe", "assessment.socratic"}
            and self._matches_request(request=request, payload=event.payload)
        ]
        if not events:
            return WithinSessionAdaptationSummary()

        observation_events = [event for event in events if event.event_type == "learner.observe"]
        assessment_events = [event for event in events if event.event_type == "assessment.socratic"]
        negative_score = 0.0
        positive_score = 0.0
        latest_assessment = assessment_events[0] if assessment_events else None

        for event in observation_events:
            observation_negative, observation_positive = self._observation_scores(event.payload)
            negative_score += observation_negative
            positive_score += observation_positive

        for event in assessment_events:
            assessment_negative, assessment_positive = self._assessment_scores(event.payload)
            negative_score += assessment_negative
            positive_score += assessment_positive

        event_count = len(events)
        net = round(positive_score - negative_score, 2)
        confidence = round(min(0.92, 0.46 + (len(observation_events) * 0.16) + (len(assessment_events) * 0.22)), 2)
        primary_kc_id = self._primary_kc_id(request=request, events=events)

        if negative_score >= 0.55 and net <= -0.1:
            return WithinSessionAdaptationSummary(
                signal="negative",
                source="session_events",
                confidence=confidence,
                support_bias=-1,
                sequence_action="hold_target",
                primary_kc_id=primary_kc_id,
                matched_observation_count=len(observation_events),
                matched_assessment_count=len(assessment_events),
                rationale=self._negative_rationale(
                    latest_assessment=latest_assessment.payload if latest_assessment is not None else None,
                    observation_count=len(observation_events),
                    assessment_count=len(assessment_events),
                    session_id=request.learning_session_id,
                ),
            )
        if positive_score >= 0.55 and net >= 0.1:
            return WithinSessionAdaptationSummary(
                signal="positive",
                source="session_events",
                confidence=confidence,
                support_bias=1,
                sequence_action="attempt_transfer",
                primary_kc_id=primary_kc_id,
                matched_observation_count=len(observation_events),
                matched_assessment_count=len(assessment_events),
                rationale=self._positive_rationale(
                    latest_assessment=latest_assessment.payload if latest_assessment is not None else None,
                    observation_count=len(observation_events),
                    assessment_count=len(assessment_events),
                    session_id=request.learning_session_id,
                ),
            )
        return WithinSessionAdaptationSummary(
            signal="mixed" if event_count > 0 else "insufficient",
            source="session_events" if event_count > 0 else "insufficient",
            confidence=confidence if event_count > 0 else 0.0,
            support_bias=0,
            sequence_action="monitor",
            primary_kc_id=primary_kc_id,
            matched_observation_count=len(observation_events),
            matched_assessment_count=len(assessment_events),
            rationale=(
                f"Recent same-session evidence in {request.learning_session_id} is mixed, so support should stay steady for now."
                if event_count > 0
                else None
            ),
        )

    def _matches_request(self, *, request: GenerationRequest, payload: dict[str, object]) -> bool:
        if request.target_kc_ids and self._overlap_score(request.target_kc_ids, payload.get("target_kc_ids")) > 0.0:
            return True
        if request.target_lo_ids and self._overlap_score(request.target_lo_ids, payload.get("target_lo_ids")) > 0.0:
            return True
        return not request.target_kc_ids and not request.target_lo_ids

    def _primary_kc_id(self, *, request: GenerationRequest, events) -> str | None:
        if request.target_kc_ids:
            return request.target_kc_ids[0]
        for event in events:
            target_kc_ids = event.payload.get("target_kc_ids")
            if isinstance(target_kc_ids, list) and target_kc_ids:
                return str(target_kc_ids[0])
        return None

    def _observation_scores(self, payload: dict[str, object]) -> tuple[float, float]:
        errors = int(payload.get("error_count", 0))
        hints = int(payload.get("hints_used", 0))
        load = float(payload.get("total_load", 0.4))
        confidence_calibration = float(payload.get("confidence_calibration", 0.5))
        frustration = str(payload.get("frustration", "low"))
        help_seeking = str(payload.get("help_seeking", "low"))
        support_level = str(payload.get("support_level", "medium"))

        negative = 0.0
        positive = 0.0

        negative += 0.26 if errors >= 2 else 0.12 if errors == 1 else 0.0
        negative += 0.22 if hints >= 2 else 0.08 if hints == 1 else 0.0
        negative += 0.24 if load >= 0.75 else 0.12 if load >= 0.6 else 0.0
        negative += {"high": 0.24, "medium": 0.12}.get(frustration, 0.0)
        negative += {"high": 0.14, "medium": 0.07}.get(help_seeking, 0.0)
        negative += 0.14 if confidence_calibration <= 0.35 else 0.07 if confidence_calibration <= 0.5 else 0.0
        if support_level == "low" and negative >= 0.4:
            negative += 0.08

        positive += 0.16 if errors == 0 else 0.0
        positive += 0.12 if hints == 0 else 0.05 if hints == 1 else 0.0
        positive += 0.18 if load <= 0.4 else 0.08 if load <= 0.55 else 0.0
        positive += 0.16 if frustration in {"none", "low"} else 0.0
        positive += 0.08 if help_seeking in {"none", "low"} else 0.0
        positive += 0.14 if confidence_calibration >= 0.7 else 0.08 if confidence_calibration >= 0.6 else 0.0
        return round(negative, 2), round(positive, 2)

    def _assessment_scores(self, payload: dict[str, object]) -> tuple[float, float]:
        evidence_strength = str(payload.get("evidence_strength", "insufficient"))
        evidence_score = float(payload.get("evidence_score", 0.0))
        next_action = str(payload.get("next_action", "ask_probe"))

        negative = 0.0
        positive = 0.0
        if evidence_strength == "demonstrated":
            positive += 0.45 + (evidence_score * 0.2)
        elif evidence_strength == "emerging":
            positive += 0.18 + (evidence_score * 0.12)
            negative += 0.08 if next_action in {"clarify", "step_back"} else 0.0
        else:
            negative += 0.34 + (0.14 if evidence_score < 0.3 else 0.06)

        if next_action == "advance":
            positive += 0.15
        elif next_action == "step_back":
            negative += 0.24
        elif next_action == "clarify":
            negative += 0.08
        return round(negative, 2), round(positive, 2)

    def _negative_rationale(
        self,
        *,
        latest_assessment: dict[str, object] | None,
        observation_count: int,
        assessment_count: int,
        session_id: str,
    ) -> str:
        if latest_assessment is not None and latest_assessment.get("next_action") == "step_back":
            return (
                f"Recent same-session evidence in {session_id} still points to step-back reasoning, so support should stay high on the current target before any transfer."
            )
        return (
            f"Recent same-session observations and assessments in {session_id} show active struggle ({observation_count} observations, {assessment_count} assessments), so support should increase and the next step should stay on the current target."
        )

    def _positive_rationale(
        self,
        *,
        latest_assessment: dict[str, object] | None,
        observation_count: int,
        assessment_count: int,
        session_id: str,
    ) -> str:
        if latest_assessment is not None and latest_assessment.get("next_action") == "advance":
            return (
                f"Recent same-session evidence in {session_id} demonstrates enough understanding to test transfer on the target next."
            )
        return (
            f"Recent same-session observations and assessments in {session_id} stayed strong ({observation_count} observations, {assessment_count} assessments), so support can fade and the next step can test transfer."
        )

    def _overlap_score(self, left: list[str], right: object) -> float:
        left_values = {str(item) for item in left}
        right_values = {str(item) for item in right} if isinstance(right, list) else set()
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(len(left_values), len(right_values))
