from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from dibble.models.assessment import SocraticEvidenceStrength
from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    CurriculumContentRequest,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
    RequestedContentType,
)
from dibble.models.observations import (
    InferredLearnerState,
    LearnerObservation,
    LearnerObservationCreate,
)
from dibble.models.profile import CognitiveTraitScore, LearnerProfile
from dibble.services.content_workflow import ContentWorkflowService
from dibble.services.harness.assessment_evidence import (
    AssessmentEvidenceHarness,
    RecordObservationEvidenceCommand,
)
from dibble.services.harness.content_generation import PreparedContentGeneration
from dibble.services.harness.within_session_control import BindGenerationRequestResult
from dibble.services.harness.facades import PreparedAuthoringRequest
from dibble.services.harness.learner_profile import (
    ApplyObservationEvidenceCommand,
    LearnerProfileHarness,
)
from dibble.services.harness.modality_routing import (
    ModalityRoutingPlan,
    TextModalityDirective,
)
from dibble.services.harness.policy import HarnessAuthoringPolicy
from dibble.services.learner_state_calibration import LearnerStateCalibrationResult
from dibble.services.observation_profile_update import ObservationProfileUpdateResult
from tests.support import build_profile


class _ProfileStore:
    def __init__(self, profile):
        self.profile = profile
        self.upserts = []

    def get(self, student_id):
        return self.profile if student_id == self.profile.student_id else None

    def upsert(self, profile):
        self.profile = profile
        self.upserts.append(profile)
        return profile


class _KnowledgeComponentStore:
    def get(self, kc_id):
        return None


class _AuditStore:
    def append(self, **kwargs):
        return type("AuditEvent", (), kwargs)()


class _GenerationModeCalibrator:
    def calibrate_request(self, request):
        return request


class _RoutingHarness:
    def __init__(self, plan):
        self.plan_result = plan
        self.calls = []

    def plan(self, *, profile, request):
        self.calls.append((profile, request))
        return self.plan_result


class _ContentGenerationHarness:
    def __init__(self, prepared_generation):
        self.prepared_generation = prepared_generation
        self.prepare_calls = []

    def prepare_generation(self, *, profile, request, routing_plan=None):
        self.prepare_calls.append((profile, request, routing_plan))
        return self.prepared_generation


class _WithinSessionControlHarness:
    def bind_generation_request(self, command):
        return BindGenerationRequestResult(request=command.request, session=None)

    def summarize_generated_content(self, command):
        raise AssertionError("Summary generation should not be used in this test")


class _ObservationStore:
    def __init__(self):
        self.append_calls = []
        self.recent = []

    def append(self, *, student_id, observation):
        persisted = LearnerObservation.model_validate(
            {
                **observation.model_dump(mode="json"),
                "observation_id": "obs-1",
                "student_id": student_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.append_calls.append((student_id, observation))
        self.recent = [persisted]
        return persisted

    def list_recent(self, *, student_id):
        return list(self.recent)


class _StateInferenceService:
    def __init__(self, inferred_state):
        self.inferred_state = inferred_state

    def infer(self, *, student_id, observations):
        return self.inferred_state


class _LearnerStateCalibrator:
    def __init__(self, result):
        self.result = result

    def calibrate(self, *, student_id, observation, inferred_state):
        return self.result


class _CognitiveTraitInferenceService:
    def __init__(self, traits):
        self.traits = traits

    def infer(self, *, student_id, observations, existing_traits):
        return self.traits


class _ObservationProfileUpdater:
    def __init__(self):
        self.calls = []

    def apply(self, profile, observation, *, recent_observations=None):
        self.calls.append((profile, observation, recent_observations))
        updated_profile = profile.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        return ObservationProfileUpdateResult(
            profile=updated_profile,
            applied=True,
            inferred_mastery=0.72,
            evidence_strength=SocraticEvidenceStrength.emerging,
            linkage_source="observation",
            matched_observation_count=len(recent_observations or []),
            average_recent_observed_mastery=0.72,
            evidence_confidence=0.61,
            kc_mastery_updates={"KC-1": 0.72},
            lo_mastery_updates={},
            propagated_kc_mastery_updates={},
            propagated_lo_mastery_updates={},
        )


class _SocraticProfileUpdater:
    def apply(self, profile, request, response, session):
        raise AssertionError("Socratic profile updater should not be used in this test")


def test_content_workflow_routes_prepare_stage_through_harnesses():
    student_id = uuid4()
    profile = LearnerProfile.model_validate(
        build_profile(student_id, frustration="low", total_load=0.2)
    )
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.reteach,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["test"],
    )
    plan = ModalityRoutingPlan(
        route=route,
        pedagogical_move=route.intervention_type.value,
        directive=TextModalityDirective(),
        rationale=["test"],
    )
    prepared_generation = PreparedContentGeneration(
        profile=profile,
        request=GenerationRequest(
            student_id=student_id,
            target_kc_ids=["KC-1"],
            intent=ContentIntent.explanation,
            requested_content_type=RequestedContentType.micro_explanation,
        ),
        routing_plan=plan,
        authoring=PreparedAuthoringRequest(
            policy=HarnessAuthoringPolicy(
                content_type=RequestedContentType.micro_explanation,
                prompt_guidance="Keep it concise.",
                request_context={},
                generation_constraints={},
            ),
            curriculum_request=CurriculumContentRequest(
                grade_level="5",
                intent=ContentIntent.explanation,
                content_type=RequestedContentType.micro_explanation,
                target_kc_ids=["KC-1"],
            ),
        ),
    )
    routing_harness = _RoutingHarness(plan)
    content_generation_harness = _ContentGenerationHarness(prepared_generation)
    workflow = ContentWorkflowService(
        profile_store=_ProfileStore(profile),
        observation_store=None,
        knowledge_component_store=_KnowledgeComponentStore(),
        generated_content_store=None,
        router=None,
        generation_engine=None,
        modality_routing_harness=routing_harness,
        content_generation_harness=content_generation_harness,
        content_warmer=None,
        generation_mode_calibrator=_GenerationModeCalibrator(),
        predictive_content_warmer=None,
        predictive_warm_scheduler=None,
        remediation_planner=None,
        remediation_workflow_coordinator=None,
        strategy_signal_service=type(
            "StrategySignalService",
            (),
            {
                "strategy_for": staticmethod(
                    lambda **kwargs: type(
                        "StrategySummary",
                        (),
                        {
                            "signal": "monitor",
                            "source": "test",
                            "support_bias": 0,
                            "recovery_focus": "monitor",
                        },
                    )()
                )
            },
        )(),
        misconception_profile_recorder=None,
        audit_store=_AuditStore(),
        within_session_adaptation_service=None,
        within_session_control_harness=_WithinSessionControlHarness(),
    )
    request = GenerationRequest(
        student_id=student_id,
        target_kc_ids=["KC-1"],
        intent=ContentIntent.explanation,
        requested_content_type=RequestedContentType.micro_explanation,
    )

    decision = workflow.decide_route(request)
    prepared = workflow.prepare_generation_request(request)

    assert decision == route
    assert routing_harness.calls == [(profile, request)]
    assert content_generation_harness.prepare_calls == [(profile, request, None)]
    assert prepared.prepared_generation is prepared_generation
    assert "student_id" not in prepared.prepared_generation.authoring.curriculum_request.model_dump(
        mode="json"
    )


def test_observation_evidence_and_profile_harnesses_round_trip_profile_writeback():
    student_id = uuid4()
    profile = LearnerProfile.model_validate(
        build_profile(student_id, frustration="none", total_load=0.2)
    )
    profile_store = _ProfileStore(profile)
    observation_store = _ObservationStore()
    inferred_state = InferredLearnerState(
        student_id=student_id,
        affective_state=profile.affective_state.model_copy(update={"frustration": "medium"}),
        cognitive_load=profile.cognitive_load.model_copy(update={"total_load": 0.61}),
        metacognitive_state=profile.metacognitive_state.model_copy(
            update={"confidence_calibration": 0.32}
        ),
        observation_count=1,
    )
    calibration = LearnerStateCalibrationResult(
        state=inferred_state,
        signal="negative",
        source="test",
        confidence=0.66,
        matched_run_count=1,
        current_evidence_signal="overload",
        current_evidence_confidence=0.7,
        applied=True,
    )
    inferred_traits = {
        "processing_speed": CognitiveTraitScore(value=0.44, confidence=0.61)
    }
    observation_updater = _ObservationProfileUpdater()
    assessment_harness = AssessmentEvidenceHarness(
        profile_store=profile_store,
        observation_store=observation_store,
        state_inference_service=_StateInferenceService(inferred_state),
        learner_state_calibrator=_LearnerStateCalibrator(calibration),
        cognitive_trait_inference_service=_CognitiveTraitInferenceService(
            inferred_traits
        ),
        socratic_assessment_service=None,
    )
    learner_profile_harness = LearnerProfileHarness(
        profile_store=profile_store,
        observation_profile_updater=observation_updater,
        socratic_profile_updater=_SocraticProfileUpdater(),
    )
    observation = LearnerObservationCreate(
        response_time_ms=25000,
        hints_used=2,
        error_count=2,
        pause_count=2,
        modality_switches=1,
        completed=False,
        target_kc_ids=["KC-1"],
    )

    evidence = assessment_harness.record_observation_evidence(
        RecordObservationEvidenceCommand(
            student_id=student_id,
            observation=observation,
        )
    )
    result = learner_profile_harness.apply_observation_evidence(
        ApplyObservationEvidenceCommand(evidence=evidence)
    )

    assert evidence.profile == profile
    assert evidence.calibration.signal == "negative"
    assert observation_updater.calls
    assert result.profile == profile_store.profile
    assert result.profile.cognitive_traits["processing_speed"].value == 0.44
    assert result.mastery_update.kc_mastery_updates == {"KC-1": 0.72}
