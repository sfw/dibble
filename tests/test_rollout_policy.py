from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from dibble.models.auth import User
from dibble.models.curriculum_intake import (
    CurriculumMigrationExecutionRequest,
    CurriculumMigrationPlan,
    MigrationAction,
    MigrationActionStatus,
    MigrationActionType,
    MigrationPlanStatus,
    MigrationRiskLevel,
    RuntimeEntityKind,
)
from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
    RequestedContentType,
)
from dibble.models.profile import LearnerProfile
from dibble.models.rollout import (
    AdaptationStrength,
    AutonomousSessionSuggestionGate,
    CloudLibraryPublishGate,
    CloudLibraryPublishMode,
    CloudLibraryReadGate,
    CloudLibraryReadMode,
    EvaluationBucket,
    ModalityAvailabilityMode,
    NonTextModalityGate,
    OutcomeDrivenAdaptationGate,
    RolloutCapability,
    RolloutPolicy,
    RolloutSimulationRequest,
    RolloutSimulationSubject,
)
from dibble.plugins.loader import build_modality_plugins
from dibble.services.harness.content_library import LibraryFirstCurriculumContentLibrary
from dibble.services.harness.curriculum_evolution import CurriculumEvolutionHarness
from dibble.services.harness.modality_routing import ModalityRoutingHarness
from dibble.services.rollout_decision_service import RolloutDecisionService
from tests.support import build_profile


class _MemoryRolloutPolicyStore:
    def __init__(self, policy: RolloutPolicy) -> None:
        self.policy = policy

    def get(self, policy_id: str = "default") -> RolloutPolicy | None:
        return self.policy if self.policy.policy_id == policy_id else None

    def upsert(self, policy: RolloutPolicy) -> RolloutPolicy:
        self.policy = policy
        return policy


class _UserStore:
    def __init__(self, users: list[User]) -> None:
        self._users = users

    def list(self) -> list[User]:
        return list(self._users)


class _StaticRouter:
    def route(self, profile: LearnerProfile, request: GenerationRequest) -> AdaptiveRouteDecision:
        return AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="guided",
            reasons=["test"],
        )


class _StubRemoteClient:
    def __init__(self) -> None:
        self.lookup_calls = 0
        self.publish_calls = 0

    def lookup(self, *, key):
        self.lookup_calls += 1
        return None

    def publish(self, *, entry):
        self.publish_calls += 1
        return entry


class _StubLocalClient:
    def __init__(self, entry=None) -> None:
        self.entry = entry
        self.publish_calls = 0

    def lookup(self, *, key):
        return self.entry

    def list_candidates(self, *, key, limit: int = 20):
        return [self.entry] if self.entry is not None else []

    def publish(self, *, entry):
        self.publish_calls += 1
        self.entry = entry
        return entry


class _PlanStore:
    def __init__(self, plan: CurriculumMigrationPlan) -> None:
        self.plan = plan

    def get(self, plan_id: str) -> CurriculumMigrationPlan | None:
        return self.plan if self.plan.plan_id == plan_id else None

    def upsert(self, plan: CurriculumMigrationPlan) -> CurriculumMigrationPlan:
        self.plan = plan
        return plan

    def list(self) -> list[CurriculumMigrationPlan]:
        return [self.plan]

    def get_for_diff(self, diff_id: str) -> CurriculumMigrationPlan | None:
        return self.plan if self.plan.diff_id == diff_id else None


@dataclass
class _NoopStore:
    def get(self, *args, **kwargs):
        return None

    def list(self):
        return []

    def upsert(self, value):
        return value


def _policy_with_buckets(*, non_text_mode: ModalityAvailabilityMode) -> RolloutPolicy:
    return RolloutPolicy(
        behavior_gates=[
            AutonomousSessionSuggestionGate(fallback_behavior="no_session_suggestion"),
            CloudLibraryReadGate(
                fallback_behavior="local_library_only",
                mode=CloudLibraryReadMode.local_only,
            ),
            CloudLibraryPublishGate(
                fallback_behavior="local_only_hold",
                mode=CloudLibraryPublishMode.local_only,
            ),
            NonTextModalityGate(
                fallback_behavior="text_only_fallback",
                mode=non_text_mode,
            ),
            OutcomeDrivenAdaptationGate(
                fallback_behavior="observe_only",
                mode=AdaptationStrength.conservative,
            ),
        ],
        evaluation_buckets=[
            EvaluationBucket(bucket_id="control", label="Control", weight=50),
            EvaluationBucket(bucket_id="test", label="Test", weight=50),
        ],
    )


def _rollout_service(policy: RolloutPolicy, learner_id: str, household_id: str) -> RolloutDecisionService:
    user = User(
        user_id="learner-user",
        display_name="Avery",
        role="learner",
        learner_id=learner_id,
        household_id=household_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    return RolloutDecisionService(
        policy_store=_MemoryRolloutPolicyStore(policy),
        user_store=_UserStore([user]),
    )


def test_rollout_bucket_assignment_is_stable():
    learner_id = str(uuid4())
    household_id = "household-1"
    service = _rollout_service(
        _policy_with_buckets(non_text_mode=ModalityAvailabilityMode.full_multimodal),
        learner_id,
        household_id,
    )

    first = service.inspect_subject(learner_id=learner_id)
    second = service.inspect_subject(learner_id=learner_id)

    assert first.evaluation_bucket is not None
    assert second.evaluation_bucket is not None
    assert first.evaluation_bucket.bucket_id == second.evaluation_bucket.bucket_id
    assert first.decision_for(RolloutCapability.non_text_modalities) is not None


def test_rollout_policy_simulation_is_side_effect_free_and_matches_live_logic():
    learner_id = str(uuid4())
    household_id = "household-1"
    service = _rollout_service(
        _policy_with_buckets(non_text_mode=ModalityAvailabilityMode.full_multimodal),
        learner_id,
        household_id,
    )
    current_policy = service.get_policy()
    proposed_policy = current_policy.model_copy(
        update={
            "behavior_gates": [
                gate.model_copy(update={"mode": CloudLibraryReadMode.remote_preferred})
                if gate.capability == RolloutCapability.cloud_library_remote_read
                else gate
                for gate in current_policy.behavior_gates
            ]
        }
    )

    simulation = service.simulate_policy_change(
        RolloutSimulationRequest(
            proposed_policy=proposed_policy,
            subjects=[RolloutSimulationSubject(learner_id=learner_id)],
        )
    )
    live_proposed = RolloutDecisionService(
        policy_store=_MemoryRolloutPolicyStore(proposed_policy),
        user_store=_UserStore(
            [
                User(
                    user_id="learner-user",
                    display_name="Avery",
                    role="learner",
                    learner_id=learner_id,
                    household_id=household_id,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            ]
        ),
    ).inspect_subject(learner_id=learner_id)

    assert service.get_policy() == current_policy
    assert simulation.summary.changed_subject_count == 1
    assert simulation.summary.newly_risky_subject_count == 1
    assert simulation.summary.capability_change_counts[
        RolloutCapability.cloud_library_remote_read.value
    ] == 1
    diff = simulation.diffs[0]
    simulated_decision = diff.proposed_inspection.decision_for(
        RolloutCapability.cloud_library_remote_read
    )
    live_decision = live_proposed.decision_for(RolloutCapability.cloud_library_remote_read)
    assert simulated_decision is not None
    assert live_decision is not None
    assert simulated_decision.mode == live_decision.mode
    assert simulated_decision.enabled == live_decision.enabled


def test_modality_rollout_policy_falls_back_to_text():
    learner_uuid = uuid4()
    learner_id = str(learner_uuid)
    household_id = "household-1"
    service = _rollout_service(
        _policy_with_buckets(non_text_mode=ModalityAvailabilityMode.text_only),
        learner_id,
        household_id,
    )
    harness = ModalityRoutingHarness(
        router=_StaticRouter(),
        modality_plugins=build_modality_plugins(),
        rollout_decision_service=service,
    )
    profile = LearnerProfile.model_validate(build_profile(learner_uuid))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent=ContentIntent.explanation,
        requested_content_type=RequestedContentType.worked_example,
        curriculum_context=["Use a diagram to reteach equivalent fractions."],
    )

    inspection = harness.inspect(profile=profile, request=request)
    plan = harness.plan(profile=profile, request=request)

    assert inspection.selected_plugin_id == "diagram"
    assert inspection.effective_plugin_id == "text"
    assert inspection.policy_fallback_applied is True
    assert plan.directive.plugin_id == "text"
    assert plan.directive.modality == "text"


def test_cloud_library_policy_skips_remote_lookup_and_publish():
    learner_uuid = uuid4()
    learner_id = str(learner_uuid)
    household_id = "household-1"
    policy = RolloutPolicy(
        behavior_gates=[
            CloudLibraryReadGate(
                fallback_behavior="local_library_only",
                mode=CloudLibraryReadMode.local_only,
            ),
            CloudLibraryPublishGate(
                fallback_behavior="local_only_hold",
                mode=CloudLibraryPublishMode.local_only,
            ),
            NonTextModalityGate(
                fallback_behavior="text_only_fallback",
                mode=ModalityAvailabilityMode.full_multimodal,
            ),
            OutcomeDrivenAdaptationGate(
                fallback_behavior="observe_only",
                mode=AdaptationStrength.conservative,
            ),
            AutonomousSessionSuggestionGate(fallback_behavior="no_session_suggestion"),
        ],
        evaluation_buckets=[EvaluationBucket(bucket_id="baseline", label="Baseline", weight=100)],
    )
    service = _rollout_service(policy, learner_id, household_id)
    local_client = _StubLocalClient()
    remote_client = _StubRemoteClient()
    library = LibraryFirstCurriculumContentLibrary(
        local_client=local_client,
        remote_client=remote_client,
        rollout_decision_service=service,
    )
    profile = LearnerProfile.model_validate(build_profile(learner_uuid))
    request = GenerationRequest(
        student_id=profile.student_id,
        target_kc_ids=["KC-1"],
        intent=ContentIntent.explanation,
        requested_content_type=RequestedContentType.worked_example,
        curriculum_context=["Equivalent fractions"],
    )
    harness = ModalityRoutingHarness(router=_StaticRouter(), modality_plugins=build_modality_plugins())
    plan = harness.plan(profile=profile, request=request)
    from dibble.services.harness.policy import HarnessAuthoringPolicyBuilder
    from dibble.services.harness.request_adapter import CurriculumContentRequestAdapter
    from dibble.models.generation import (
        CurriculumContentKey,
        CurriculumLibraryEntry,
        GeneratedContent,
        GenerationMetadata,
        GenerationResponse,
        ModerationResult,
    )

    policy_builder = HarnessAuthoringPolicyBuilder()
    authoring_policy = policy_builder.build(profile=profile, request=request, route=plan.route)
    curriculum_request = CurriculumContentRequestAdapter().adapt(
        grade_level=profile.grade_level,
        request=request,
        policy=authoring_policy,
    )
    content_key = CurriculumContentKey(request=curriculum_request, route=plan.route, grounding=[])
    content = GeneratedContent(
        generation_id="gen-1",
        student_id="00000000-0000-0000-0000-000000000000",
        content_type="worked_example",
        request_context={"selected_content_type": "worked_example"},
        response=GenerationResponse(
            student_id="00000000-0000-0000-0000-000000000000",
            route=plan.route,
            blocks=[],
            curriculum_context=[],
            safety_notes=[],
        ),
        quality=GenerationMetadata(
            cache_hit=False,
            quality_score=1.0,
            validation_passed=True,
            moderation=ModerationResult(status="clear", stage="response"),
            generation_latency_ms=0,
        ),
    )

    assert library.get_fresh_entry(key=content_key, learner_id=learner_id) is None
    library.upsert_entry(
        entry=CurriculumLibraryEntry(content_key=content_key, content=content),
        learner_id=learner_id,
    )

    assert remote_client.lookup_calls == 0
    assert remote_client.publish_calls == 0
    assert local_client.publish_calls >= 1


def test_kill_switch_and_rollout_block_migration_execution():
    learner_id = str(uuid4())
    household_id = "household-1"
    policy = RolloutPolicy(
        behavior_gates=[
            CloudLibraryReadGate(
                fallback_behavior="local_library_only",
                mode=CloudLibraryReadMode.local_only,
            ),
            CloudLibraryPublishGate(
                fallback_behavior="local_only_hold",
                mode=CloudLibraryPublishMode.local_only,
            ),
            NonTextModalityGate(
                fallback_behavior="text_only_fallback",
                mode=ModalityAvailabilityMode.full_multimodal,
            ),
            OutcomeDrivenAdaptationGate(
                fallback_behavior="observe_only",
                mode=AdaptationStrength.conservative,
            ),
            AutonomousSessionSuggestionGate(fallback_behavior="no_session_suggestion"),
        ],
        evaluation_buckets=[EvaluationBucket(bucket_id="baseline", label="Baseline", weight=100)],
    )
    service = _rollout_service(policy, learner_id, household_id)
    plan = CurriculumMigrationPlan(
        plan_id="plan-1",
        diff_id="diff-1",
        source_snapshot_id="snap-1",
        target_snapshot_id="snap-2",
        status=MigrationPlanStatus.ready,
        actions=[
            MigrationAction(
                action_id="action-1",
                action_type=MigrationActionType.swap_provenance_only,
                entity_kind=RuntimeEntityKind.learner_goal,
                entity_id="goal-1",
                source_snapshot_id="snap-1",
                target_snapshot_id="snap-2",
                risk_level=MigrationRiskLevel.low,
                confidence=0.9,
                status=MigrationActionStatus.approved,
                rationale="Safe swap",
            )
        ],
    )
    harness = CurriculumEvolutionHarness(
        published_snapshot_store=_NoopStore(),
        framework_import_artifact_store=_NoopStore(),
        alignment_edge_store=_NoopStore(),
        curriculum_snapshot_diff_store=_NoopStore(),
        curriculum_impact_analysis_store=_NoopStore(),
        curriculum_migration_plan_store=_PlanStore(plan),
        profile_store=_NoopStore(),
        learner_goal_store=_NoopStore(),
        trajectory_store=_NoopStore(),
        assignment_store=_NoopStore(),
        classroom_store=_NoopStore(),
        course_store=_NoopStore(),
        curriculum_content_library_store=_NoopStore(),
        rollout_decision_service=service,
    )

    blocked = harness.execute_migration_plan(
        "plan-1",
        CurriculumMigrationExecutionRequest(executor_id="admin-1"),
    )

    assert blocked.plan_id == "plan-1"
    assert blocked.status == MigrationPlanStatus.ready
    assert blocked.actions[0].status == MigrationActionStatus.approved
