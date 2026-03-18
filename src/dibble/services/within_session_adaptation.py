from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from dibble.models.generation import GenerationRequest
from dibble.models.session_adaptation import WithinSessionControllerState
from dibble.services.protocols import AuditStore, WithinSessionControllerStore
from dibble.services.workflow_rationale import decision_grade_rationale


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
    phase: str = "monitor"
    recovery_intent: str = "monitor"
    support_step_budget: int = 0
    support_steps_remaining: int = 0
    stuck_loop_risk: str = "low"
    arc_action: str = "steady"
    generated_step_count: int = 0
    positive_streak: int = 0
    negative_streak: int = 0
    current_evidence_signal: str = "steady"
    current_evidence_confidence: float = 0.0
    current_evidence_rationale: str | None = None
    latest_assessment_prompt_style: str | None = None
    latest_assessment_next_action: str = "monitor"
    latest_assessment_evidence_strength: str = "insufficient"
    socratic_steering_action: str = "steady"
    rationale: str | None = None


@dataclass(slots=True)
class WithinSessionAdaptationService:
    audit_store: AuditStore
    controller_store: WithinSessionControllerStore | None = None
    max_events: int = 500
    recency_window_hours: int = 6

    def adaptation_for(self, *, student_id: UUID, request: GenerationRequest) -> WithinSessionAdaptationSummary:
        if request.learning_session_id is None:
            return WithinSessionAdaptationSummary()
        controller = self._controller_for(student_id=student_id, request=request)
        if controller is not None:
            return self._summary_from_controller(controller)

        return self._raw_adaptation_for(student_id=student_id, request=request)

    def record_observation_event(self, *, student_id: UUID, event_payload: dict[str, object]) -> WithinSessionAdaptationSummary:
        request = self._request_from_payload(student_id=student_id, payload=event_payload, default_intent="practice")
        if request is None:
            return WithinSessionAdaptationSummary()
        raw_summary = self._raw_adaptation_for(student_id=student_id, request=request)
        controller = self._transition_controller(
            request=request,
            raw_summary=raw_summary,
            event_type="learner.observe",
        )
        return self._summary_from_controller(controller)

    def record_assessment_event(self, *, student_id: UUID, event_payload: dict[str, object]) -> WithinSessionAdaptationSummary:
        request = self._request_from_payload(student_id=student_id, payload=event_payload, default_intent="assessment")
        if request is None:
            return WithinSessionAdaptationSummary()
        raw_summary = self._raw_adaptation_for(student_id=student_id, request=request)
        controller = self._transition_controller(
            request=request,
            raw_summary=raw_summary,
            event_type="assessment.socratic",
        )
        return self._summary_from_controller(controller)

    def record_generation_step(
        self,
        *,
        request: GenerationRequest,
        content_type: str,
        generation_id: str,
    ) -> WithinSessionAdaptationSummary:
        if request.learning_session_id is None or self.controller_store is None:
            return self.adaptation_for(student_id=request.student_id, request=request)
        existing = self.controller_store.get(request.learning_session_id)
        if existing is None:
            raw_summary = self._raw_adaptation_for(student_id=request.student_id, request=request)
            existing = self._build_controller_state(
                request=request,
                raw_summary=raw_summary,
                phase=self._phase_for(raw_summary=raw_summary, existing=None),
                recovery_intent=self._recovery_intent_for(raw_summary=raw_summary, existing=None),
                positive_streak=1 if raw_summary.signal == "positive" else 0,
                negative_streak=1 if raw_summary.signal == "negative" else 0,
                mixed_streak=1 if raw_summary.signal == "mixed" else 0,
                generation_count=0,
            )
        updated = existing.model_copy(
            update={
                "generation_count": existing.generation_count + 1,
                "support_steps_remaining": self._remaining_steps_after_generation(existing),
                "stuck_loop_risk": self._stuck_loop_risk_for(
                    phase=existing.phase,
                    support_steps_remaining=self._remaining_steps_after_generation(existing),
                    raw_summary=self._summary_from_controller(existing),
                    generation_count=existing.generation_count + 1,
                    negative_streak=existing.negative_streak,
                    phase_changed=False,
                ),
                "arc_action": self._arc_action_for(
                    phase=existing.phase,
                    raw_summary=self._summary_from_controller(existing),
                    stuck_loop_risk=self._stuck_loop_risk_for(
                        phase=existing.phase,
                        support_steps_remaining=self._remaining_steps_after_generation(existing),
                        raw_summary=self._summary_from_controller(existing),
                        generation_count=existing.generation_count + 1,
                        negative_streak=existing.negative_streak,
                        phase_changed=False,
                    ),
                ),
                "last_generated_content_type": content_type,
                "last_generation_id": generation_id,
                "rationale": self._generation_step_rationale(
                    learning_session_id=request.learning_session_id,
                    existing=existing,
                    support_steps_remaining=self._remaining_steps_after_generation(existing),
                    generation_count=existing.generation_count + 1,
                ),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self.controller_store.upsert(updated)
        return self._summary_from_controller(updated)

    def _raw_adaptation_for(self, *, student_id: UUID, request: GenerationRequest) -> WithinSessionAdaptationSummary:
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
        latest_assessment_payload = latest_assessment.payload if latest_assessment is not None else None
        latest_assessment_prompt_style = (
            str(latest_assessment_payload.get("prompt_style"))
            if latest_assessment_payload is not None and latest_assessment_payload.get("prompt_style") is not None
            else None
        )
        latest_assessment_next_action = (
            str(latest_assessment_payload.get("next_action", "monitor"))
            if latest_assessment_payload is not None
            else "monitor"
        )
        latest_assessment_evidence_strength = (
            str(latest_assessment_payload.get("evidence_strength", "insufficient"))
            if latest_assessment_payload is not None
            else "insufficient"
        )
        socratic_steering_action = self._socratic_steering_action(latest_assessment_payload)

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
        strong_assessment_recovery = self._strong_assessment_recovery(latest_assessment.payload if latest_assessment is not None else None)
        current_evidence_signal, current_evidence_confidence, current_evidence_rationale = self._current_evidence_summary(
            observation_events
        )

        if negative_score >= 0.55 and net <= -0.1:
            if strong_assessment_recovery and positive_score >= 0.72:
                return WithinSessionAdaptationSummary(
                    signal="positive",
                    source="session_events",
                    confidence=confidence,
                    support_bias=1,
                    sequence_action="attempt_transfer",
                    primary_kc_id=primary_kc_id,
                    matched_observation_count=len(observation_events),
                    matched_assessment_count=len(assessment_events),
                    phase="transfer_check",
                    recovery_intent="fade_support",
                    current_evidence_signal=current_evidence_signal,
                    current_evidence_confidence=current_evidence_confidence,
                    current_evidence_rationale=current_evidence_rationale,
                    latest_assessment_prompt_style=latest_assessment_prompt_style,
                    latest_assessment_next_action=latest_assessment_next_action,
                    latest_assessment_evidence_strength=latest_assessment_evidence_strength,
                    socratic_steering_action=socratic_steering_action,
                    rationale=self._positive_rationale(
                        latest_assessment=latest_assessment_payload,
                        observation_count=len(observation_events),
                        assessment_count=len(assessment_events),
                        session_id=request.learning_session_id,
                    ),
                )
            return WithinSessionAdaptationSummary(
                signal="negative",
                source="session_events",
                confidence=confidence,
                support_bias=-1,
                sequence_action="hold_target",
                primary_kc_id=primary_kc_id,
                matched_observation_count=len(observation_events),
                matched_assessment_count=len(assessment_events),
                phase="stabilize",
                recovery_intent="stabilize_support",
                current_evidence_signal=current_evidence_signal,
                current_evidence_confidence=current_evidence_confidence,
                current_evidence_rationale=current_evidence_rationale,
                latest_assessment_prompt_style=latest_assessment_prompt_style,
                latest_assessment_next_action=latest_assessment_next_action,
                latest_assessment_evidence_strength=latest_assessment_evidence_strength,
                socratic_steering_action=socratic_steering_action,
                rationale=self._negative_rationale(
                    latest_assessment=latest_assessment_payload,
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
                phase="transfer_check",
                recovery_intent="fade_support",
                current_evidence_signal=current_evidence_signal,
                current_evidence_confidence=current_evidence_confidence,
                current_evidence_rationale=current_evidence_rationale,
                latest_assessment_prompt_style=latest_assessment_prompt_style,
                latest_assessment_next_action=latest_assessment_next_action,
                latest_assessment_evidence_strength=latest_assessment_evidence_strength,
                socratic_steering_action=socratic_steering_action,
                rationale=self._positive_rationale(
                    latest_assessment=latest_assessment_payload,
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
            phase="monitor",
            recovery_intent="monitor",
            current_evidence_signal=current_evidence_signal,
            current_evidence_confidence=current_evidence_confidence,
            current_evidence_rationale=current_evidence_rationale,
            latest_assessment_prompt_style=latest_assessment_prompt_style,
            latest_assessment_next_action=latest_assessment_next_action,
            latest_assessment_evidence_strength=latest_assessment_evidence_strength,
            socratic_steering_action=socratic_steering_action,
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

    def _request_from_payload(
        self,
        *,
        student_id: UUID,
        payload: dict[str, object],
        default_intent: str,
    ) -> GenerationRequest | None:
        learning_session_id = payload.get("learning_session_id")
        if learning_session_id is None:
            return None
        target_kc_ids = [str(item) for item in payload.get("target_kc_ids", [])] if isinstance(payload.get("target_kc_ids"), list) else []
        target_lo_ids = [str(item) for item in payload.get("target_lo_ids", [])] if isinstance(payload.get("target_lo_ids"), list) else []
        return GenerationRequest(
            student_id=student_id,
            learning_session_id=str(learning_session_id),
            target_kc_ids=target_kc_ids,
            target_lo_ids=target_lo_ids,
            intent=str(payload.get("intent", default_intent)),
        )

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
        current_evidence_signal = str(payload.get("current_evidence_signal", "steady"))
        current_evidence_confidence = float(payload.get("current_evidence_confidence", 0.0))

        negative = 0.0
        positive = 0.0

        negative += 0.26 if errors >= 2 else 0.12 if errors == 1 else 0.0
        negative += 0.22 if hints >= 2 else 0.08 if hints == 1 else 0.0
        negative += 0.24 if load >= 0.75 else 0.12 if load >= 0.6 else 0.0
        negative += {"high": 0.24, "medium": 0.12}.get(frustration, 0.0)
        negative += {"high": 0.14, "medium": 0.07}.get(help_seeking, 0.0)
        negative += 0.14 if confidence_calibration <= 0.35 else 0.07 if confidence_calibration <= 0.5 else 0.0
        if current_evidence_signal == "overload":
            negative += 0.24 * current_evidence_confidence
        elif current_evidence_signal == "disengagement":
            negative += 0.22 * current_evidence_confidence
        elif current_evidence_signal == "support_dependence":
            negative += 0.18 * current_evidence_confidence
        if support_level == "low" and negative >= 0.4:
            negative += 0.08

        positive += 0.16 if errors == 0 else 0.0
        positive += 0.12 if hints == 0 else 0.05 if hints == 1 else 0.0
        positive += 0.18 if load <= 0.4 else 0.08 if load <= 0.55 else 0.0
        positive += 0.16 if frustration in {"none", "low"} else 0.0
        positive += 0.08 if help_seeking in {"none", "low"} else 0.0
        positive += 0.14 if confidence_calibration >= 0.7 else 0.08 if confidence_calibration >= 0.6 else 0.0
        if current_evidence_signal == "productive_struggle":
            positive += 0.2 * current_evidence_confidence
            negative = max(0.0, negative - (0.1 * current_evidence_confidence))
        return round(negative, 2), round(positive, 2)

    def _strong_assessment_recovery(self, latest_assessment: dict[str, object] | None) -> bool:
        if latest_assessment is None:
            return False
        evidence_strength = str(latest_assessment.get("evidence_strength", "insufficient"))
        evidence_score = float(latest_assessment.get("evidence_score", 0.0))
        next_action = str(latest_assessment.get("next_action", "ask_probe"))
        return (
            evidence_strength == "demonstrated"
            and evidence_score >= 0.85
            and next_action == "advance"
        )

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
            return decision_grade_rationale(
                (
                    f"Recent same-session evidence in {session_id} still points to step-back reasoning, "
                    "so support should stay high on the current target before any transfer."
                ),
                action="hold_target",
                target_stage="repair",
            )
        return decision_grade_rationale(
            (
                f"Recent same-session observations and assessments in {session_id} show active struggle "
                f"({observation_count} observations, {assessment_count} assessments), so support should increase "
                "and the next step should stay on the current target."
            ),
            action="hold_target",
            target_stage="target",
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
            return decision_grade_rationale(
                f"Recent same-session evidence in {session_id} demonstrates enough understanding to test transfer on the target next.",
                action="attempt_transfer",
                target_stage="transfer",
            )
        return decision_grade_rationale(
            (
                f"Recent same-session observations and assessments in {session_id} stayed strong "
                f"({observation_count} observations, {assessment_count} assessments), so support can fade "
                "and the next step can test transfer."
            ),
            action="attempt_transfer",
            target_stage="transfer",
        )

    def _overlap_score(self, left: list[str], right: object) -> float:
        left_values = {str(item) for item in left}
        right_values = {str(item) for item in right} if isinstance(right, list) else set()
        if not left_values or not right_values:
            return 0.0
        return len(left_values & right_values) / max(len(left_values), len(right_values))

    def _controller_for(self, *, student_id: UUID, request: GenerationRequest) -> WithinSessionControllerState | None:
        if self.controller_store is None or request.learning_session_id is None:
            return None
        controller = self.controller_store.get(request.learning_session_id)
        if controller is None or str(controller.student_id) != str(student_id):
            return None
        if request.target_kc_ids and self._overlap_score(request.target_kc_ids, controller.target_kc_ids) <= 0.0:
            return None
        if request.target_lo_ids and self._overlap_score(request.target_lo_ids, controller.target_lo_ids) <= 0.0:
            return None
        return controller

    def _summary_from_controller(self, controller: WithinSessionControllerState) -> WithinSessionAdaptationSummary:
        return WithinSessionAdaptationSummary(
            signal=controller.signal,
            source=controller.source,
            confidence=controller.confidence,
            support_bias=controller.support_bias,
            sequence_action=controller.sequence_action,
            primary_kc_id=controller.primary_kc_id,
            matched_observation_count=controller.observation_count,
            matched_assessment_count=controller.assessment_count,
            phase=controller.phase,
            recovery_intent=controller.recovery_intent,
            support_step_budget=controller.support_step_budget,
            support_steps_remaining=controller.support_steps_remaining,
            stuck_loop_risk=controller.stuck_loop_risk,
            arc_action=controller.arc_action,
            generated_step_count=controller.generation_count,
            positive_streak=controller.positive_streak,
            negative_streak=controller.negative_streak,
            current_evidence_signal=controller.current_evidence_signal,
            current_evidence_confidence=controller.current_evidence_confidence,
            current_evidence_rationale=controller.current_evidence_rationale,
            latest_assessment_prompt_style=controller.latest_assessment_prompt_style,
            latest_assessment_next_action=controller.latest_assessment_next_action,
            latest_assessment_evidence_strength=controller.latest_assessment_evidence_strength,
            socratic_steering_action=controller.socratic_steering_action,
            rationale=controller.rationale,
        )

    def _transition_controller(
        self,
        *,
        request: GenerationRequest,
        raw_summary: WithinSessionAdaptationSummary,
        event_type: str,
    ) -> WithinSessionControllerState:
        if self.controller_store is None or request.learning_session_id is None:
            return self._build_controller_state(
                request=request,
                raw_summary=raw_summary,
                phase=self._phase_for(raw_summary=raw_summary, existing=None),
                recovery_intent=self._recovery_intent_for(raw_summary=raw_summary, existing=None),
                positive_streak=1 if raw_summary.signal == "positive" else 0,
                negative_streak=1 if raw_summary.signal == "negative" else 0,
                mixed_streak=1 if raw_summary.signal == "mixed" else 0,
                generation_count=0,
            )
        existing = self.controller_store.get(request.learning_session_id)
        positive_streak = self._updated_streak(existing.positive_streak if existing is not None else 0, raw_summary.signal == "positive")
        negative_streak = self._updated_streak(existing.negative_streak if existing is not None else 0, raw_summary.signal == "negative")
        mixed_streak = self._updated_streak(existing.mixed_streak if existing is not None else 0, raw_summary.signal == "mixed")
        phase = self._phase_for(raw_summary=raw_summary, existing=existing)
        recovery_intent = self._recovery_intent_for(raw_summary=raw_summary, existing=existing)
        phase_changed = existing is None or existing.phase != phase
        support_step_budget = self._support_step_budget_for(phase=phase, raw_summary=raw_summary)
        support_steps_remaining = self._support_steps_remaining_for(
            phase=phase,
            existing=existing,
            raw_summary=raw_summary,
            support_step_budget=support_step_budget,
            phase_changed=phase_changed,
        )
        stuck_loop_risk = self._stuck_loop_risk_for(
            phase=phase,
            support_steps_remaining=support_steps_remaining,
            raw_summary=raw_summary,
            generation_count=existing.generation_count if existing is not None else 0,
            negative_streak=negative_streak,
            phase_changed=phase_changed,
        )
        arc_action = self._arc_action_for(
            phase=phase,
            raw_summary=raw_summary,
            stuck_loop_risk=stuck_loop_risk,
        )
        signal, support_bias, sequence_action = self._controller_signal(
            raw_summary=raw_summary,
            existing=existing,
            phase=phase,
            positive_streak=positive_streak,
            negative_streak=negative_streak,
        )
        confidence = self._controller_confidence(
            raw_summary=raw_summary,
            phase=phase,
            positive_streak=positive_streak,
            negative_streak=negative_streak,
            stuck_loop_risk=stuck_loop_risk,
        )
        observation_count = raw_summary.matched_observation_count
        assessment_count = raw_summary.matched_assessment_count
        generation_count = existing.generation_count if existing is not None else 0
        updated = WithinSessionControllerState(
            learning_session_id=request.learning_session_id,
            student_id=request.student_id,
            target_kc_ids=request.target_kc_ids,
            target_lo_ids=request.target_lo_ids,
            signal=signal,
            confidence=confidence,
            support_bias=support_bias,
            sequence_action=sequence_action,
            primary_kc_id=raw_summary.primary_kc_id or (existing.primary_kc_id if existing is not None else None),
            phase=phase,
            recovery_intent=recovery_intent,
            support_step_budget=support_step_budget,
            support_steps_remaining=support_steps_remaining,
            stuck_loop_risk=stuck_loop_risk,
            arc_action=arc_action,
            observation_count=observation_count,
            assessment_count=assessment_count,
            generation_count=generation_count,
            positive_streak=positive_streak,
            negative_streak=negative_streak,
            mixed_streak=mixed_streak,
            current_evidence_signal=raw_summary.current_evidence_signal,
            current_evidence_confidence=raw_summary.current_evidence_confidence,
            current_evidence_rationale=raw_summary.current_evidence_rationale,
            latest_assessment_prompt_style=raw_summary.latest_assessment_prompt_style,
            latest_assessment_next_action=raw_summary.latest_assessment_next_action,
            latest_assessment_evidence_strength=raw_summary.latest_assessment_evidence_strength,
            socratic_steering_action=raw_summary.socratic_steering_action,
            last_generated_content_type=existing.last_generated_content_type if existing is not None else None,
            last_generation_id=existing.last_generation_id if existing is not None else None,
            rationale=self._controller_rationale(
                learning_session_id=request.learning_session_id,
                phase=phase,
                recovery_intent=recovery_intent,
                raw_summary=raw_summary,
                positive_streak=positive_streak,
                negative_streak=negative_streak,
                stuck_loop_risk=stuck_loop_risk,
                arc_action=arc_action,
                event_type=event_type,
            ),
            created_at=existing.created_at if existing is not None else datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.controller_store.upsert(updated)
        return updated

    def _build_controller_state(
        self,
        *,
        request: GenerationRequest,
        raw_summary: WithinSessionAdaptationSummary,
        phase: str,
        recovery_intent: str,
        positive_streak: int,
        negative_streak: int,
        mixed_streak: int,
        generation_count: int,
    ) -> WithinSessionControllerState:
        signal, support_bias, sequence_action = self._controller_signal(
            raw_summary=raw_summary,
            existing=None,
            phase=phase,
            positive_streak=positive_streak,
            negative_streak=negative_streak,
        )
        support_step_budget = self._support_step_budget_for(phase=phase, raw_summary=raw_summary)
        support_steps_remaining = self._support_steps_remaining_for(
            phase=phase,
            existing=None,
            raw_summary=raw_summary,
            support_step_budget=support_step_budget,
            phase_changed=True,
        )
        stuck_loop_risk = self._stuck_loop_risk_for(
            phase=phase,
            support_steps_remaining=support_steps_remaining,
            raw_summary=raw_summary,
            generation_count=generation_count,
            negative_streak=negative_streak,
            phase_changed=True,
        )
        arc_action = self._arc_action_for(
            phase=phase,
            raw_summary=raw_summary,
            stuck_loop_risk=stuck_loop_risk,
        )
        return WithinSessionControllerState(
            learning_session_id=request.learning_session_id or "",
            student_id=request.student_id,
            target_kc_ids=request.target_kc_ids,
            target_lo_ids=request.target_lo_ids,
            signal=signal,
            confidence=self._controller_confidence(
                raw_summary=raw_summary,
                phase=phase,
                positive_streak=positive_streak,
                negative_streak=negative_streak,
                stuck_loop_risk=stuck_loop_risk,
            ),
            support_bias=support_bias,
            sequence_action=sequence_action,
            primary_kc_id=raw_summary.primary_kc_id,
            phase=phase,
            recovery_intent=recovery_intent,
            support_step_budget=support_step_budget,
            support_steps_remaining=support_steps_remaining,
            stuck_loop_risk=stuck_loop_risk,
            arc_action=arc_action,
            observation_count=raw_summary.matched_observation_count,
            assessment_count=raw_summary.matched_assessment_count,
            generation_count=generation_count,
            positive_streak=positive_streak,
            negative_streak=negative_streak,
            mixed_streak=mixed_streak,
            current_evidence_signal=raw_summary.current_evidence_signal,
            current_evidence_confidence=raw_summary.current_evidence_confidence,
            current_evidence_rationale=raw_summary.current_evidence_rationale,
            latest_assessment_prompt_style=raw_summary.latest_assessment_prompt_style,
            latest_assessment_next_action=raw_summary.latest_assessment_next_action,
            latest_assessment_evidence_strength=raw_summary.latest_assessment_evidence_strength,
            socratic_steering_action=raw_summary.socratic_steering_action,
            rationale=raw_summary.rationale,
        )

    def _current_evidence_summary(self, observation_events) -> tuple[str, float, str | None]:
        if not observation_events:
            return "steady", 0.0, None
        ranked: dict[str, float] = {}
        rationale: str | None = None
        for event in observation_events:
            signal = str(event.payload.get("current_evidence_signal", "steady"))
            confidence = float(event.payload.get("current_evidence_confidence", 0.0))
            if signal == "steady" or confidence <= 0.0:
                continue
            ranked[signal] = ranked.get(signal, 0.0) + confidence
            if rationale is None:
                rationale = event.payload.get("current_evidence_rationale")
        if not ranked:
            return "steady", 0.0, None
        signal, weight = max(ranked.items(), key=lambda item: item[1])
        confidence = round(min(0.92, weight / max(1, len(observation_events))), 2)
        return signal, confidence, rationale

    def _socratic_steering_action(self, latest_assessment: dict[str, object] | None) -> str:
        if latest_assessment is None:
            return "steady"
        explicit_action = latest_assessment.get("steering_action")
        if explicit_action is not None:
            return str(explicit_action)
        next_action = str(latest_assessment.get("next_action", "monitor"))
        prompt_style = str(latest_assessment.get("prompt_style", ""))
        evidence_strength = str(latest_assessment.get("evidence_strength", "insufficient"))
        if next_action == "step_back" or prompt_style == "scaffolded_step_back":
            return "repair_then_model"
        if next_action == "clarify" or prompt_style == "clarification":
            return "clarify_then_check"
        if next_action == "advance" or prompt_style == "transfer_check":
            return "verify_transfer" if evidence_strength == "demonstrated" else "clarify_then_check"
        if prompt_style == "diagnostic":
            return "probe_from_new_angle"
        return "steady"

    def _updated_streak(self, current: int, is_same_signal: bool) -> int:
        return current + 1 if is_same_signal else 0

    def _tracks_support_budget(self, phase: str) -> bool:
        return phase in {"stabilize", "repair", "consolidate", "bridge"}

    def _support_step_budget_for(self, *, phase: str, raw_summary: WithinSessionAdaptationSummary) -> int:
        base_budget = {
            "stabilize": 1,
            "repair": 2,
            "consolidate": 1,
            "bridge": 1,
        }.get(phase, 0)
        if phase in {"stabilize", "repair"} and raw_summary.latest_assessment_next_action == "step_back":
            return base_budget + 1
        return base_budget

    def _support_steps_remaining_for(
        self,
        *,
        phase: str,
        existing: WithinSessionControllerState | None,
        raw_summary: WithinSessionAdaptationSummary,
        support_step_budget: int,
        phase_changed: bool,
    ) -> int:
        if not self._tracks_support_budget(phase):
            return 0
        if existing is None or phase_changed:
            return support_step_budget
        if raw_summary.signal == "positive" and phase in {"consolidate", "bridge"} and existing.signal in {"negative", "mixed", "recovering"}:
            return support_step_budget
        return min(support_step_budget, existing.support_steps_remaining)

    def _remaining_steps_after_generation(self, controller: WithinSessionControllerState) -> int:
        if not self._tracks_support_budget(controller.phase):
            return 0
        return max(0, controller.support_steps_remaining - 1)

    def _stuck_loop_risk_for(
        self,
        *,
        phase: str,
        support_steps_remaining: int,
        raw_summary: WithinSessionAdaptationSummary,
        generation_count: int,
        negative_streak: int,
        phase_changed: bool,
    ) -> str:
        if not self._tracks_support_budget(phase):
            return "low"
        if (
            support_steps_remaining <= 0
            and (
                generation_count >= 2
                or raw_summary.signal == "mixed"
                or raw_summary.latest_assessment_next_action in {"clarify", "step_back"}
            )
        ):
            return "high"
        if support_steps_remaining <= 0:
            return "moderate"
        if phase_changed:
            return "low"
        if (
            support_steps_remaining <= 1
            and generation_count >= 1
            and (
                negative_streak >= 2
                or raw_summary.latest_assessment_next_action in {"clarify", "step_back"}
                or raw_summary.socratic_steering_action == "probe_from_new_angle"
            )
        ):
            return "moderate"
        return "low"

    def _arc_action_for(
        self,
        *,
        phase: str,
        raw_summary: WithinSessionAdaptationSummary,
        stuck_loop_risk: str,
    ) -> str:
        if stuck_loop_risk == "high" or raw_summary.socratic_steering_action == "probe_from_new_angle":
            return "reprobe_new_angle"
        if phase in {"stabilize", "repair"}:
            return "model_repair"
        if phase == "consolidate":
            return "restate_then_apply"
        if phase == "bridge":
            return "bridge_with_target"
        if phase == "transfer_check":
            return "attempt_transfer"
        return "steady"

    def _phase_for(
        self,
        *,
        raw_summary: WithinSessionAdaptationSummary,
        existing: WithinSessionControllerState | None,
    ) -> str:
        if raw_summary.signal == "negative":
            if existing is not None and existing.phase in {"bridge", "transfer_check"}:
                return "stabilize"
            if existing is not None and existing.negative_streak >= 1:
                return "repair"
            return "stabilize"
        if raw_summary.signal == "positive":
            if self._current_evidence_blocks_transfer(raw_summary):
                if existing is not None and existing.phase == "bridge":
                    return "bridge"
                if existing is not None and existing.phase == "consolidate":
                    return "bridge"
                return "consolidate"
            if existing is not None and existing.phase in {"stabilize", "repair"}:
                if existing.positive_streak >= 1:
                    return "bridge"
                return "consolidate"
            if existing is not None and existing.phase == "consolidate":
                return "bridge"
            if existing is not None and existing.phase == "bridge":
                return "transfer_check"
            return "transfer_check"
        if existing is not None and existing.phase in {"stabilize", "repair"}:
            return existing.phase
        if existing is not None and existing.phase == "bridge":
            return "bridge"
        if existing is not None and existing.phase == "transfer_check":
            return "consolidate"
        return "monitor"

    def _recovery_intent_for(
        self,
        *,
        raw_summary: WithinSessionAdaptationSummary,
        existing: WithinSessionControllerState | None,
    ) -> str:
        if raw_summary.signal == "negative":
            return "increase_support"
        if raw_summary.signal == "positive":
            if self._current_evidence_blocks_transfer(raw_summary):
                if existing is not None and existing.phase in {"consolidate", "bridge"}:
                    return "bridge_target"
                return "confirm_recovery"
            if existing is not None and existing.phase in {"stabilize", "repair"}:
                return "confirm_recovery"
            if existing is not None and existing.phase == "consolidate":
                return "bridge_target"
            if existing is not None and existing.phase == "bridge":
                return "check_transfer"
            return "check_transfer"
        if existing is not None and existing.phase in {"stabilize", "repair"}:
            return "hold_repair"
        if existing is not None and existing.phase == "consolidate":
            return "hold_recovery"
        if existing is not None and existing.phase == "bridge":
            return "bridge_target"
        return "monitor"

    def _controller_signal(
        self,
        *,
        raw_summary: WithinSessionAdaptationSummary,
        existing: WithinSessionControllerState | None,
        phase: str,
        positive_streak: int,
        negative_streak: int,
    ) -> tuple[str, int, str]:
        if phase in {"stabilize", "repair"}:
            return "negative", -1, "hold_target"
        if phase == "consolidate":
            return "recovering", 0, "hold_target"
        if phase == "bridge":
            return "recovering", 0, "hold_bridge_target"
        if phase == "transfer_check":
            return "positive", 1, "attempt_transfer"
        if raw_summary.signal == "mixed" and negative_streak > 0:
            return "mixed", -1, "hold_target"
        return raw_summary.signal, raw_summary.support_bias, raw_summary.sequence_action

    def _controller_confidence(
        self,
        *,
        raw_summary: WithinSessionAdaptationSummary,
        phase: str,
        positive_streak: int,
        negative_streak: int,
        stuck_loop_risk: str,
    ) -> float:
        streak_bonus = min(0.14, ((positive_streak + negative_streak) * 0.04))
        phase_bonus = 0.04 if phase in {"repair", "consolidate", "bridge", "transfer_check"} else 0.0
        loop_penalty = 0.08 if stuck_loop_risk == "high" else 0.04 if stuck_loop_risk == "moderate" else 0.0
        return round(max(0.0, min(0.95, raw_summary.confidence + streak_bonus + phase_bonus - loop_penalty)), 2)

    def _controller_rationale(
        self,
        *,
        learning_session_id: str,
        phase: str,
        recovery_intent: str,
        raw_summary: WithinSessionAdaptationSummary,
        positive_streak: int,
        negative_streak: int,
        stuck_loop_risk: str,
        arc_action: str,
        event_type: str,
    ) -> str:
        posture_action = (
            "attempt_transfer"
            if phase == "transfer_check"
            else "hold_bridge_target"
            if phase == "bridge"
            else "hold_target"
        )
        posture_stage = (
            "transfer"
            if phase == "transfer_check"
            else "bridge"
            if phase == "bridge"
            else "target"
        )
        if raw_summary.signal == "positive" and self._current_evidence_blocks_transfer(raw_summary):
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} has some recovery evidence, "
                "but live signals still look support-dependent or overloaded, so it is holding before transfer."
                ,
                action="hold_bridge_target" if phase == "bridge" else "hold_target",
                target_stage="bridge" if phase == "bridge" else "target",
            )
        if stuck_loop_risk == "high":
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} has exhausted its guided support budget during {phase}, "
                f"so after {event_type} it is changing angle instead of repeating the same scaffold."
                ,
                action=posture_action,
                target_stage=posture_stage,
            )
        if phase == "repair":
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} has seen {negative_streak} consecutive struggle signals, "
                f"so it is staying in repair mode after {event_type}."
                ,
                action="hold_target",
                target_stage="repair",
            )
        if phase == "stabilize":
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} is stabilizing support after fresh same-session struggle."
                ,
                action="hold_target",
                target_stage="repair",
            )
        if phase == "consolidate":
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} has seen recovery evidence after earlier struggle, "
                "so it is holding the target while confidence consolidates."
                ,
                action="hold_target",
                target_stage="target",
            )
        if phase == "bridge":
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} has seen repeated recovery evidence, "
                "so it is bridging through one more guided target step before transfer."
                ,
                action="hold_bridge_target",
                target_stage="bridge",
            )
        if phase == "transfer_check":
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} has seen {positive_streak} consecutive strong signals, "
                "so the next generated step can test transfer."
                ,
                action="attempt_transfer",
                target_stage="transfer",
            )
        if arc_action == "reprobe_new_angle":
            return decision_grade_rationale(
                f"Within-session controller for {learning_session_id} is avoiding a support loop by probing the same target from a new angle."
                ,
                action=posture_action,
                target_stage=posture_stage,
            )
        return decision_grade_rationale(
            raw_summary.rationale or (
            f"Within-session controller for {learning_session_id} is monitoring the active recovery intent {recovery_intent}."
            ),
            action=posture_action,
            target_stage=posture_stage,
        )

    def _generation_step_rationale(
        self,
        *,
        learning_session_id: str,
        existing: WithinSessionControllerState,
        support_steps_remaining: int,
        generation_count: int,
    ) -> str:
        if self._tracks_support_budget(existing.phase) and support_steps_remaining <= 0:
            return (
                f"Within-session controller for {learning_session_id} has used {generation_count} generated support steps in {existing.phase}, "
                "so the next move should change representation or check reasoning instead of adding another similar scaffold."
            )
        return (
            f"Within-session controller for {learning_session_id} has delivered {generation_count} generated steps in the current {existing.phase} arc."
        )

    def _current_evidence_blocks_transfer(self, raw_summary: WithinSessionAdaptationSummary) -> bool:
        if raw_summary.current_evidence_signal in {"overload", "support_dependence"}:
            return raw_summary.current_evidence_confidence >= 0.55
        if raw_summary.current_evidence_signal == "disengagement":
            return raw_summary.current_evidence_confidence >= 0.6
        return False
