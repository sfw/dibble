from __future__ import annotations

from dataclasses import dataclass

from dibble.models.assessment import (
    SocraticAssessmentEvaluation,
    SocraticAssessmentRequest,
    SocraticAssessmentSession,
    SocraticEvidenceStrength,
    SocraticPromptStyle,
)


@dataclass(frozen=True, slots=True)
class SocraticPolicyDecision:
    prompt_style: SocraticPromptStyle
    rationale: str


@dataclass(slots=True)
class SocraticTurnPolicy:
    def decide(
        self,
        session: SocraticAssessmentSession,
        request: SocraticAssessmentRequest,
        current_evaluation: SocraticAssessmentEvaluation,
    ) -> SocraticPolicyDecision:
        if not session.turns and not request.learner_response:
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.diagnostic,
                rationale="Start with an open probe so the system can observe the learner's current reasoning without over-scaffolding.",
            )

        latest_evaluation = current_evaluation if request.learner_response else session.turns[-1].evaluation if session.turns else current_evaluation
        recent_mastery = [turn.evaluation.inferred_mastery for turn in session.turns[-2:]]
        if request.learner_response:
            recent_mastery.append(current_evaluation.inferred_mastery)
        mastery_trend = 0.0
        if len(recent_mastery) >= 2:
            mastery_trend = recent_mastery[-1] - recent_mastery[0]

        repeated_low_signal = all(
            turn.evaluation.evidence_strength == SocraticEvidenceStrength.insufficient for turn in session.turns[-2:]
        )
        repeated_clarification = (
            len(session.turns) >= 2
            and all(turn.prompt_style == SocraticPromptStyle.clarification for turn in session.turns[-2:])
        )
        repeated_step_back = (
            len(session.turns) >= 2
            and all(turn.prompt_style == SocraticPromptStyle.scaffolded_step_back for turn in session.turns[-2:])
        )
        already_step_back = any(turn.prompt_style == SocraticPromptStyle.scaffolded_step_back for turn in session.turns[-2:])
        already_checked_transfer = any(turn.prompt_style == SocraticPromptStyle.transfer_check for turn in session.turns[-2:])
        last_prompt_style = session.turns[-1].prompt_style if session.turns else None
        stalled_recent_progress = len(recent_mastery) >= 2 and abs(mastery_trend) < 0.05
        clarification_loop = (
            repeated_clarification
            and stalled_recent_progress
            and latest_evaluation.evidence_score < 0.6
            and latest_evaluation.evidence_dimensions.misconception_risk < 0.45
        )
        step_back_loop = (
            repeated_step_back
            and stalled_recent_progress
            and latest_evaluation.evidence_dimensions.progression_signal < 0.55
            and latest_evaluation.evidence_dimensions.misconception_risk < 0.5
        )

        if latest_evaluation.evidence_strength == SocraticEvidenceStrength.demonstrated:
            if (
                last_prompt_style == SocraticPromptStyle.scaffolded_step_back
                and (
                    request.learner_confidence is not None
                    and request.learner_confidence < 0.55
                    or latest_evaluation.evidence_dimensions.progression_signal < 0.55
                )
            ):
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.clarification,
                    rationale="The learner recovered after a step-back prompt but still needs to restate the repaired idea clearly before transfer.",
                )
            if request.learner_confidence is not None and request.learner_confidence < 0.45:
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.clarification,
                    rationale="The learner showed understanding but low confidence, so a short clarification can stabilize the idea before transfer.",
                )
            if request.learner_response is None:
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.transfer_check,
                    rationale="The latest stored turn demonstrated understanding, so the next prompt should keep pressure on transfer to confirm the idea holds in a nearby example.",
                )
            if already_checked_transfer and mastery_trend >= 0.0:
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.diagnostic,
                    rationale="Recent turns already checked transfer, so the next best move is a fresh probe from a new angle rather than repeating the same prompt style.",
                )
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.transfer_check,
                rationale="Recent evidence is strong enough to test whether the learner can transfer the idea to a nearby example.",
            )

        if latest_evaluation.evidence_strength == SocraticEvidenceStrength.emerging:
            if clarification_loop:
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.diagnostic,
                    rationale="Recent clarification turns are circling the same gap, so the next prompt should probe from a new angle instead of repeating the same wording.",
                )
            if step_back_loop:
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.diagnostic,
                    rationale="Repeated step-back turns are no longer moving the learner forward, so the next prompt should test the idea through a new representation before adding more scaffold.",
                )
            if (
                last_prompt_style == SocraticPromptStyle.scaffolded_step_back
                and (
                    latest_evaluation.evidence_score >= 0.45
                    or latest_evaluation.evidence_dimensions.progression_signal >= 0.55
                )
            ):
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.clarification,
                    rationale="The learner is improving after a step-back turn, so the next prompt should refine the repaired reasoning before any transfer check.",
                )
            if repeated_clarification and (
                latest_evaluation.evidence_dimensions.confidence_alignment < 0.4
                or (request.learner_confidence is not None and request.learner_confidence < 0.45)
            ):
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.scaffolded_step_back,
                    rationale="Repeated clarification has not stabilized the learner's explanation, so the next prompt should step back to a prerequisite anchor.",
                )
            if mastery_trend < -0.08 and not already_step_back:
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.scaffolded_step_back,
                    rationale="The learner is regressing across recent turns, so stepping back to a prerequisite idea is safer than pushing for another thin clarification.",
                )
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.clarification,
                rationale="The learner is showing partial understanding, so the next prompt should sharpen their explanation before the system advances.",
            )

        if (
            last_prompt_style == SocraticPromptStyle.transfer_check
            and latest_evaluation.evidence_dimensions.misconception_risk < 0.45
        ):
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.clarification,
                rationale="The learner did not yet transfer the idea, but the gap looks narrow enough for one focused clarification before a full step-back.",
            )
        if clarification_loop or step_back_loop:
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.diagnostic,
                rationale="Recent Socratic turns have started to loop, so the next prompt should re-probe the learner's thinking from a new angle.",
            )
        if repeated_low_signal and not already_step_back:
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.scaffolded_step_back,
                rationale="Multiple recent turns stayed below the evidence bar, so the next prompt should step back to prerequisite reasoning.",
            )
        if latest_evaluation.evidence_dimensions.misconception_risk >= 0.45:
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.scaffolded_step_back,
                rationale="The current response carries elevated misconception risk, so the next prompt should rebuild the prerequisite idea explicitly.",
            )
        return SocraticPolicyDecision(
            prompt_style=SocraticPromptStyle.clarification,
            rationale="The system needs one more focused clarification before deciding whether to step back further.",
        )
