from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import GeneratedContent, RequestedContentType


@dataclass(frozen=True, slots=True)
class PredictiveNextStepPlanner:
    def plan(self, generated_content: GeneratedContent) -> list[tuple[RequestedContentType, str]]:
        request_context = generated_content.request_context
        content_type = str(
            request_context.get("selected_content_type")
            or request_context.get("requested_content_type")
            or generated_content.content_type
        )
        route_calibration = generated_content.response.route.calibration
        mode_calibration = request_context.get("mode_calibration", {})
        mode_support_bias = int(mode_calibration.get("support_bias", 0)) if isinstance(mode_calibration, dict) else 0
        progression = request_context.get("progression", {})
        progression_action = (
            str(progression.get("action", "stay_on_requested_target"))
            if isinstance(progression, dict)
            else "stay_on_requested_target"
        )
        progression_confidence = (
            float(progression.get("confidence", 0.0))
            if isinstance(progression, dict)
            else 0.0
        )
        strategy_trajectory_state = (
            str(mode_calibration.get("strategy_trajectory_state", "insufficient"))
            if isinstance(mode_calibration, dict)
            else "insufficient"
        )
        strategy_next_action = (
            str(mode_calibration.get("strategy_recommended_next_action", "monitor"))
            if isinstance(mode_calibration, dict)
            else "monitor"
        )
        strategy_relapse_risk = (
            float(mode_calibration.get("strategy_relapse_risk", 0.0))
            if isinstance(mode_calibration, dict)
            else 0.0
        )
        sequence_action = (
            str(mode_calibration.get("sequence_action") or mode_calibration.get("strategy_sequence_action", "monitor"))
            if isinstance(mode_calibration, dict)
            else "monitor"
        )
        session_phase = (
            str(mode_calibration.get("session_phase", "monitor"))
            if isinstance(mode_calibration, dict)
            else "monitor"
        )
        route_signal = route_calibration.signal if route_calibration is not None else "insufficient"
        progress_signal = route_calibration.progress_signal if route_calibration is not None else "insufficient"

        if content_type == RequestedContentType.micro_explanation.value:
            if progression_action == "hold_target" and progression_confidence >= 0.5:
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Same-session progression evidence still says hold the current target, so warm one more guided practice step before transfer.",
                    )
                ]
            if session_phase == "consolidate":
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Within-session recovery is still consolidating, so warm one more guided practice step before transfer.",
                    )
                ]
            if self._should_rebuild_prerequisite(
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
                strategy_relapse_risk=strategy_relapse_risk,
            ):
                return [
                    (
                        RequestedContentType.remedial_micro_module,
                        "Cross-session strategy suggests the learner is relapsing, so warm a prerequisite repair step before more explanation.",
                    )
                ]
            if self._should_vary_support(
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
            ):
                return [
                    (
                        RequestedContentType.worked_example,
                        "Cross-session strategy suggests varying support before moving straight into independent practice.",
                    )
                ]
            if self._needs_modeled_support(
                route_signal=route_signal,
                progress_signal=progress_signal,
                mode_support_bias=mode_support_bias,
            ):
                return [
                    (
                        RequestedContentType.worked_example,
                        "Recent calibration suggests adding modeled support before moving into independent practice.",
                    )
                ]
            if sequence_action == "attempt_transfer":
                return [
                    (
                        RequestedContentType.assessment_probe,
                        "Per-KC sequencing suggests the learner can test transfer on the target KC next.",
                    )
                ]
            return [
                (
                    RequestedContentType.practice_problem,
                    "Practice immediately after explanation while the concept is still active.",
                )
            ]

        if content_type == RequestedContentType.worked_example.value:
            if progression_action == "hold_target" and progression_confidence >= 0.5:
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Same-session progression evidence still says hold the current target, so warm guided practice instead of a transfer check.",
                    )
                ]
            if session_phase == "bridge":
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Within-session recovery is in a bridge phase, so warm one guided target problem before transfer.",
                    )
                ]
            if self._should_rebuild_prerequisite(
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
                strategy_relapse_risk=strategy_relapse_risk,
            ):
                return [
                    (
                        RequestedContentType.remedial_micro_module,
                        "Cross-session strategy suggests stepping back to prerequisite repair before fading support further.",
                    )
                ]
            follow_ups = [
                (
                    RequestedContentType.practice_problem,
                    "Fade from modeled support into a near-term practice problem.",
                )
            ]
            if not self._needs_modeled_support(
                route_signal=route_signal,
                progress_signal=progress_signal,
                mode_support_bias=mode_support_bias,
            ) and self._should_check_transfer(
                route_signal=route_signal,
                progress_signal=progress_signal,
                mode_support_bias=mode_support_bias,
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
            ):
                follow_ups.append(
                    (
                        RequestedContentType.assessment_probe,
                        "Prepare a quick diagnostic probe after the worked example.",
                    )
                )
            return follow_ups

        if content_type == RequestedContentType.practice_problem.value:
            if progression_action == "hold_target" and progression_confidence >= 0.5:
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Same-session progression evidence still says hold the current target, so warm another target-aligned practice step.",
                    )
                ]
            if progression_action == "attempt_transfer" and progression_confidence >= 0.5:
                return [
                    (
                        RequestedContentType.assessment_probe,
                        "Same-session progression evidence now suggests testing transfer on the current target.",
                    )
                ]
            if session_phase == "consolidate":
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Within-session recovery is still consolidating, so keep one more guided practice step warm.",
                    )
                ]
            if session_phase == "bridge":
                return [
                    (
                        RequestedContentType.assessment_probe,
                        "Within-session recovery has reached the bridge step, so prepare a transfer check next.",
                    )
                ]
            if self._should_rebuild_prerequisite(
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
                strategy_relapse_risk=strategy_relapse_risk,
            ):
                return [
                    (
                        RequestedContentType.remedial_micro_module,
                        "Cross-session strategy suggests relapse, so warm a prerequisite repair step instead of another independent attempt.",
                    )
                ]
            if self._should_vary_support(
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
            ):
                return [
                    (
                        RequestedContentType.worked_example,
                        "Cross-session strategy suggests a plateau or uneven outcomes, so warm a varied modeled example next.",
                    )
                ]
            if self._needs_modeled_support(
                route_signal=route_signal,
                progress_signal=progress_signal,
                mode_support_bias=mode_support_bias,
            ):
                return [
                    (
                        RequestedContentType.worked_example,
                        "Recent struggle suggests warming a modeled example before another independent step.",
                    )
                ]
            return [
                (
                    RequestedContentType.assessment_probe,
                    "Prepare a quick transfer check after practice.",
                )
            ]

        if content_type == RequestedContentType.remedial_micro_module.value:
            if session_phase == "bridge":
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Within-session recovery is bridging back to the target, so warm a guided target problem next.",
                    )
                ]
            if session_phase == "consolidate":
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Within-session recovery is consolidating, so warm one more repair-focused practice step before transfer.",
                    )
                ]
            if sequence_action in {"hold_target", "hold_repair_target"}:
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Per-KC sequencing suggests staying on the repair target before moving back into transfer.",
                    )
                ]
            if self._should_vary_support(
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
            ):
                return [
                    (
                        RequestedContentType.practice_problem,
                        "Keep the learner in guided repair practice while the cross-session plateau or volatility stabilizes.",
                    )
                ]
            follow_ups = [
                (
                    RequestedContentType.practice_problem,
                    "Warm a repair-focused practice problem after remediation.",
                )
            ]
            if self._shows_independence(
                route_signal=route_signal,
                progress_signal=progress_signal,
                mode_support_bias=mode_support_bias,
            ) and self._should_check_transfer(
                route_signal=route_signal,
                progress_signal=progress_signal,
                mode_support_bias=mode_support_bias,
                strategy_trajectory_state=strategy_trajectory_state,
                strategy_next_action=strategy_next_action,
            ):
                follow_ups.append(
                    (
                        RequestedContentType.assessment_probe,
                        "Recent improvement suggests a quick transfer check after remediation.",
                    )
                )
            return follow_ups

        return []

    def _needs_modeled_support(
        self,
        *,
        route_signal: str,
        progress_signal: str,
        mode_support_bias: int,
    ) -> bool:
        return route_signal == "negative" or progress_signal == "declining" or mode_support_bias < 0

    def _shows_independence(
        self,
        *,
        route_signal: str,
        progress_signal: str,
        mode_support_bias: int,
    ) -> bool:
        return route_signal == "positive" or progress_signal == "improving" or mode_support_bias > 0

    def _should_rebuild_prerequisite(
        self,
        *,
        strategy_trajectory_state: str,
        strategy_next_action: str,
        strategy_relapse_risk: float,
    ) -> bool:
        return (
            strategy_next_action == "rebuild_prerequisite"
            or strategy_trajectory_state == "relapsing"
            or strategy_relapse_risk >= 0.65
        )

    def _should_vary_support(
        self,
        *,
        strategy_trajectory_state: str,
        strategy_next_action: str,
    ) -> bool:
        return (
            strategy_next_action in {"introduce_varied_support", "stabilize_support"}
            or strategy_trajectory_state in {"plateaued", "volatile"}
        )

    def _should_check_transfer(
        self,
        *,
        route_signal: str,
        progress_signal: str,
        mode_support_bias: int,
        strategy_trajectory_state: str,
        strategy_next_action: str,
    ) -> bool:
        if strategy_trajectory_state in {"plateaued", "volatile", "relapsing"}:
            return False
        if strategy_next_action == "check_transfer_readiness":
            return True
        if strategy_trajectory_state == "insufficient" and strategy_next_action == "monitor":
            return True
        return self._shows_independence(
            route_signal=route_signal,
            progress_signal=progress_signal,
            mode_support_bias=mode_support_bias,
        )
