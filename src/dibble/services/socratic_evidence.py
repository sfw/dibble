from __future__ import annotations

from dataclasses import dataclass

from dibble.models.assessment import (
    SocraticAssessmentEvaluation,
    SocraticAssessmentRequest,
    SocraticAssessmentSession,
    SocraticEvidenceDimensions,
    SocraticEvidenceStrength,
    SocraticNextAction,
)
from dibble.services.protocols import OutcomeStore
from dibble.services.retrieval.text import salient_tokens


_REASONING_CUES = (
    "because",
    "so",
    "therefore",
    "since",
    "means",
    "if",
    "when",
)
_UNCERTAINTY_CUES = (
    "maybe",
    "might",
    "guess",
    "not sure",
    "idk",
    "i think",
)
_ABSOLUTIST_CUES = ("always", "never", "just", "only")


def _clamp(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


@dataclass(slots=True)
class SocraticEvidenceScorer:
    outcome_store: OutcomeStore

    def evaluate(
        self,
        session: SocraticAssessmentSession,
        request: SocraticAssessmentRequest,
    ) -> SocraticAssessmentEvaluation:
        if not request.learner_response:
            return SocraticAssessmentEvaluation(
                evidence_strength=SocraticEvidenceStrength.insufficient,
                evidence_score=0.0,
                evidence_dimensions=SocraticEvidenceDimensions(),
                inferred_mastery=0.0,
                matched_terms=[],
                rationale="No learner response was provided yet, so the next step is to ask an open diagnostic question.",
                next_action=SocraticNextAction.ask_probe,
            )

        response_text = request.learner_response.lower()
        learner_terms = set(salient_tokens(response_text))
        expected_terms = self._expected_terms(session, request)
        matched_terms = sorted(learner_terms & expected_terms)

        lexical_alignment = self._lexical_alignment(matched_terms, expected_terms)
        reasoning_signal = self._reasoning_signal(response_text, learner_terms)
        understanding_signal = (lexical_alignment * 0.62) + (reasoning_signal * 0.38)
        confidence_alignment = self._confidence_alignment(
            request.learner_confidence, understanding_signal
        )
        progression_signal = self._progression_signal(session, understanding_signal)
        misconception_risk = self._misconception_risk(
            response_text=response_text,
            learner_terms=learner_terms,
            lexical_alignment=lexical_alignment,
            confidence_alignment=confidence_alignment,
            confidence=request.learner_confidence,
        )
        evidence_score = _clamp(
            (lexical_alignment * 0.42)
            + (reasoning_signal * 0.24)
            + (confidence_alignment * 0.16)
            + (progression_signal * 0.12)
            + ((1.0 - misconception_risk) * 0.06)
        )
        evidence_dimensions = SocraticEvidenceDimensions(
            lexical_alignment=round(lexical_alignment, 2),
            reasoning_signal=round(reasoning_signal, 2),
            confidence_alignment=round(confidence_alignment, 2),
            progression_signal=round(progression_signal, 2),
            misconception_risk=round(misconception_risk, 2),
        )
        evidence_strength = self._evidence_strength(evidence_score)
        next_action = self._next_action(
            evidence_strength=evidence_strength,
            evidence_score=evidence_score,
            misconception_risk=misconception_risk,
            confidence_alignment=confidence_alignment,
            progression_signal=progression_signal,
        )
        inferred_mastery = round(
            _clamp(
                (understanding_signal * 0.7)
                + (confidence_alignment * 0.1)
                + (progression_signal * 0.2)
            ),
            2,
        )

        return SocraticAssessmentEvaluation(
            evidence_strength=evidence_strength,
            evidence_score=round(evidence_score, 2),
            evidence_dimensions=evidence_dimensions,
            inferred_mastery=inferred_mastery,
            matched_terms=matched_terms,
            rationale=self._rationale(
                evidence_strength=evidence_strength,
                lexical_alignment=lexical_alignment,
                reasoning_signal=reasoning_signal,
                progression_signal=progression_signal,
                confidence_alignment=confidence_alignment,
                misconception_risk=misconception_risk,
            ),
            next_action=next_action,
        )

    def _expected_terms(
        self,
        session: SocraticAssessmentSession,
        request: SocraticAssessmentRequest,
    ) -> set[str]:
        session_kc_ids = session.target_kc_ids or request.target_kc_ids
        session_lo_ids = session.target_lo_ids or request.target_lo_ids
        context_values = [*session.curriculum_context, *request.curriculum_context]
        expected_terms: set[str] = set()

        for value in [*context_values, *session_kc_ids, *session_lo_ids]:
            expected_terms.update(salient_tokens(value))

        for message in session.conversation_history[-4:]:
            expected_terms.update(salient_tokens(message.text))

        context_tokens = set()
        for value in context_values:
            context_tokens.update(salient_tokens(value))

        for outcome in self.outcome_store.list():
            matches_target = bool(
                set(outcome.knowledge_component_ids) & set(session_kc_ids)
            )
            outcome_terms = set(salient_tokens(outcome.title))
            outcome_terms.update(salient_tokens(outcome.description))
            outcome_terms.update(token.lower() for token in outcome.tags)
            matches_context = (
                bool(outcome_terms & context_tokens) if context_tokens else False
            )
            if matches_target or matches_context:
                expected_terms.update(outcome_terms)

        return expected_terms

    def _lexical_alignment(
        self, matched_terms: list[str], expected_terms: set[str]
    ) -> float:
        expected_count = max(4, min(len(expected_terms), 6))
        return _clamp(len(matched_terms) / expected_count)

    def _reasoning_signal(self, response_text: str, learner_terms: set[str]) -> float:
        cue_hits = sum(1 for cue in _REASONING_CUES if cue in response_text)
        explanation_density = min(len(learner_terms), 18) / 18
        return _clamp((cue_hits * 0.34) + (explanation_density * 0.32))

    def _confidence_alignment(
        self, confidence: float | None, understanding_signal: float
    ) -> float:
        if confidence is None:
            return 0.75
        return _clamp(1.0 - abs(confidence - understanding_signal))

    def _progression_signal(
        self, session: SocraticAssessmentSession, understanding_signal: float
    ) -> float:
        if not session.turns:
            return 0.5
        prior_mastery = sum(
            turn.evaluation.inferred_mastery for turn in session.turns[-2:]
        ) / min(len(session.turns), 2)
        return _clamp(0.5 + ((understanding_signal - prior_mastery) * 0.8))

    def _misconception_risk(
        self,
        *,
        response_text: str,
        learner_terms: set[str],
        lexical_alignment: float,
        confidence_alignment: float,
        confidence: float | None,
    ) -> float:
        uncertainty_hits = sum(1 for cue in _UNCERTAINTY_CUES if cue in response_text)
        absolutist_hits = sum(1 for cue in _ABSOLUTIST_CUES if cue in response_text)
        overconfident_gap = 0.0
        if confidence is not None and confidence >= 0.75 and lexical_alignment < 0.35:
            overconfident_gap = 0.28
        brevity_penalty = 0.16 if len(learner_terms) <= 3 else 0.0
        return _clamp(
            (uncertainty_hits * 0.22)
            + (absolutist_hits * 0.12)
            + overconfident_gap
            + brevity_penalty
            + ((1.0 - confidence_alignment) * 0.12)
        )

    def _evidence_strength(self, evidence_score: float) -> SocraticEvidenceStrength:
        if evidence_score >= 0.62:
            return SocraticEvidenceStrength.demonstrated
        if evidence_score >= 0.4:
            return SocraticEvidenceStrength.emerging
        return SocraticEvidenceStrength.insufficient

    def _next_action(
        self,
        *,
        evidence_strength: SocraticEvidenceStrength,
        evidence_score: float,
        misconception_risk: float,
        confidence_alignment: float,
        progression_signal: float,
    ) -> SocraticNextAction:
        if (
            evidence_strength == SocraticEvidenceStrength.demonstrated
            and confidence_alignment >= 0.4
        ):
            return SocraticNextAction.advance
        if evidence_strength == SocraticEvidenceStrength.insufficient and (
            misconception_risk >= 0.45
            or evidence_score < 0.3
            or progression_signal < 0.45
        ):
            return SocraticNextAction.step_back
        return SocraticNextAction.clarify

    def _rationale(
        self,
        *,
        evidence_strength: SocraticEvidenceStrength,
        lexical_alignment: float,
        reasoning_signal: float,
        progression_signal: float,
        confidence_alignment: float,
        misconception_risk: float,
    ) -> str:
        if evidence_strength == SocraticEvidenceStrength.demonstrated:
            if progression_signal > 0.55:
                return "The learner used grounded concept language, explained causal reasoning, and improved on the recent turn."
            return "The learner used grounded concept language and explained their reasoning clearly enough to test transfer."
        if evidence_strength == SocraticEvidenceStrength.emerging:
            if confidence_alignment < 0.4:
                return "The learner showed some relevant reasoning, but the confidence signal is misaligned enough that a clarifying follow-up is safer."
            return "The learner showed partial grounding or reasoning, but still needs a clarifying follow-up before advancing."
        if misconception_risk >= 0.45:
            return "The learner response stayed thin or uncertain, which raises misconception risk and suggests stepping back to a prerequisite idea."
        if lexical_alignment < 0.25 and reasoning_signal < 0.25:
            return "The learner response did not yet show enough grounded concept language or reasoning to demonstrate understanding."
        return "The learner needs another supported follow-up before the system can trust this understanding signal."
