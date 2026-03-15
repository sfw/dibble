from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuthIdentity(BaseModel):
    principal_id: str
    role: str
    auth_scheme: str = "api_key"


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    identity: AuthIdentity


class AuthTokenClaims(BaseModel):
    sub: str
    role: str
    iat: int
    exp: int
    iss: str


class AuthSession(BaseModel):
    identity: AuthIdentity
    authenticated_at: datetime | None = None
    expires_at: datetime | None = None
