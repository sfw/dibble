from __future__ import annotations

from dataclasses import dataclass

from dibble.config import Settings


class AuthenticationError(RuntimeError):
    """Raised when a request is not authorized."""


@dataclass(slots=True)
class AuthService:
    enabled: bool = False
    api_keys: tuple[str, ...] = ()
    header_name: str = "X-API-Key"

    @classmethod
    def from_settings(cls, settings: Settings) -> "AuthService":
        return cls(
            enabled=settings.auth_enabled,
            api_keys=settings.auth_api_keys,
            header_name=settings.auth_header_name,
        )

    def authorize(self, provided_key: str | None) -> None:
        if not self.enabled:
            return
        if not self.api_keys:
            raise AuthenticationError("Authentication is enabled but no API keys are configured.")
        if provided_key not in self.api_keys:
            raise AuthenticationError("A valid API key is required for this endpoint.")
