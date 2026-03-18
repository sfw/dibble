from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from dibble.models.assessment import SocraticAssessmentSession
from dibble.models.generation import GeneratedContent
from dibble.models.profile import LearnerContinueAction, ProfileSummary
from dibble.models.remediation import RemediationWorkflowSession


class LearnerWorkspaceArtifact(BaseModel):
    kind: str = "idle"
    resource_id: str | None = None
    generation_id: str | None = None
    learning_session_id: str | None = None
    flow_type: str = "idle"
    status: str = "idle"
    current_phase: str = "idle"
    content_type: str | None = None
    rationale: str | None = None


class AffectiveSupportMessage(BaseModel):
    kind: str
    title: str
    detail: str


class LearnerWorkspace(BaseModel):
    student_id: UUID
    summary: ProfileSummary
    active_artifact: LearnerWorkspaceArtifact = Field(default_factory=LearnerWorkspaceArtifact)
    continue_action: LearnerContinueAction = Field(default_factory=LearnerContinueAction)
    affective_support: AffectiveSupportMessage | None = None
    generated_content: GeneratedContent | None = None
    remediation_session: RemediationWorkflowSession | None = None
    socratic_session: SocraticAssessmentSession | None = None
