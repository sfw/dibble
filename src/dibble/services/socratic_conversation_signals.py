from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dibble.models.generation import GenerationRequest
from dibble.models.profile import SocraticConversationSummary
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class SocraticConversationSignalService:
    audit_store: AuditStore
    recency_window_days: int = 30
    max_events: int = 500
    max_matched_turns: int = 12
    minimum_session_count: int = 2
    minimum_turn_count: int = 3
    minimum_confidence: float = 0.55

    def summary_for(self, *, student_id: UUID, request: GenerationRequest) -> SocraticConversationSummary:
        if not request.target_kc_ids and not request.target_lo_ids:
            return SocraticConversationSummary()
        matched_events = self._matched_events(student_id=student_id, request=request)
        if len(matched_events) < self.minimum_turn_count:
            return SocraticConversationSummary()

        session_ids = {
            str(event.payload.get("learning_session_id") or event.payload.get("session_id"))
            for event in matched_events
            if event.payload.get("learning_session_id") or event.payload.get("session_id")
        }
        matched_session_count = len(session_ids)
        if matched_session_count < self.minimum_session_count:
            return SocraticConversationSummary()

        steering_counts = Counter(str(event.payload.get("steering_action", "steady")) for event in matched_events)
        prompt_style_counts = Counter(
            str(event.payload.get("prompt_style")) for event in matched_events if event.payload.get("prompt_style") is not None
        )
        total_turns = len(matched_events)
        repair_rate = round(
            sum(1 for event in matched_events if event.payload.get("steering_action") == "repair_then_model") / total_turns,
            2,
        )
        clarification_rate = round(
            sum(
                1
                for event in matched_events
                if event.payload.get("steering_action") in {"clarify_then_check", "restate_then_apply"}
            )
            / total_turns,
            2,
        )
        transfer_readiness = round(
            sum(
                1
                for event in matched_events
                if event.payload.get("steering_action") in {"verify_transfer", "restate_then_apply"}
                or event.payload.get("evidence_strength") == "demonstrated"
            )
            / total_turns,
            2,
        )
        loop_break_rate = round(
            sum(1 for event in matched_events if event.payload.get("steering_action") == "probe_from_new_angle") / total_turns,
            2,
        )
        confidence = round(
            min(
                0.9,
                0.18
                + (min(total_turns, self.max_matched_turns) * 0.05)
                + (matched_session_count * 0.12)
                + (transfer_readiness * 0.08),
            ),
            2,
        )
        signal = self._signal(
            repair_rate=repair_rate,
            clarification_rate=clarification_rate,
            transfer_readiness=transfer_readiness,
            loop_break_rate=loop_break_rate,
            confidence=confidence,
        )
        if signal == "insufficient":
            return SocraticConversationSummary()

        dominant_prompt_style = prompt_style_counts.most_common(1)[0][0] if prompt_style_counts else None
        dominant_steering_action = steering_counts.most_common(1)[0][0] if steering_counts else "steady"
        return SocraticConversationSummary(
            signal=signal,
            source="socratic_assessment_history",
            confidence=confidence,
            matched_turn_count=total_turns,
            matched_session_count=matched_session_count,
            dominant_steering_action=dominant_steering_action,
            dominant_prompt_style=dominant_prompt_style,
            repair_rate=repair_rate,
            clarification_rate=clarification_rate,
            transfer_readiness=transfer_readiness,
            loop_break_rate=loop_break_rate,
            rationale=self._rationale(
                signal=signal,
                dominant_steering_action=dominant_steering_action,
                matched_session_count=matched_session_count,
            ),
            updated_at=matched_events[0].created_at,
        )

    def _matched_events(self, *, student_id: UUID, request: GenerationRequest):
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, self.recency_window_days))
        events = self.audit_store.list(limit=self.max_events)
        matched = [
            event
            for event in events
            if event.student_id is not None
            and str(event.student_id) == str(student_id)
            and event.event_type == "assessment.socratic"
            and event.created_at >= recent_cutoff
            and self._targets_overlap(
                request=request,
                payload=event.payload,
            )
        ]
        matched.sort(key=lambda event: event.created_at, reverse=True)
        return matched[: self.max_matched_turns]

    def _targets_overlap(self, *, request: GenerationRequest, payload: dict[str, object]) -> bool:
        payload_target_kc_ids = {str(item) for item in payload.get("target_kc_ids", [])} if isinstance(payload.get("target_kc_ids"), list) else set()
        payload_target_lo_ids = {str(item) for item in payload.get("target_lo_ids", [])} if isinstance(payload.get("target_lo_ids"), list) else set()
        if set(request.target_kc_ids).intersection(payload_target_kc_ids):
            return True
        if set(request.target_lo_ids).intersection(payload_target_lo_ids):
            return True
        return False

    def _signal(
        self,
        *,
        repair_rate: float,
        clarification_rate: float,
        transfer_readiness: float,
        loop_break_rate: float,
        confidence: float,
    ) -> str:
        if confidence < self.minimum_confidence:
            return "insufficient"
        if loop_break_rate >= 0.34:
            return "vary_representation"
        if repair_rate >= 0.4 and transfer_readiness < 0.5:
            return "model_then_release"
        if clarification_rate >= 0.45 and transfer_readiness < 0.58:
            return "clarify_then_check"
        if transfer_readiness >= 0.58:
            return "independent_check"
        return "steady"

    def _rationale(self, *, signal: str, dominant_steering_action: str, matched_session_count: int) -> str:
        if signal == "vary_representation":
            return (
                f"Recent Socratic turns across {matched_session_count} sessions needed fresh angles ({dominant_steering_action}), "
                "so the next generated step should vary representation instead of repeating the last wording."
            )
        if signal == "model_then_release":
            return (
                f"Recent Socratic turns across {matched_session_count} sessions still leaned on {dominant_steering_action}, "
                "so the next generated step should model the correction before releasing more independence."
            )
        if signal == "clarify_then_check":
            return (
                f"Recent Socratic turns across {matched_session_count} sessions leaned on clarification, "
                "so the next generated step should tighten the language and quickly re-check understanding."
            )
        if signal == "independent_check":
            return (
                f"Recent Socratic turns across {matched_session_count} sessions repeatedly supported transfer readiness, "
                "so the next generated step can shift toward independent application."
            )
        return (
            f"Recent Socratic turns across {matched_session_count} sessions were informative but not decisive enough to force a different generation posture."
        )
