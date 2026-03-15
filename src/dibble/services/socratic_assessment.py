from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from uuid import uuid4

from dibble.models.assessment import (
    SocraticAssessmentEvaluation,
    SocraticAssessmentRequest,
    SocraticAssessmentResponse,
    SocraticAssessmentSession,
    SocraticEvidenceStrength,
    SocraticMessage,
    SocraticMessageRole,
    SocraticNextAction,
    SocraticTurnRecord,
)
from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.retrieval.text import salient_tokens
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore


@dataclass(slots=True)
class SocraticAssessmentService:
    generation_engine: GenerationEngine
    curriculum_store: SQLiteCurriculumStore
    session_store: SQLiteSocraticSessionStore

    def assess(self, profile: LearnerProfile, request: SocraticAssessmentRequest) -> SocraticAssessmentResponse:
        session = self._load_or_create_session(request)
        conversation_history = self._merged_history(session, request)
        generation_request = GenerationRequest(
            student_id=request.student_id,
            target_kc_ids=session.target_kc_ids,
            target_lo_ids=session.target_lo_ids,
            intent="assessment",
            requested_content_type="assessment_probe",
            learner_prompt=self._build_assessment_prompt(request, conversation_history),
            curriculum_context=session.curriculum_context,
        )
        response = self.generation_engine.generate(profile, generation_request)
        prompt = self._extract_prompt(response.blocks)
        evaluation = self._evaluate_response(request, response)
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
            turn_id=turn_id,
            prompt=prompt,
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
        request: SocraticAssessmentRequest,
        conversation_history: list[SocraticMessage],
    ) -> str:
        history_text = " ".join(f"{item.role.value}: {item.text}" for item in conversation_history[-6:])
        confidence_text = (
            f" Learner confidence signal: {request.learner_confidence:.2f}."
            if request.learner_confidence is not None
            else ""
        )
        if request.learner_response:
            return (
                "Ask one short Socratic follow-up question that checks reasoning, not recall only. "
                f"The learner previously answered: {request.learner_response}.{confidence_text} "
                f"Recent conversation: {history_text or 'none'}"
            )
        return (
            "Ask one short open-ended diagnostic question that reveals reasoning about the target concept. "
            f"Recent conversation: {history_text or 'none'}.{confidence_text}"
        )

    def _extract_prompt(self, blocks) -> str:
        for block in blocks:
            if "?" in block.body:
                return block.body.strip()
        for block in blocks:
            if block.kind in {"instruction", "practice"}:
                return f"{block.body.strip()} What do you notice?"
        return "What makes you think that?"

    def _evaluate_response(self, request: SocraticAssessmentRequest, response) -> SocraticAssessmentEvaluation:
        if not request.learner_response:
            return SocraticAssessmentEvaluation(
                evidence_strength=SocraticEvidenceStrength.insufficient,
                inferred_mastery=0.0,
                matched_terms=[],
                rationale="No learner response was provided yet, so the next step is to ask an open diagnostic question.",
                next_action=SocraticNextAction.ask_probe,
            )

        learner_terms = set(salient_tokens(request.learner_response))
        expected_terms = self._expected_terms(request, response)
        matched_terms = sorted(learner_terms & expected_terms)
        expected_count = max(3, len(expected_terms))
        overlap_ratio = len(matched_terms) / expected_count
        reasoning_cues = {"because", "so", "therefore", "since", "means"}
        has_reasoning = any(cue in request.learner_response.lower() for cue in reasoning_cues)

        if overlap_ratio >= 0.14 and has_reasoning:
            return SocraticAssessmentEvaluation(
                evidence_strength=SocraticEvidenceStrength.demonstrated,
                inferred_mastery=0.74,
                matched_terms=matched_terms,
                rationale="The learner used several curriculum-aligned terms and connected them with an explicit reasoning cue.",
                next_action=SocraticNextAction.advance,
            )
        if overlap_ratio >= 0.1 or has_reasoning:
            return SocraticAssessmentEvaluation(
                evidence_strength=SocraticEvidenceStrength.emerging,
                inferred_mastery=0.52,
                matched_terms=matched_terms,
                rationale="The learner showed partial conceptual language or reasoning, but still needs a clarifying follow-up.",
                next_action=SocraticNextAction.clarify,
            )
        return SocraticAssessmentEvaluation(
            evidence_strength=SocraticEvidenceStrength.insufficient,
            inferred_mastery=0.28,
            matched_terms=matched_terms,
            rationale="The learner response did not yet show enough grounded concept language to demonstrate understanding.",
            next_action=SocraticNextAction.step_back,
        )

    def _expected_terms(self, request: SocraticAssessmentRequest, response) -> set[str]:
        terms = set()
        for value in request.curriculum_context:
            terms.update(salient_tokens(value))
        for value in request.target_kc_ids + request.target_lo_ids:
            terms.update(salient_tokens(value))
        for grounding in response.grounding:
            terms.update(salient_tokens(grounding.title))
            terms.update(token.lower() for token in grounding.matched_terms)
            resource = self.curriculum_store.get(grounding.resource_id)
            if resource is not None:
                terms.update(salient_tokens(resource.title))
                terms.update(salient_tokens(resource.body))
                for tag in resource.tags:
                    terms.update(salient_tokens(tag))
        for block in response.blocks:
            terms.update(salient_tokens(block.title))
            terms.update(salient_tokens(block.body))
        return terms
