from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from dibble.models.auth import AuthIdentity
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import RouterPlugin
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.auth import (
    AuthService,
    AuthenticationError,
    AuthorizationError,
)
from dibble.services.content_warmer import ContentWarmer
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.socratic_assessment import SocraticAssessmentService
from dibble.services.socratic_profile_update import SocraticProfileUpdater
from dibble.services.socratic_session_store import SQLiteSocraticSessionStore
from dibble.services.state_inference import LearnerStateInferenceService
from dibble.services.telemetry import TelemetryService


class ApiServices(Protocol):
    profile_store: SQLiteProfileStore
    curriculum_store: SQLiteCurriculumStore
    knowledge_component_store: SQLiteKnowledgeComponentStore
    audit_store: SQLiteAuditStore
    observation_store: SQLiteObservationStore
    auth_service: AuthService
    telemetry_service: TelemetryService
    router_plugin: RouterPlugin
    generation_engine: GenerationEngine
    content_warmer: ContentWarmer
    remediation_planner: RemediationPlanner
    socratic_assessment_service: SocraticAssessmentService
    socratic_profile_updater: SocraticProfileUpdater
    socratic_session_store: SQLiteSocraticSessionStore
    state_inference_service: LearnerStateInferenceService


@dataclass(slots=True)
class ApiContext:
    services: ApiServices

    def require_access(self, *allowed_roles: str):
        async def dependency(
            request: Request,
            api_key: str | None = Header(default=None, alias=self.services.auth_service.header_name),
            authorization: str | None = Header(default=None, alias="Authorization"),
        ) -> AuthIdentity:
            bearer_token = None
            if authorization and authorization.lower().startswith("bearer "):
                bearer_token = authorization[7:].strip()
            try:
                session = self.services.auth_service.authorize(
                    provided_key=api_key,
                    bearer_token=bearer_token,
                    allowed_roles=tuple(allowed_roles) or ("viewer",),
                )
                identity = session.identity
                request.state.auth_identity = identity
                return identity
            except AuthenticationError as exc:
                self.services.audit_store.append(
                    event_type="auth.request",
                    status="denied",
                    payload={
                        "path": request.url.path,
                        "method": request.method,
                        "header_name": self.services.auth_service.header_name,
                        "required_roles": list(allowed_roles or ("viewer",)),
                    },
                )
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
            except AuthorizationError as exc:
                identity = self.services.auth_service.authenticate(api_key)
                self.services.audit_store.append(
                    event_type="auth.request",
                    status="forbidden",
                    payload={
                        "path": request.url.path,
                        "method": request.method,
                        "header_name": self.services.auth_service.header_name,
                        "principal_id": identity.principal_id,
                        "role": identity.role,
                        "required_roles": list(allowed_roles or ("viewer",)),
                    },
                )
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

        return dependency

    def deps(self, *roles: str):
        if not self.services.auth_service.enabled:
            return []
        return [Depends(self.require_access(*roles))]


def missing_profile(student_id: UUID) -> LearnerProfile:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Learner profile not found for student_id {student_id}.",
    )
