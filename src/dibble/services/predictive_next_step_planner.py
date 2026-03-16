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
        route_signal = route_calibration.signal if route_calibration is not None else "insufficient"
        progress_signal = route_calibration.progress_signal if route_calibration is not None else "insufficient"

        if content_type == RequestedContentType.micro_explanation.value:
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
            return [
                (
                    RequestedContentType.practice_problem,
                    "Practice immediately after explanation while the concept is still active.",
                )
            ]

        if content_type == RequestedContentType.worked_example.value:
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
            ):
                follow_ups.append(
                    (
                        RequestedContentType.assessment_probe,
                        "Prepare a quick diagnostic probe after the worked example.",
                    )
                )
            return follow_ups

        if content_type == RequestedContentType.practice_problem.value:
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
