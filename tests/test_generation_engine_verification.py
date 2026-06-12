from __future__ import annotations

from uuid import UUID, uuid4

from dibble.models.generation import (
    AdaptiveRouteDecision,
    BlockVerification,
    DeliveryMode,
    GeneratedBlock,
    GenerationRequest,
    GroundingReference,
    InterventionType,
    MultipleChoiceInteraction,
    MultipleChoiceOption,
)
from dibble.models.profile import LearnerProfile
from dibble.models.telemetry import AuditEvent
from dibble.services.generation_engine import GenerationEngine
from dibble.services.math_verification import (
    VERIFICATION_FAILED_EVENT_TYPE,
    MathVerificationService,
)
from tests.support import build_profile


class StubRetriever:
    def retrieve(self, request, limit: int = 3):
        return [
            GroundingReference(
                outcome_id="CURR-1",
                title="Equivalent Fractions Foundations",
                grade_level="5",
                excerpt="Use visual fraction models to explain equivalent fractions.",
                score=1.0,
                matched_terms=["equivalent fractions"],
            )
        ]


class StubRouter:
    def route(self, profile, request):
        return AdaptiveRouteDecision(
            intervention_type=InterventionType.targeted_practice,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["test"],
        )


class PassValidator:
    def validate(self, blocks, grounding):
        return []


class SequenceProvider:
    """Returns each configured block list in order; repeats the last one."""

    def __init__(self, block_lists: list[list[GeneratedBlock]]) -> None:
        self.block_lists = block_lists
        self.generate_calls = 0

    def generate(self, request, route, grounding):
        index = min(self.generate_calls, len(self.block_lists) - 1)
        self.generate_calls += 1
        return [block.model_copy(deep=True) for block in self.block_lists[index]]


class StubAuditStore:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(
        self,
        *,
        event_type: str,
        status: str,
        student_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            status=status,
            student_id=UUID(student_id) if student_id else None,
            payload=payload or {},
        )
        self.events.append(event)
        return event

    def list(self, *, limit: int = 50) -> list[AuditEvent]:
        return list(reversed(self.events))[:limit]


def _profile() -> LearnerProfile:
    return LearnerProfile.model_validate(
        build_profile(uuid4(), frustration="low", total_load=0.2)
    )


def _practice_blocks(*, answer_value: str) -> list[GeneratedBlock]:
    return [
        GeneratedBlock(
            kind="summary",
            title="Adding fractions",
            body="We add fractions by finding a common denominator.",
        ),
        GeneratedBlock(
            kind="practice_problem",
            title="Fraction sums",
            body="What is 3/4 + 1/8?",
            interaction=MultipleChoiceInteraction(
                prompt="Pick the sum.",
                options=[
                    MultipleChoiceOption(
                        option_id="A",
                        label="Option A",
                        body="Found a common denominator first.",
                    ),
                    MultipleChoiceOption(
                        option_id="B",
                        label="Option B",
                        body="Added numerators and denominators directly.",
                    ),
                ],
                correct_option_id="A",
            ),
            verification=BlockVerification(
                answer_expression="3/4 + 1/8",
                answer_value=answer_value,
                distractor_values=["4/12"],
            ),
        ),
    ]


def _engine(
    provider: SequenceProvider, audit_store: StubAuditStore
) -> GenerationEngine:
    return GenerationEngine(
        retriever=StubRetriever(),
        router=StubRouter(),
        provider=provider,
        validator=PassValidator(),
        math_verification_service=MathVerificationService(),
        audit_store=audit_store,
    )


def _request(profile: LearnerProfile) -> GenerationRequest:
    return GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        curriculum_context=["Equivalent fractions"],
    )


def test_verified_content_passes_through_without_retry() -> None:
    profile = _profile()
    provider = SequenceProvider([_practice_blocks(answer_value="7/8")])
    audit_store = StubAuditStore()

    response = _engine(provider, audit_store).generate(profile, _request(profile))

    assert provider.generate_calls == 1
    assert response.generation_metadata is not None
    assert response.generation_metadata.verification_status == "verified"
    assert response.generation_metadata.verification_attempts == 1
    assert audit_store.events == []


def test_failed_verification_regenerates_and_recovers() -> None:
    profile = _profile()
    provider = SequenceProvider(
        [
            _practice_blocks(answer_value="4/12"),  # wrong key
            _practice_blocks(answer_value="7/8"),  # corrected
        ]
    )
    audit_store = StubAuditStore()

    response = _engine(provider, audit_store).generate(profile, _request(profile))

    assert provider.generate_calls == 2
    assert response.generation_metadata is not None
    assert response.generation_metadata.verification_status == "verified"
    assert response.route.delivery_mode == DeliveryMode.generated
    regenerated_events = [
        event
        for event in audit_store.events
        if event.event_type == VERIFICATION_FAILED_EVENT_TYPE
    ]
    assert len(regenerated_events) == 1
    assert regenerated_events[0].status == "regenerated"


def test_exhausted_retries_fall_back_to_deterministic_content() -> None:
    profile = _profile()
    provider = SequenceProvider([_practice_blocks(answer_value="4/12")])
    audit_store = StubAuditStore()

    response = _engine(provider, audit_store).generate(profile, _request(profile))

    # Initial attempt + 2 retries.
    assert provider.generate_calls == 3
    assert response.route.delivery_mode == DeliveryMode.static_fallback
    assert response.generation_metadata is not None
    assert response.generation_metadata.verification_status == "fallback"
    # Fallback content never shows an answer key that could be wrong.
    assert all(block.interaction is None for block in response.blocks)
    statuses = [
        event.status
        for event in audit_store.events
        if event.event_type == VERIFICATION_FAILED_EVENT_TYPE
    ]
    assert statuses == ["regenerated", "regenerated", "fallback"]


def test_non_practice_content_is_skipped() -> None:
    profile = _profile()
    provider = SequenceProvider(
        [
            [
                GeneratedBlock(
                    kind="summary",
                    title="Recap",
                    body="Fractions name parts of a whole.",
                ),
                GeneratedBlock(
                    kind="instruction",
                    title="Next",
                    body="Read the model and explain it in your own words.",
                ),
            ]
        ]
    )
    audit_store = StubAuditStore()

    response = _engine(provider, audit_store).generate(profile, _request(profile))

    assert response.generation_metadata is not None
    assert response.generation_metadata.verification_status == "skipped"
    assert audit_store.events == []
