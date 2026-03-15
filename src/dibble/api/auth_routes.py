from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status

from dibble.api.common import ApiContext
from dibble.models.auth import AuthIdentity, AuthRefreshRequest, AuthRevokeRequest, AuthToken
from dibble.services.auth import AuthenticationError, TokenConfigurationError


def build_auth_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.get("/auth/me", response_model=AuthIdentity, dependencies=context.deps("viewer"))
    def get_current_identity(request: Request) -> AuthIdentity:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            return services.auth_service.authenticate(None)
        return identity

    @router.post("/auth/token", response_model=AuthToken, dependencies=context.deps("viewer"))
    def issue_access_token(request: Request) -> AuthToken:
        identity = getattr(request.state, "auth_identity", None)
        if identity is None:
            return services.auth_service.issue_token(services.auth_service.authenticate(None))
        try:
            token = services.auth_service.issue_token(identity)
        except TokenConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        services.audit_store.append(
            event_type="auth.token",
            status="issued",
            payload={"principal_id": identity.principal_id, "role": identity.role},
        )
        return token

    @router.post("/auth/token/refresh", response_model=AuthToken)
    def refresh_access_token(payload: AuthRefreshRequest) -> AuthToken:
        try:
            token = services.auth_service.refresh_session(payload.refresh_token)
        except (AuthenticationError, TokenConfigurationError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        services.audit_store.append(
            event_type="auth.token",
            status="refreshed",
            payload={
                "principal_id": token.identity.principal_id,
                "role": token.identity.role,
            },
        )
        return token

    @router.post("/auth/token/revoke")
    def revoke_access_token(
        payload: AuthRevokeRequest | None = None,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> dict[str, str]:
        bearer_token = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer_token = authorization[7:].strip()

        try:
            services.auth_service.revoke_session(
                refresh_token=payload.refresh_token if payload is not None else None,
                bearer_token=bearer_token,
            )
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        services.audit_store.append(
            event_type="auth.token",
            status="revoked",
            payload={"mode": "refresh" if payload and payload.refresh_token else "bearer"},
        )
        return {"status": "revoked"}

    return router
