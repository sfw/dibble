from __future__ import annotations

from pydantic import BaseModel


class AuthIdentity(BaseModel):
    principal_id: str
    role: str
    auth_scheme: str = "api_key"
