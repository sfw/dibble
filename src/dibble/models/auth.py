from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuthIdentity(BaseModel):
    principal_id: str
    role: str
    auth_scheme: str = "api_key"
    learner_id: str | None = None
    teacher_id: str | None = None
    display_name: str | None = None
    classroom_ids: list[str] = Field(default_factory=list)


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
    learner_id: str | None = None
    teacher_id: str | None = None
    display_name: str | None = None
    classroom_ids: list[str] = Field(default_factory=list)


class AuthSession(BaseModel):
    identity: AuthIdentity
    session_id: str | None = None
    authenticated_at: datetime | None = None
    expires_at: datetime | None = None


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class AuthRevokeRequest(BaseModel):
    refresh_token: str | None = None


# ---------------------------------------------------------------------------
# User management models
# ---------------------------------------------------------------------------


class User(BaseModel):
    user_id: str
    display_name: str | None = None
    role: str
    api_key_hash: str | None = None
    passphrase_hash: str | None = None
    learner_id: str | None = None
    teacher_id: str | None = None
    classroom_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class UserCreateRequest(BaseModel):
    display_name: str | None = None
    role: str
    learner_id: str | None = None
    teacher_id: str | None = None
    classroom_ids: list[str] = Field(default_factory=list)


class UserCreateResponse(BaseModel):
    user_id: str
    credential: str
    display_name: str | None = None
    role: str


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    learner_id: str | None = None
    teacher_id: str | None = None
    classroom_ids: list[str] | None = None


class UserSummary(BaseModel):
    user_id: str
    display_name: str | None = None
    role: str
    learner_id: str | None = None
    teacher_id: str | None = None
    classroom_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class BulkUserCreateRequest(BaseModel):
    users: list[UserCreateRequest]


class BulkUserCreateResponse(BaseModel):
    created: list[UserCreateResponse]
