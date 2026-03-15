from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from dibble.models.assessment import (
    SocraticAssessmentEvaluation,
    SocraticAssessmentRequest,
    SocraticAssessmentResponse,
    SocraticAssessmentSession,
    SocraticMessage,
    SocraticMessageRole,
    SocraticPromptStyle,
    SocraticTurnRecord,
)
from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.services.generation_engine import GenerationEngine
from dibble.services.socratic_evidence import SocraticEvidenceScorer
from dibble.services.socratic_policy import SocraticTurnPolicy
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore


@dataclass(slots=True)
class SocraticAssessmentService:
    generation_engine: GenerationEngine
    session_store: SQLiteSocraticSessionStore
    evidence_scorer: SocraticEvidenceScorer
    turn_policy: SocraticTurnPolicy

    def assess(self, profile: LearnerProfile, request: SocraticAssessmentRequest) -> SocraticAssessmentResponse:
        session = self._load_or_create_session(request)
        evaluation = self.evidence_scorer.evaluate(session, request)
        conversation_history = self._merged_history(session, request)
        policy_decision = self.turn_policy.decide(session, request, evaluation)
        generation_request = GenerationRequest(
            student_id=request.student_id,
            learning_session_id=session.learning_session_id,
            target_kc_ids=session.target_kc_ids,
            target_lo_ids=session.target_lo_ids,
            intent="assessment",
            requested_content_type="assessment_probe",
            learner_prompt=self._build_assessment_prompt(
                request=request,
                conversation_history=conversation_history,
                prompt_style=policy_decision.prompt_style,
                policy_rationale=policy_decision.rationale,
                evaluation=evaluation,
            ),
            curriculum_context=session.curriculum_context,
        )
        response = self.generation_engine.generate(profile, generation_request)
        prompt = self._extract_prompt(response.blocks)
        generation_metadata = response.generation_metadata
        turn_id = str(uuid4())
        updated_history = list(conversation_history)
        updated_history.append(SocraticMessage(role=SocraticMessageRole.tutor, text=prompt))
        updated_session = session.model_copy(
            update={
                "conversation_history": updated_history,
                "turns": [
                    *session.turns,
                    SocraticTurnRecord(
                        turn_id=turn_id,
                        prompt=prompt,
                        prompt_style=policy_decision.prompt_style,
                        policy_rationale=policy_decision.rationale,
                        learner_response=request.learner_response,
                        evaluation=evaluation,
                    ),
                ],
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self.session_store.upsert(updated_session)

        return SocraticAssessmentResponse(
            session_id=updated_session.session_id,
            student_id=request.student_id,
            learning_session_id=updated_session.learning_session_id,
            turn_id=turn_id,
            prompt=prompt,
            prompt_style=policy_decision.prompt_style,
            policy_rationale=policy_decision.rationale,
            evaluation=evaluation,
            route=response.route,
            grounding=response.grounding,
            generated_blocks=response.blocks,
            conversation_history=updated_session.conversation_history,
            generation_id=response.generation_id,
            generation_metadata=generation_metadata,
        )

    def get_session(self, session_id: str) -> SocraticAssessmentSession | None:
        return self.session_store.get(session_id)

    def _load_or_create_session(self, request: SocraticAssessmentRequest) -> SocraticAssessmentSession:
        if request.session_id:
            session = self.session_store.get(request.session_id)
            if session is not None:
                return session
        now = datetime.now(timezone.utc)
        return SocraticAssessmentSession(
            session_id=request.session_id or str(uuid4()),
            student_id=request.student_id,
            learning_session_id=request.learning_session_id,
            target_kc_ids=request.target_kc_ids,
            target_lo_ids=request.target_lo_ids,
            curriculum_context=request.curriculum_context,
            conversation_history=[],
            turns=[],
            created_at=now,
            updated_at=now,
        )

    def _merged_history(
        self,
        session: SocraticAssessmentSession,
        request: SocraticAssessmentRequest,
    ) -> list[SocraticMessage]:
        history = list(session.conversation_history)
        if request.conversation_history:
            history.extend(request.conversation_history)
        if request.learner_response:
            history.append(SocraticMessage(role=SocraticMessageRole.learner, text=request.learner_response))
        return history

    def _build_assessment_prompt(
        self,
        *,
        request: SocraticAssessmentRequest,
        conversation_history: list[SocraticMessage],
        prompt_style: SocraticPromptStyle,
        policy_rationale: str,
        evaluation: SocraticAssessmentEvaluation,
    ) -> str:
        history_text = " ".join(f"{item.role.value}: {item.text}" for item in conversation_history[-6:])
        confidence_text = (
            f" Learner confidence signal: {request.learner_confidence:.2f}."
            if request.learner_confidence is not None
            else ""
        )
        evidence_text = (
            f" Evidence score: {evaluation.evidence_score:.2f}. "
            f"Current evidence strength: {evaluation.evidence_strength.value}. "
            f"Evaluation rationale: {evaluation.rationale}"
        )
        if prompt_style == SocraticPromptStyle.scaffolded_step_back:
            return (
                "Ask one short scaffolded step-back question that targets a prerequisite idea before returning to the main concept. "
                f"Policy rationale: {policy_rationale}.{evidence_text} Recent conversation: {history_text or 'none'}.{confidence_text}"
            )
        if prompt_style == SocraticPromptStyle.clarification:
            return (
                "Ask one short clarification question that helps the learner explain their reasoning more precisely. "
                f"Policy rationale: {policy_rationale}.{evidence_text} Recent conversation: {history_text or 'none'}.{confidence_text}"
            )
        if prompt_style == SocraticPromptStyle.transfer_check:
            return (
                "Ask one short transfer question that checks whether the learner can apply the idea in a nearby example. "
                f"Policy rationale: {policy_rationale}.{evidence_text} Recent conversation: {history_text or 'none'}.{confidence_text}"
            )
        if request.learner_response:
            return (
                "Ask one short Socratic follow-up question that checks reasoning, not recall only. "
                f"The learner previously answered: {request.learner_response}. "
                f"Policy rationale: {policy_rationale}.{evidence_text}{confidence_text} Recent conversation: {history_text or 'none'}"
            )
        return (
            "Ask one short open-ended diagnostic question that reveals reasoning about the target concept. "
            f"Policy rationale: {policy_rationale}.{evidence_text} Recent conversation: {history_text or 'none'}.{confidence_text}"
        )

    def _extract_prompt(self, blocks) -> str:
        for block in blocks:
            if "?" in block.body:
                return block.body.strip()
        for block in blocks:
            if block.kind in {"instruction", "practice"}:
                return f"{block.body.strip()} What do you notice?"
        return "What makes you think that?"
