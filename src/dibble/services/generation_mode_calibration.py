from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import GenerationModeCalibration, GenerationRequest
from dibble.models.profile import LearnerStateProfileSummary, LearnerTraitProfileSummary
from dibble.services.kc_sequence_planner import KcSequencePlanner
from dibble.services.learning_state_profiles import LearnerStateSignalService
from dibble.services.learning_trait_profiles import LearnerTraitProfileSignalService
from dibble.services.learner_strategy_profiles import LearnerStrategySignalService
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.services.within_session_adaptation import WithinSessionAdaptationService


@dataclass(slots=True)
class GenerationModeCalibrator:
    calibration_signal_service: RouterCalibrationSignalService
    strategy_signal_service: LearnerStrategySignalService
    within_session_adaptation_service: WithinSessionAdaptationService
    state_signal_service: LearnerStateSignalService | None = None
    trait_profile_signal_service: LearnerTraitProfileSignalService | None = None
    kc_sequence_planner: KcSequencePlanner = KcSequencePlanner()
    minimum_confidence_for_bias: float = 0.65
    minimum_session_confidence_for_bias: float = 0.55
    minimum_positive_outcome_score: float = 0.78
    minimum_improving_outcome_score: float = 0.7
    maximum_negative_outcome_score: float = 0.45
    maximum_declining_outcome_score: float = 0.72
    minimum_matched_runs_for_positive_bias: int = 2

    def calibrate_request(self, *, request: GenerationRequest) -> GenerationRequest:
        calibration = self.calibration_for(request=request)
        if calibration is None:
            return request
        return request.model_copy(update={"mode_calibration": calibration})

    def calibration_for(self, *, request: GenerationRequest) -> GenerationModeCalibration | None:
        signal = self.calibration_signal_service.signal_for(student_id=request.student_id, request=request)
        strategy = self.strategy_signal_service.strategy_for(student_id=request.student_id, request=request)
        session = self.within_session_adaptation_service.adaptation_for(student_id=request.student_id, request=request)
        state_profile = (
            self.state_signal_service.state_for(student_id=request.student_id, request=request)
            if self.state_signal_service is not None
            else LearnerStateProfileSummary()
        )
        trait_profile = (
            self.trait_profile_signal_service.latest_for_student(student_id=request.student_id)
            if self.trait_profile_signal_service is not None
            else LearnerTraitProfileSummary()
        )
        support_bias = self._support_bias(
            signal=signal,
            strategy=strategy,
            session=session,
            state_profile=state_profile,
            trait_profile=trait_profile,
        )
        if (
            signal.source == "insufficient"
            and strategy.source == "insufficient"
            and session.source == "insufficient"
            and state_profile.source == "insufficient"
            and trait_profile.source == "insufficient"
            and support_bias == 0
        ):
            return None

        source = self._source(
            signal=signal,
            strategy=strategy,
            session=session,
            state_profile=state_profile,
            trait_profile=trait_profile,
            support_bias=support_bias,
        )
        calibration_signal = self._calibration_signal(
            signal=signal,
            strategy=strategy,
            session=session,
            state_profile=state_profile,
            support_bias=support_bias,
        )
        confidence = self._confidence(
            signal=signal,
            strategy=strategy,
            session=session,
            state_profile=state_profile,
            trait_profile=trait_profile,
        )
        average_run_outcome_score = (
            signal.average_run_outcome_score
            if signal.average_run_outcome_score is not None
            else strategy.average_run_outcome_score
        )
        strategy_sequence = self.kc_sequence_planner.plan(
            strategy_summary=strategy,
            target_kc_ids=request.target_kc_ids,
        )
        sequence = self._sequence_for(
            request=request,
            strategy_sequence=strategy_sequence,
            session=session,
        )
        matched_run_count = signal.matched_run_count if signal.source != "insufficient" else strategy.matched_run_count
        progress_signal = signal.progress_signal if signal.source != "insufficient" else strategy.progress_signal
        progress_delta = signal.progress_delta if signal.source != "insufficient" else strategy.progress_delta
        rationale = self._rationale(
            signal=signal,
            strategy=strategy,
            session=session,
            state_profile=state_profile,
            trait_profile=trait_profile,
            support_bias=support_bias,
        )
        return GenerationModeCalibration(
            signal=calibration_signal,
            source=source,
            confidence=confidence,
            matched_run_count=matched_run_count,
            average_run_outcome_score=average_run_outcome_score,
            progress_signal=progress_signal,
            progress_delta=progress_delta,
            support_bias=support_bias,
            strategy_signal=strategy.signal,
            strategy_recovery_focus=strategy.recovery_focus,
            strategy_trajectory_state=strategy.trajectory_state,
            strategy_recommended_next_action=strategy.recommended_next_action,
            strategy_volatility_index=strategy.volatility_index,
            strategy_relapse_risk=strategy.relapse_risk,
            strategy_source=strategy.source,
            strategy_rationale=strategy.rationale,
            state_profile_signal=state_profile.signal,
            state_profile_source=state_profile.source,
            state_profile_confidence=state_profile.confidence,
            state_profile_total_load=state_profile.total_load,
            state_profile_confidence_calibration=state_profile.confidence_calibration,
            state_profile_help_seeking=state_profile.help_seeking.value,
            state_profile_affective_reliability=state_profile.affective_reliability,
            state_profile_load_reliability=state_profile.load_reliability,
            state_profile_recovery_stability=state_profile.recovery_stability,
            state_profile_overload_risk=state_profile.overload_risk,
            state_profile_metacognitive_reliability=state_profile.metacognitive_reliability,
            trait_profile_signal=trait_profile.signal,
            trait_profile_source=trait_profile.source,
            trait_profile_trait_stability=trait_profile.trait_stability,
            trait_profile_challenge_tolerance=trait_profile.challenge_tolerance,
            trait_profile_challenge_evidence_strength=trait_profile.challenge_evidence_strength,
            trait_profile_processing_speed_reliability=trait_profile.processing_speed_reliability,
            trait_profile_working_memory_reliability=trait_profile.working_memory_reliability,
            trait_profile_spatial_reasoning_reliability=trait_profile.spatial_reasoning_reliability,
            strategy_sequence_action=strategy_sequence.action,
            strategy_sequence_primary_kc_id=strategy_sequence.primary_kc_id,
            strategy_sequence_kc_ids=strategy_sequence.ordered_kc_ids,
            strategy_sequence_deferred_kc_ids=strategy_sequence.deferred_kc_ids,
            strategy_sequence_rationale=strategy_sequence.rationale,
            sequence_action=sequence.action,
            sequence_primary_kc_id=sequence.primary_kc_id,
            sequence_kc_ids=sequence.ordered_kc_ids,
            sequence_deferred_kc_ids=sequence.deferred_kc_ids,
            sequence_source=session.source if session.sequence_action != "monitor" else "strategy_profile",
            sequence_rationale=sequence.rationale,
            session_signal=session.signal,
            session_source=session.source,
            session_confidence=session.confidence,
            session_support_bias=session.support_bias,
            session_sequence_action=session.sequence_action,
            session_primary_kc_id=session.primary_kc_id,
            session_observation_count=session.matched_observation_count,
            session_assessment_count=session.matched_assessment_count,
            session_phase=session.phase,
            session_recovery_intent=session.recovery_intent,
            session_support_step_budget=session.support_step_budget,
            session_support_steps_remaining=session.support_steps_remaining,
            session_stuck_loop_risk=session.stuck_loop_risk,
            session_arc_action=session.arc_action,
            session_generated_step_count=session.generated_step_count,
            session_positive_streak=session.positive_streak,
            session_negative_streak=session.negative_streak,
            current_evidence_signal=session.current_evidence_signal,
            current_evidence_confidence=session.current_evidence_confidence,
            current_evidence_rationale=session.current_evidence_rationale,
            session_latest_prompt_style=session.latest_assessment_prompt_style,
            session_latest_next_action=session.latest_assessment_next_action,
            session_latest_evidence_strength=session.latest_assessment_evidence_strength,
            socratic_steering_action=session.socratic_steering_action,
            session_rationale=session.rationale,
            rationale=rationale,
        )

    def _support_bias(self, *, signal, strategy, session, state_profile, trait_profile) -> int:
        current_evidence_bias = self._current_evidence_support_bias(
            session=session,
            state_profile=state_profile,
            trait_profile=trait_profile,
        )
        durable_bias = self._durable_profile_support_bias(
            state_profile=state_profile,
            trait_profile=trait_profile,
        )
        if self._is_decisive_session(session):
            if current_evidence_bias < 0 and session.support_bias >= 0:
                return current_evidence_bias
            return session.support_bias
        if current_evidence_bias != 0:
            return current_evidence_bias
        if signal.confidence < self.minimum_confidence_for_bias:
            return strategy.support_bias if strategy.support_bias != 0 else durable_bias
        calibration_bias = self._calibration_support_bias(signal=signal)
        if calibration_bias != 0:
            return calibration_bias
        return strategy.support_bias if strategy.support_bias != 0 else durable_bias

    def _calibration_support_bias(self, *, signal) -> int:
        if signal.confidence < self.minimum_confidence_for_bias:
            return 0
        if (
            signal.progress_signal == "improving"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score >= self.minimum_improving_outcome_score
            and signal.matched_run_count >= self.minimum_matched_runs_for_positive_bias
        ):
            return 1
        if (
            signal.progress_signal == "declining"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score <= self.maximum_declining_outcome_score
            and signal.matched_run_count >= 2
        ):
            return -1
        if (
            signal.signal == "positive"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score >= self.minimum_positive_outcome_score
            and signal.matched_run_count >= self.minimum_matched_runs_for_positive_bias
        ):
            return 1
        if (
            signal.signal == "negative"
            and signal.average_run_outcome_score is not None
            and signal.average_run_outcome_score <= self.maximum_negative_outcome_score
            and signal.matched_run_count >= 1
        ):
            return -1
        return 0

    def _calibration_signal(self, *, signal, strategy, session, state_profile, support_bias: int) -> str:
        if self._is_decisive_session(session):
            return session.signal
        if signal.source != "insufficient":
            return signal.signal
        if state_profile.source != "insufficient" and state_profile.signal != "insufficient":
            if state_profile.signal == "independence_ready":
                return "positive"
            if state_profile.signal == "support_needed":
                return "negative"
        if support_bias > 0:
            return "positive"
        if support_bias < 0:
            return "negative"
        if strategy.signal != "insufficient":
            return "mixed"
        return "insufficient"

    def _source(self, *, signal, strategy, session, state_profile, trait_profile, support_bias: int) -> str:
        if self._is_decisive_session(session):
            return session.source
        if signal.source != "insufficient":
            return signal.source
        if strategy.source != "insufficient":
            return strategy.source
        if support_bias != 0 and state_profile.source != "insufficient":
            return state_profile.source
        if support_bias != 0 and trait_profile.source != "insufficient":
            return trait_profile.source
        if state_profile.source != "insufficient":
            return state_profile.source
        if trait_profile.source != "insufficient":
            return trait_profile.source
        return strategy.source

    def _confidence(self, *, signal, strategy, session, state_profile, trait_profile) -> float:
        if self._is_decisive_session(session):
            return session.confidence
        if signal.source != "insufficient":
            return signal.confidence
        if strategy.source != "insufficient":
            return strategy.confidence
        if state_profile.source != "insufficient":
            return state_profile.confidence
        if trait_profile.source != "insufficient":
            return self._trait_profile_confidence(trait_profile=trait_profile)
        return 0.0

    def _sequence_for(self, *, request, strategy_sequence, session):
        if session.sequence_action == "monitor":
            return strategy_sequence
        ordered_kc_ids = request.target_kc_ids or strategy_sequence.ordered_kc_ids
        return strategy_sequence.model_copy(
            update={
                "action": session.sequence_action,
                "primary_kc_id": session.primary_kc_id or strategy_sequence.primary_kc_id,
                "ordered_kc_ids": ordered_kc_ids,
                "deferred_kc_ids": [],
                "rationale": session.rationale or strategy_sequence.rationale,
            }
        )

    def _rationale(self, *, signal, strategy, session, state_profile, trait_profile, support_bias: int) -> str:
        if self._is_decisive_session(session):
            if session.arc_action == "reprobe_new_angle":
                return (
                    "Recent same-session support has started to loop, so the next generated step should change representation or reasoning frame instead of adding another similar scaffold."
                )
            if session.arc_action == "bridge_with_target":
                return (
                    "Recent same-session recovery looks stable enough for one guided target application before a full transfer check."
                )
            if session.arc_action == "restate_then_apply":
                return (
                    "Recent same-session recovery is consolidating, so the next generated step should ask for a brief restatement and one guided application."
                )
            if session.socratic_steering_action == "repair_then_model":
                return (
                    "Recent Socratic turns still point to prerequisite repair, so the next generated step should model the correction before expecting freer explanation."
                )
            if session.socratic_steering_action == "restate_then_apply":
                return (
                    "Recent Socratic turns show the learner has repaired the idea but still needs to restate it clearly and apply it once before a freer transfer move."
                )
            if session.socratic_steering_action == "clarify_then_check":
                return (
                    "Recent Socratic turns exposed a narrow reasoning gap, so the next generated step should clarify that language and quickly check the learner's explanation."
                )
            if session.socratic_steering_action == "verify_transfer":
                return (
                    "Recent Socratic turns demonstrated understanding, so the next generated step should shift from explanation toward independent transfer."
                )
            return session.rationale or (
                "Recent same-session evidence was strong enough to update support before relying on cross-session history."
            )
        if support_bias > 0 and signal.progress_signal == "improving":
            return (
                "Recent matching runs have been improving across sessions, so the generation mode can allow slightly more independence."
            )
        if support_bias < 0 and signal.progress_signal == "declining":
            return (
                "Recent matching runs have been declining across sessions, so the generation mode should add one step of modeled support."
            )
        if support_bias > 0:
            return (
                "Recent matching runs stayed durably positive, so the generation mode can allow slightly more independence."
            )
        if support_bias < 0:
            return (
                "Recent matching runs trended negative, so the generation mode should add one step of modeled support."
            )
        if strategy.signal == "independence_ready":
            return strategy.rationale or (
                "Long-horizon learner strategy shows the learner is ready for slightly more independent practice."
            )
        if strategy.signal == "support_intensive":
            return strategy.rationale or (
                "Long-horizon learner strategy shows the learner still needs one more step of modeled support."
            )
        if strategy.signal == "stabilizing":
            return strategy.rationale or (
                "Long-horizon learner strategy suggests staying with guided practice while recent gains stabilize."
            )
        if strategy.trajectory_state == "plateaued":
            return strategy.rationale or (
                "Long-horizon learner strategy shows the learner has plateaued, so the next step should vary support instead of repeating the same independence level."
            )
        if strategy.trajectory_state == "volatile":
            return strategy.rationale or (
                "Long-horizon learner strategy shows uneven outcomes, so the next step should stabilize support before pushing ahead."
            )
        if strategy.trajectory_state == "relapsing":
            return strategy.rationale or (
                "Long-horizon learner strategy shows relapse across sessions, so the next step should rebuild prerequisite support."
            )
        if (
            state_profile.source != "insufficient"
            and support_bias < 0
            and state_profile.load_reliability >= 0.58
            and state_profile.overload_risk >= 0.64
        ):
            return (
                "Durable learner-state evidence still shows reliable overload risk, so the next generation step should keep support explicit instead of fading too quickly."
            )
        if (
            state_profile.source != "insufficient"
            and support_bias > 0
            and state_profile.recovery_stability >= 0.68
            and state_profile.metacognitive_reliability >= 0.58
        ):
            return (
                "Durable learner-state evidence shows stable recovery, so the next generation step can release one more move to the learner without overcommitting."
            )
        if (
            trait_profile.source != "insufficient"
            and support_bias < 0
            and trait_profile.working_memory_reliability >= 0.68
            and trait_profile.challenge_tolerance < 0.48
        ):
            return (
                "Durable cognitive-trait evidence suggests challenge tolerance is still fragile, so the next step should keep the comparison space tight and the learner release small."
            )
        if (
            trait_profile.source != "insufficient"
            and support_bias > 0
            and trait_profile.trait_stability >= 0.72
            and trait_profile.challenge_tolerance >= 0.66
        ):
            return (
                "Durable cognitive-trait evidence suggests the learner can handle a lighter release, so the next step can shift toward transfer with minimal cueing."
            )
        if session.current_evidence_signal == "productive_struggle" and session.current_evidence_confidence >= 0.58:
            return (
                "Current observation evidence looks like productive struggle rather than overload, so the next step should preserve challenge while keeping support targeted."
            )
        if session.current_evidence_signal == "overload" and session.current_evidence_confidence >= 0.58:
            return (
                "Current observation evidence looks like reliable overload, so the next generation step should keep support explicit instead of treating the learner's friction as healthy challenge."
            )
        if session.current_evidence_signal == "disengagement" and session.current_evidence_confidence >= 0.58:
            return (
                "Current observation evidence looks more like disengagement than productive challenge, so the next generation step should re-engage the learner before adding independence."
            )
        if session.current_evidence_signal == "support_dependence" and session.current_evidence_confidence >= 0.58:
            return (
                "Current observation evidence shows the learner succeeding mainly under heavy support, so the next generation step should tighten scaffolds instead of releasing a bigger transfer move."
            )
        return (
            "Recent matching runs were informative but not decisive enough to override the baseline mode heuristics."
        )

    def _current_evidence_support_bias(self, *, session, state_profile, trait_profile) -> int:
        if session.current_evidence_confidence < 0.58:
            return 0
        if session.current_evidence_signal in {"overload", "disengagement", "support_dependence"}:
            return -1
        if (
            session.current_evidence_signal == "productive_struggle"
            and session.current_evidence_confidence >= 0.64
            and state_profile.overload_risk <= 0.68
            and trait_profile.challenge_tolerance >= 0.45
        ):
            return 0
        return 0

    def _durable_profile_support_bias(self, *, state_profile, trait_profile) -> int:
        support_pressure = 0
        release_pressure = 0
        if state_profile.source != "insufficient":
            if state_profile.load_reliability >= 0.58 and state_profile.overload_risk >= 0.64:
                support_pressure += 2
            if (
                state_profile.metacognitive_reliability >= 0.58
                and state_profile.confidence_calibration <= 0.42
                and state_profile.help_seeking.value in {"medium", "high"}
            ):
                support_pressure += 1
            if (
                state_profile.recovery_stability >= 0.68
                and state_profile.metacognitive_reliability >= 0.58
                and state_profile.total_load <= 0.5
                and state_profile.confidence_calibration >= 0.62
                and state_profile.signal == "independence_ready"
            ):
                release_pressure += 2
        if trait_profile.source != "insufficient":
            if (
                trait_profile.working_memory_reliability >= 0.68
                and trait_profile.challenge_tolerance < 0.48
                and trait_profile.challenge_evidence_strength >= 0.52
            ):
                support_pressure += 1
            if (
                trait_profile.trait_stability >= 0.72
                and trait_profile.challenge_tolerance >= 0.66
                and trait_profile.challenge_evidence_strength >= 0.58
            ):
                release_pressure += 1
        if support_pressure >= 2 and release_pressure == 0:
            return -1
        if release_pressure >= 2 and support_pressure == 0:
            return 1
        return 0

    def _trait_profile_confidence(self, *, trait_profile) -> float:
        reliability = max(
            trait_profile.processing_speed_reliability,
            trait_profile.working_memory_reliability,
            trait_profile.spatial_reasoning_reliability,
        )
        return round(
            min(
                1.0,
                0.12
                + (trait_profile.trait_stability * 0.34)
                + (trait_profile.challenge_evidence_strength * 0.22)
                + (reliability * 0.32),
            ),
            2,
        )

    def _is_decisive_session(self, session) -> bool:
        return (
            session.source != "insufficient"
            and session.confidence >= self.minimum_session_confidence_for_bias
            and session.signal in {"positive", "negative"}
        )
