from __future__ import annotations

from dataclasses import dataclass

from dibble.config import Settings
from dibble.models.auth import AuthIdentity
from dibble.services.access_control import allows_role


class AuthenticationError(RuntimeError):
    """Raised when a request is not authorized."""


class AuthorizationError(RuntimeError):
    """Raised when an authenticated principal lacks a required role."""


@dataclass(frozen=True, slots=True)
class ApiKeyPrincipal:
    api_key: str
    principal_id: str
    role: str


@dataclass(slots=True)
class AuthService:
    enabled: bool = False
    principals: tuple[ApiKeyPrincipal, ...] = ()
    header_name: str = "X-API-Key"

    @classmethod
    def from_settings(cls, settings: Settings) -> "AuthService":
        return cls(
            enabled=settings.auth_enabled,
            principals=_build_principals(settings),
            header_name=settings.auth_header_name,
        )

    def authenticate(self, provided_key: str | None) -> AuthIdentity:
        if not self.enabled:
            return AuthIdentity(principal_id="anonymous", role="admin", auth_scheme="disabled")
        if not self.principals:
            raise AuthenticationError("Authentication is enabled but no API keys are configured.")

        for principal in self.principals:
            if provided_key == principal.api_key:
                return AuthIdentity(principal_id=principal.principal_id, role=principal.role)

        raise AuthenticationError("A valid API key is required for this endpoint.")

    def authorize(self, provided_key: str | None, *, allowed_roles: tuple[str, ...]) -> AuthIdentity:
        identity = self.authenticate(provided_key)
        if not allows_role(identity.role, allowed_roles):
            raise AuthorizationError("Your role does not allow access to this endpoint.")
        return identity


def _build_principals(settings: Settings) -> tuple[ApiKeyPrincipal, ...]:
    if settings.auth_principals:
        principals: list[ApiKeyPrincipal] = []
        for entry in settings.auth_principals:
            api_key, separator, remainder = entry.partition(":")
            principal_id, separator_two, role = remainder.partition(":")
            if not api_key or separator == "" or not principal_id or separator_two == "" or not role:
                continue
            principals.append(
                ApiKeyPrincipal(
                    api_key=api_key,
                    principal_id=principal_id,
                    role=role.lower(),
                )
            )
        if principals:
            return tuple(principals)

    return tuple(
        ApiKeyPrincipal(
            api_key=api_key,
            principal_id=f"principal-{index + 1}",
            role="admin",
        )
        for index, api_key in enumerate(settings.auth_api_keys)
    )
