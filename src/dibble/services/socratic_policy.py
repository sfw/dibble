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
        already_step_back = any(turn.prompt_style == SocraticPromptStyle.scaffolded_step_back for turn in session.turns[-2:])
        already_checked_transfer = any(turn.prompt_style == SocraticPromptStyle.transfer_check for turn in session.turns[-2:])

        if latest_evaluation.evidence_strength == SocraticEvidenceStrength.demonstrated:
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
            if mastery_trend < -0.08 and not already_step_back:
                return SocraticPolicyDecision(
                    prompt_style=SocraticPromptStyle.scaffolded_step_back,
                    rationale="The learner is regressing across recent turns, so stepping back to a prerequisite idea is safer than pushing for another thin clarification.",
                )
            return SocraticPolicyDecision(
                prompt_style=SocraticPromptStyle.clarification,
                rationale="The learner is showing partial understanding, so the next prompt should sharpen their explanation before the system advances.",
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
