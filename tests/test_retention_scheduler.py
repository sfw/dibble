from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from dibble.models.assessment import SocraticEvidenceStrength
from dibble.models.curriculum import KnowledgeComponent, Outcome
from dibble.models.observations import (
    LearnerObservation,
    ObservationSupportLevel,
    ObservationTaskType,
)
from dibble.models.planning import (
    PlanningAdaptationState,
    PlanningConceptClusterMarker,
    PlanningEvidenceStrength,
    PlanningRecoveryPattern,
    TrajectoryRiskLevel,
)
from dibble.models.profile import (
    KnowledgeState,
    LearnerCurriculumProgressionSummary,
    LearnerFlowSummary,
    LearnerProfile,
    OutcomeProgressSummary,
)
from dibble.models.retention import (
    RetentionReviewCandidate,
    RetentionReviewReason,
    RetentionReviewStatus,
    RetentionStrengthTier,
    RetentionSuppressionContext,
)
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learner_progression_service import LearnerProgressionService
from dibble.services.observation_profile_update import ObservationProfileUpdateResult
from dibble.services.planning_adaptation import PlanningAdaptationService
from dibble.services.retention_review_candidate_store import (
    SQLiteRetentionReviewCandidateStore,
)
from dibble.services.retention_scheduler import RetentionSchedulerService
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


class _FakeRetentionScheduler:
    def __init__(self) -> None:
        self.progression_calls: list[LearnerCurriculumProgressionSummary] = []
        self.planning_calls: list[PlanningAdaptationState] = []

    def nominate_from_progression_summary(
        self, *, learner_id: UUID, progression: LearnerCurriculumProgressionSummary
    ) -> None:
        self.progression_calls.append(progression)

    def nominate_from_planning_state(
        self, *, learner_id: UUID, planning_state: PlanningAdaptationState
    ) -> None:
        self.planning_calls.append(planning_state)


class _ProfileStore:
    def __init__(self, profile: LearnerProfile) -> None:
        self.profile = profile

    def get(self, student_id: UUID) -> LearnerProfile:
        return self.profile


class _OutcomeStore:
    def __init__(self, outcomes: list[Outcome]) -> None:
        self.outcomes = outcomes

    def list(self) -> list[Outcome]:
        return self.outcomes


class _KnowledgeComponentStore:
    def __init__(self, components: list[KnowledgeComponent]) -> None:
        self.components = components

    def list(self) -> list[KnowledgeComponent]:
        return self.components


class _LearnerFlowService:
    def build_for_student(self, *, student_id: UUID) -> LearnerFlowSummary:
        return LearnerFlowSummary()


def _service(tmp_path):
    database_path = str(tmp_path / "retention.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    store = SQLiteRetentionReviewCandidateStore(conn)
    return RetentionSchedulerService(candidate_store=store), database_path


def _observation(student_id: UUID) -> LearnerObservation:
    return LearnerObservation(
        observation_id="obs-1",
        student_id=student_id,
        response_time_ms=20_000,
        completed=True,
        confidence=0.84,
        hints_used=0,
        error_count=0,
        task_type=ObservationTaskType.practice,
        support_level=ObservationSupportLevel.low,
        target_kc_ids=["KC-1"],
        created_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )


def test_retention_scheduler_nominates_from_strengthened_kc_writeback(tmp_path):
    service, _ = _service(tmp_path)
    student_id = uuid4()
    reference_time = datetime(2026, 6, 8, 12, tzinfo=timezone.utc)
    mastery_update = ObservationProfileUpdateResult(
        profile=None,  # type: ignore[arg-type]
        applied=True,
        inferred_mastery=0.82,
        evidence_strength=SocraticEvidenceStrength.demonstrated,
        kc_mastery_updates={"KC-1": 0.78},
        durable_mastery_signal="durable_mastery",
        durable_mastery_confidence=0.7,
        average_recent_observed_mastery=0.82,
    )

    result = service.nominate_from_observation_writeback(
        learner_id=student_id,
        observation=_observation(student_id),
        mastery_update=mastery_update,
        reference_time=reference_time,
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.review_reason == RetentionReviewReason.strengthened_kc_writeback
    assert candidate.retention_strength_tier == RetentionStrengthTier.light
    assert candidate.kc_ids == ["KC-1"]
    assert candidate.due_at == reference_time + timedelta(days=4)


def test_retention_scheduler_suppresses_active_repair_and_duplicate_clusters(tmp_path):
    service, _ = _service(tmp_path)
    student_id = uuid4()
    reference_time = datetime(2026, 6, 8, 12, tzinfo=timezone.utc)
    candidate = RetentionReviewCandidate(
        candidate_id="cand-1",
        learner_id=student_id,
        kc_ids=["KC-1", "KC-2"],
        review_reason=RetentionReviewReason.concept_cluster_risk,
        retention_strength_tier=RetentionStrengthTier.standard,
        due_at=reference_time + timedelta(days=2),
    )

    suppressed = service.upsert_candidates_for_student(
        learner_id=student_id,
        candidates=[candidate],
        suppression_context=RetentionSuppressionContext(active_repair_kc_ids=["KC-2"]),
    )

    assert suppressed.candidates == []
    assert len(suppressed.suppressed) == 1
    assert suppressed.suppressed[0].status == RetentionReviewStatus.suppressed
    assert service.scheduled_reviews_for_student(learner_id=student_id) == []

    first = service.upsert_candidates_for_student(
        learner_id=student_id,
        candidates=[candidate],
    )
    duplicate = candidate.model_copy(
        update={
            "candidate_id": "cand-duplicate",
            "retention_strength_tier": RetentionStrengthTier.urgent,
            "due_at": reference_time + timedelta(days=1),
        }
    )
    second = service.upsert_candidates_for_student(
        learner_id=student_id,
        candidates=[duplicate],
    )

    assert len(first.candidates) == 1
    assert len(second.candidates) == 1
    scheduled = service.scheduled_reviews_for_student(
        learner_id=student_id,
        now=reference_time,
    )
    assert len(scheduled) == 1
    assert scheduled[0].candidate_id == "cand-1"
    assert scheduled[0].retention_strength_tier == RetentionStrengthTier.urgent


def test_retention_scheduler_queries_due_vs_scheduled_reviews(tmp_path):
    service, _ = _service(tmp_path)
    student_id = uuid4()
    now = datetime(2026, 6, 8, 12, tzinfo=timezone.utc)
    due_candidate = RetentionReviewCandidate(
        candidate_id="due-cand",
        learner_id=student_id,
        kc_ids=["KC-DUE"],
        review_reason=RetentionReviewReason.outcome_near_mastered,
        retention_strength_tier=RetentionStrengthTier.standard,
        due_at=now - timedelta(minutes=5),
    )
    scheduled_candidate = RetentionReviewCandidate(
        candidate_id="scheduled-cand",
        learner_id=student_id,
        kc_ids=["KC-LATER"],
        review_reason=RetentionReviewReason.outcome_mastered,
        retention_strength_tier=RetentionStrengthTier.light,
        due_at=now + timedelta(days=1),
    )

    service.upsert_candidates_for_student(
        learner_id=student_id,
        candidates=[due_candidate, scheduled_candidate],
    )

    due = service.due_reviews_for_student(learner_id=student_id, now=now)
    scheduled = service.scheduled_reviews_for_student(learner_id=student_id, now=now)

    assert [item.candidate_id for item in due] == ["due-cand"]
    assert due[0].status == RetentionReviewStatus.due
    assert [item.candidate_id for item in scheduled] == ["scheduled-cand"]


def test_retention_scheduler_persists_and_reloads_candidates(tmp_path):
    service, database_path = _service(tmp_path)
    student_id = uuid4()
    now = datetime(2026, 6, 8, 12, tzinfo=timezone.utc)

    service.nominate_from_planning_state(
        learner_id=student_id,
        reference_time=now,
        planning_state=PlanningAdaptationState(
            concept_cluster_markers=[
                PlanningConceptClusterMarker(
                    cluster_key="KC-1|KC-2",
                    label="KC-1, KC-2",
                    target_kc_ids=["KC-1", "KC-2"],
                    evidence_strength=PlanningEvidenceStrength.emerging,
                    risk_level=TrajectoryRiskLevel.high,
                    sample_count=4,
                    stall_count=2,
                    recovery_success_count=1,
                    average_outcome_score=0.61,
                )
            ],
            recovery_patterns=[
                PlanningRecoveryPattern(
                    pattern_key="practice:repair",
                    label="Practice repair",
                    evidence_strength=PlanningEvidenceStrength.emerging,
                    sample_count=2,
                    success_count=1,
                    success_rate=0.5,
                    average_outcome_score=0.68,
                    cluster_key="KC-3",
                    target_kc_ids=["KC-3"],
                )
            ],
        ),
    )

    reloaded_conn = create_connection(database_path)
    reloaded = RetentionSchedulerService(
        candidate_store=SQLiteRetentionReviewCandidateStore(reloaded_conn)
    )
    scheduled = reloaded.scheduled_reviews_for_student(
        learner_id=student_id,
        now=now,
    )

    assert len(scheduled) == 2
    assert {item.review_reason for item in scheduled} == {
        RetentionReviewReason.concept_cluster_risk,
        RetentionReviewReason.recovery_after_stall,
    }


def test_retention_scheduler_nominates_near_mastered_progression_outcome(tmp_path):
    service, _ = _service(tmp_path)
    student_id = uuid4()
    now = datetime(2026, 6, 8, 12, tzinfo=timezone.utc)
    progression = LearnerCurriculumProgressionSummary(
        status="ready_for_next_outcome",
        ready_outcomes=[
            OutcomeProgressSummary(
                outcome_id="OUT-1",
                title="Add fractions",
                state="ready",
                knowledge_component_ids=["KC-1", "KC-2"],
                mastery_ratio=0.78,
            )
        ],
    )

    result = service.nominate_from_progression_summary(
        learner_id=student_id,
        progression=progression,
        reference_time=now,
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].review_reason == RetentionReviewReason.outcome_near_mastered
    assert result.candidates[0].outcome_id == "OUT-1"


def test_progression_build_nominates_retention_candidates_from_outcome_state():
    student_id = uuid4()
    retention_scheduler = _FakeRetentionScheduler()
    service = LearnerProgressionService(
        profile_store=_ProfileStore(
            LearnerProfile(
                student_id=student_id,
                grade_level="5",
                knowledge_state=KnowledgeState(kc_mastery={"KC-1": 0.84}),
            )
        ),
        outcome_store=_OutcomeStore(
            [
                Outcome(
                    outcome_id="OUT-1",
                    title="Equivalent fractions",
                    strand_id="STRAND-1",
                    grade_level="5",
                    subject="math",
                    description="Explain equivalent fractions.",
                    knowledge_component_ids=["KC-1"],
                )
            ]
        ),
        knowledge_component_store=_KnowledgeComponentStore(
            [
                KnowledgeComponent(
                    kc_id="KC-1",
                    name="Equivalent fractions",
                    outcome_id="OUT-1",
                    grade_level="5",
                    subject="math",
                )
            ]
        ),
        learner_flow_service=_LearnerFlowService(),
        retention_scheduler_service=retention_scheduler,  # type: ignore[arg-type]
    )

    progression = service.build_for_student(student_id=student_id)

    assert progression is not None
    assert progression.mastered_outcome_count == 1
    assert len(retention_scheduler.progression_calls) == 1
    assert retention_scheduler.progression_calls[0].mastered_outcome_count == 1


def test_planning_adaptation_build_nominates_retention_candidates_from_risk_state(
    tmp_path,
):
    database_path = str(tmp_path / "planning-retention.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    retention_scheduler = _FakeRetentionScheduler()
    for index, score in enumerate([0.42, 0.48, 0.69, 0.7]):
        audit_store.append(
            event_type="learning.run.summary",
            status="success",
            student_id=str(student_id),
            payload={
                "target_kc_ids": ["KC-1", "KC-2"],
                "run_outcome_score": score,
                "learning_session_id": f"session-{index}",
            },
        )

    service = PlanningAdaptationService(
        audit_store=audit_store,
        retention_scheduler_service=retention_scheduler,  # type: ignore[arg-type]
    )

    state = service.build_state(student_id=student_id)

    assert state.concept_cluster_markers
    assert len(retention_scheduler.planning_calls) == 1
    assert retention_scheduler.planning_calls[0].concept_cluster_markers
