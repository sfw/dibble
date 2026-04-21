from __future__ import annotations

from typing import Protocol
from uuid import UUID

from dibble.models.assignment import Assignment
from dibble.models.auth import User
from dibble.models.household import (
    Household,
    LearnerRelationshipState,
    ParentNotification,
)
from dibble.models.classroom import Classroom, ClassroomUpsert
from dibble.models.classroom_membership import (
    ClassroomMembership,
    ClassroomMembershipRole,
    ClassroomMembershipUpsert,
)
from dibble.models.course import Course, CourseUpsert
from dibble.models.curriculum import (
    KnowledgeComponent,
    KnowledgeComponentUpsert,
    Outcome,
    OutcomeUpsert,
    Strand,
    StrandUpsert,
)
from dibble.models.curriculum_intake import (
    AlignmentEdge,
    AlignmentReviewDecision,
    CurriculumFramework,
    FrameworkImport,
    FrameworkImportArtifact,
    PublishedCurriculumSnapshot,
)
from dibble.models.assessment import SocraticAssessmentSession
from dibble.models.generation import (
    CurriculumContentKey,
    GeneratedContent,
    GenerationRequest,
    CurriculumLibraryEntry,
    ModalityRoutingPrior,
    PredictiveWarmSweepResult,
    PredictiveWarmTask,
)
from dibble.models.observations import LearnerObservation, LearnerObservationCreate
from dibble.models.planning import LearnerGoal, TrajectoryPlan
from dibble.models.profile import LearnerProfile
from dibble.models.remediation import RemediationWorkflowSession
from dibble.models.session_control import SessionControlState
from dibble.models.session_adaptation import WithinSessionControllerState
from dibble.models.telemetry import (
    AuditEvent,
    ProviderHealthEvent,
    ProviderStatusSnapshot,
)
from dibble.services.auth_sessions import StoredAuthSession
from dibble.services.provider_health import ProviderRoutingSnapshot
from dibble.services.retrieval.embedding_store import StoredEmbedding


class AssignmentStore(Protocol):
    def upsert(self, assignment: Assignment) -> Assignment: ...
    def get(self, assignment_id: str) -> Assignment | None: ...
    def list_for_student(
        self, *, student_id: str, limit: int = 20, offset: int = 0
    ) -> list[Assignment]: ...
    def count_for_student(self, *, student_id: str) -> int: ...
    def list_for_section(
        self, *, section_id: str, limit: int = 50, offset: int = 0
    ) -> list[Assignment]: ...
    def list_for_teacher(
        self, *, teacher_id: str, limit: int = 50, offset: int = 0
    ) -> list[Assignment]: ...


class ProfileStore(Protocol):
    def upsert(self, profile: LearnerProfile) -> LearnerProfile: ...
    def get(self, student_id: UUID) -> LearnerProfile | None: ...
    def list_ids(self) -> list[str]: ...


class LearnerGoalStore(Protocol):
    def upsert(self, goal: LearnerGoal) -> LearnerGoal: ...
    def get(self, goal_id: str) -> LearnerGoal | None: ...
    def list_for_student(self, *, student_id: UUID) -> list[LearnerGoal]: ...
    def get_active_for_student(self, *, student_id: UUID) -> LearnerGoal | None: ...


class TrajectoryStore(Protocol):
    def upsert(self, trajectory: TrajectoryPlan) -> TrajectoryPlan: ...
    def get(self, trajectory_id: str) -> TrajectoryPlan | None: ...
    def list_for_goal(self, *, goal_id: str) -> list[TrajectoryPlan]: ...
    def get_active_for_student(self, *, student_id: UUID) -> TrajectoryPlan | None: ...


class SessionControlStore(Protocol):
    def upsert(self, session: SessionControlState) -> SessionControlState: ...
    def get(self, learning_session_id: str) -> SessionControlState | None: ...
    def get_active_for_student(
        self, *, student_id: UUID
    ) -> SessionControlState | None: ...


class ObservationStore(Protocol):
    def append(
        self, *, student_id: str, observation: LearnerObservationCreate
    ) -> LearnerObservation: ...
    def list_recent(
        self, *, student_id: str, limit: int = 20
    ) -> list[LearnerObservation]: ...


class OutcomeStore(Protocol):
    def upsert(self, outcome: OutcomeUpsert) -> Outcome: ...
    def get(self, outcome_id: str) -> Outcome | None: ...
    def list(self) -> list[Outcome]: ...


class StrandStore(Protocol):
    def upsert(self, strand: StrandUpsert) -> Strand: ...
    def get(self, strand_id: str) -> Strand | None: ...
    def list(self) -> list[Strand]: ...
    def list_for_course(self, course_id: str) -> list[Strand]: ...


class ClassroomStore(Protocol):
    def upsert(self, classroom: ClassroomUpsert) -> Classroom: ...
    def get(self, classroom_id: str) -> Classroom | None: ...
    def list(self) -> list[Classroom]: ...


class CourseStore(Protocol):
    def upsert(self, course: CourseUpsert) -> Course: ...
    def get(self, course_id: str) -> Course | None: ...
    def list(self) -> list[Course]: ...


class CurriculumFrameworkStore(Protocol):
    def upsert(self, framework: CurriculumFramework) -> CurriculumFramework: ...
    def get(self, framework_id: str) -> CurriculumFramework | None: ...
    def list(self) -> list[CurriculumFramework]: ...


class FrameworkImportStore(Protocol):
    def upsert(self, framework_import: FrameworkImport) -> FrameworkImport: ...
    def get(self, import_id: str) -> FrameworkImport | None: ...
    def list(self) -> list[FrameworkImport]: ...
    def list_for_framework(self, framework_id: str) -> list[FrameworkImport]: ...
    def find_by_fingerprint(
        self, *, framework_id: str, source_fingerprint: str
    ) -> FrameworkImport | None: ...


class FrameworkImportArtifactStore(Protocol):
    def upsert(self, artifact: FrameworkImportArtifact) -> FrameworkImportArtifact: ...
    def get(self, artifact_id: str) -> FrameworkImportArtifact | None: ...
    def list_for_import(self, import_id: str) -> list[FrameworkImportArtifact]: ...


class PublishedCurriculumSnapshotStore(Protocol):
    def upsert(
        self, snapshot: PublishedCurriculumSnapshot
    ) -> PublishedCurriculumSnapshot: ...
    def get(self, snapshot_id: str) -> PublishedCurriculumSnapshot | None: ...
    def list(self) -> list[PublishedCurriculumSnapshot]: ...
    def get_for_import(self, import_id: str) -> PublishedCurriculumSnapshot | None: ...


class AlignmentEdgeStore(Protocol):
    def upsert(self, edge: AlignmentEdge) -> AlignmentEdge: ...
    def get(self, edge_id: str) -> AlignmentEdge | None: ...
    def list(self) -> list[AlignmentEdge]: ...


class AlignmentReviewDecisionStore(Protocol):
    def append(self, decision: AlignmentReviewDecision) -> AlignmentReviewDecision: ...
    def list_for_edge(self, edge_id: str) -> list[AlignmentReviewDecision]: ...


class ClassroomMembershipStore(Protocol):
    def upsert(self, membership: ClassroomMembershipUpsert) -> ClassroomMembership: ...
    def replace_for_classroom(
        self,
        *,
        classroom_id: str,
        role: ClassroomMembershipRole,
        user_ids: list[str],
    ) -> list[ClassroomMembership]: ...
    def replace_for_user(
        self,
        *,
        user_id: str,
        role: ClassroomMembershipRole,
        section_ids: list[str],
    ) -> list[ClassroomMembership]: ...
    def list_classroom_user_ids(
        self,
        classroom_id: str,
        *,
        role: ClassroomMembershipRole | None = None,
    ) -> list[str]: ...
    def list_user_section_ids(
        self,
        user_id: str,
        *,
        role: ClassroomMembershipRole | None = None,
    ) -> list[str]: ...
    def delete_for_user(self, user_id: str) -> None: ...


class KnowledgeComponentStore(Protocol):
    def upsert(self, component: KnowledgeComponentUpsert) -> KnowledgeComponent: ...
    def get(self, kc_id: str) -> KnowledgeComponent | None: ...
    def list(self) -> list[KnowledgeComponent]: ...
    def list_prerequisites(self, kc_id: str) -> list[KnowledgeComponent]: ...


class AuditStore(Protocol):
    def append(
        self,
        *,
        event_type: str,
        status: str,
        student_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> AuditEvent: ...

    def list(self, *, limit: int = 50) -> list[AuditEvent]: ...


class GeneratedContentStore(Protocol):
    def upsert(
        self, *, cache_key: str, content: GeneratedContent
    ) -> GeneratedContent: ...
    def get(self, *, generation_id: str) -> GeneratedContent | None: ...
    def get_fresh(self, *, cache_key: str) -> GeneratedContent | None: ...
    def refresh(self, *, content: GeneratedContent) -> GeneratedContent: ...
    def list_recent(self, *, limit: int = 50) -> list[GeneratedContent]: ...
    def list_recent_for_student(
        self,
        *,
        student_id: str,
        limit: int = 20,
        offset: int = 0,
        include_predictive_warm: bool = False,
    ) -> list[GeneratedContent]: ...
    def expire_predictive_content(
        self,
        *,
        student_id: str | None,
        target_kc_ids: list[str],
        target_lo_ids: list[str],
        learning_session_id: str | None = None,
    ) -> int: ...
    def stats(self) -> dict[str, int]: ...


class CurriculumContentLibraryStore(Protocol):
    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None: ...

    def list_candidate_entries(
        self,
        *,
        key: CurriculumContentKey,
        limit: int = 20,
    ) -> list[CurriculumLibraryEntry]: ...

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry: ...

    def record_outcome(
        self,
        *,
        source_generation_id: str,
        outcome_score: float,
        engagement_score: float | None,
        progress_score: float | None,
    ) -> list[CurriculumLibraryEntry]: ...


class ModalityRoutingPriorStore(Protocol):
    def upsert(self, prior: ModalityRoutingPrior) -> ModalityRoutingPrior: ...
    def get(
        self,
        *,
        learner_id: UUID,
        scope: str,
        prior_key: str,
        context_key: str,
    ) -> ModalityRoutingPrior | None: ...
    def list_for_learner(self, *, learner_id: UUID) -> list[ModalityRoutingPrior]: ...


class PredictiveWarmTaskStore(Protocol):
    def enqueue(self, *, request: GenerationRequest) -> PredictiveWarmTask | None: ...
    def sweep(self, *, limit: int = 200) -> PredictiveWarmSweepResult: ...
    def claim_pending(
        self,
        *,
        limit: int = 10,
        claim_owner: str = "scheduler",
        claim_mode: str = "pending_drain",
        claim_reason: str = "eligible queue backlog",
        stale_recovered_task_ids: list[str] | None = None,
    ) -> list[PredictiveWarmTask]: ...
    def claim_tasks(
        self,
        *,
        task_ids: list[str],
        claim_owner: str = "scheduler",
        claim_mode: str = "targeted",
        claim_reason: str = "targeted queue claim",
        stale_recovered_task_ids: list[str] | None = None,
    ) -> list[PredictiveWarmTask]: ...
    def mark_completed(self, *, task_id: str) -> None: ...
    def mark_failed(self, *, task_id: str, error: str) -> None: ...
    def defer_retry(self, *, task_id: str, error: str) -> PredictiveWarmTask | None: ...
    def cancel_pending(
        self,
        *,
        student_id: str | None,
        target_kc_ids: list[str],
        target_lo_ids: list[str],
        learning_session_id: str | None = None,
    ) -> int: ...
    def stats(self) -> dict[str, int | None]: ...


class EmbeddingStore(Protocol):
    def get(self, resource_id: str) -> StoredEmbedding | None: ...
    def upsert(
        self, *, resource_id: str, vector: list[float], source_updated_at: str
    ) -> StoredEmbedding: ...


class ProviderHealthStore(Protocol):
    def append(
        self,
        *,
        provider_name: str,
        status: str,
        detail: dict[str, object] | None = None,
    ) -> ProviderHealthEvent: ...
    def list(self, *, limit: int = 100) -> list[ProviderHealthEvent]: ...
    def latest_statuses(self) -> list[ProviderStatusSnapshot]: ...
    def routing_snapshots(
        self, *, provider_names: list[str] | None = None, limit: int = 500
    ) -> list[ProviderRoutingSnapshot]: ...


class SocraticSessionStore(Protocol):
    def upsert(
        self, session: SocraticAssessmentSession
    ) -> SocraticAssessmentSession: ...
    def get(self, session_id: str) -> SocraticAssessmentSession | None: ...
    def list_recent_for_student(
        self, *, student_id: str, limit: int = 20, offset: int = 0
    ) -> list[SocraticAssessmentSession]: ...


class RemediationSessionStore(Protocol):
    def upsert(
        self, session: RemediationWorkflowSession
    ) -> RemediationWorkflowSession: ...
    def get(self, session_id: str) -> RemediationWorkflowSession | None: ...
    def list_recent_for_student(
        self, *, student_id: str, limit: int = 20, offset: int = 0
    ) -> list[RemediationWorkflowSession]: ...


class WithinSessionControllerStore(Protocol):
    def upsert(
        self, session: WithinSessionControllerState
    ) -> WithinSessionControllerState: ...
    def get(self, learning_session_id: str) -> WithinSessionControllerState | None: ...


class UserStore(Protocol):
    def create(self, user: User) -> User: ...
    def get(self, user_id: str) -> User | None: ...
    def get_by_api_key_hash(self, api_key_hash: str) -> User | None: ...
    def get_by_passphrase_hash(self, passphrase_hash: str) -> User | None: ...
    def list(self) -> list[User]: ...
    def update(self, user: User) -> User: ...
    def delete(self, user_id: str) -> bool: ...
    def count(self) -> int: ...


class HouseholdStore(Protocol):
    def upsert(self, household: Household) -> Household: ...
    def get(self, household_id: str) -> Household | None: ...
    def get_by_parent_user_id(self, parent_user_id: str) -> Household | None: ...


class LearnerRelationshipStateStore(Protocol):
    def upsert(self, state: LearnerRelationshipState) -> LearnerRelationshipState: ...
    def get(
        self, *, household_id: str, learner_id: str
    ) -> LearnerRelationshipState | None: ...
    def list_for_household(
        self, *, household_id: str
    ) -> list[LearnerRelationshipState]: ...


class ParentNotificationStore(Protocol):
    def upsert(self, notification: ParentNotification) -> ParentNotification: ...
    def list_for_household(self, *, household_id: str) -> list[ParentNotification]: ...
    def get(self, notification_id: str) -> ParentNotification | None: ...


class AuthSessionStore(Protocol):
    def get(self, session_id: str) -> StoredAuthSession | None: ...
    def upsert(self, session: StoredAuthSession) -> StoredAuthSession: ...
    def revoke(self, session_id: str, *, revoked_at: str) -> None: ...
