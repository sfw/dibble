from uuid import uuid4

from dibble.models.generation import GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.services.adaptive_router import AdaptiveRouter
from tests.support import build_profile


def test_router_returns_targeted_practice_for_low_mastery():
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.2}, engagement="medium")
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="practice")

    decision = AdaptiveRouter().route(profile, request)

    assert decision.intervention_type.value == "targeted_practice"
    assert decision.delivery_mode.value == "generated"


def test_router_returns_stretch_for_high_mastery_and_high_engagement():
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.95}, engagement="high")
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="explanation")

    decision = AdaptiveRouter().route(profile, request)

    assert decision.intervention_type.value == "stretch"
    assert decision.delivery_mode.value == "blended"


def test_router_holds_back_stretch_when_metacognitive_readiness_is_low():
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.95},
            engagement="high",
            confidence_calibration=0.35,
            help_seeking="high",
        )
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="explanation")

    decision = AdaptiveRouter().route(profile, request)

    assert decision.intervention_type.value == "reteach"
    assert decision.delivery_mode.value == "generated"
