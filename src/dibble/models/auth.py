from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuthIdentity(BaseModel):
    principal_id: str
    role: str
    auth_scheme: str = "api_key"


class AuthToken(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    identity: AuthIdentity


class AuthTokenClaims(BaseModel):
    sub: str
    role: str
    sid: str
    jti: str
    typ: str = "access"
    iat: int
    exp: int
    iss: str


class AuthSession(BaseModel):
    identity: AuthIdentity
    session_id: str | None = None
    authenticated_at: datetime | None = None
    expires_at: datetime | None = None


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class AuthRevokeRequest(BaseModel):
    refresh_token: str | None = None
