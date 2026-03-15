from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dibble.config import Settings
from dibble.models.auth import AuthIdentity, AuthSession, AuthToken, AuthTokenClaims
from dibble.services.access_control import allows_role


class AuthenticationError(RuntimeError):
    """Raised when a request is not authorized."""


class AuthorizationError(RuntimeError):
    """Raised when an authenticated principal lacks a required role."""


class TokenConfigurationError(RuntimeError):
    """Raised when bearer token features are requested without configuration."""


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
    token_secret: str | None = None
    token_issuer: str = "dibble"
    token_ttl_seconds: int = 3600

    @classmethod
    def from_settings(cls, settings: Settings) -> "AuthService":
        return cls(
            enabled=settings.auth_enabled,
            principals=_build_principals(settings),
            header_name=settings.auth_header_name,
            token_secret=settings.auth_token_secret,
            token_issuer=settings.auth_token_issuer,
            token_ttl_seconds=settings.auth_token_ttl_seconds,
        )

    def authenticate(self, provided_key: str | None) -> AuthIdentity:
        if not self.enabled:
            return AuthIdentity(principal_id="anonymous", role="admin", auth_scheme="disabled")
        if not self.principals:
            raise AuthenticationError("Authentication is enabled but no API keys are configured.")

        for principal in self.principals:
            if provided_key == principal.api_key:
                return AuthIdentity(principal_id=principal.principal_id, role=principal.role, auth_scheme="api_key")

        raise AuthenticationError("A valid API key is required for this endpoint.")

    def authenticate_request(self, *, provided_key: str | None, bearer_token: str | None) -> AuthSession:
        if bearer_token:
            return self.authenticate_bearer_token(bearer_token)

        identity = self.authenticate(provided_key)
        return AuthSession(identity=identity)

    def authorize(
        self,
        *,
        provided_key: str | None,
        bearer_token: str | None,
        allowed_roles: tuple[str, ...],
    ) -> AuthSession:
        session = self.authenticate_request(provided_key=provided_key, bearer_token=bearer_token)
        identity = session.identity
        if not allows_role(identity.role, allowed_roles):
            raise AuthorizationError("Your role does not allow access to this endpoint.")
        return session

    def issue_token(self, identity: AuthIdentity) -> AuthToken:
        if not self.token_secret:
            raise TokenConfigurationError("Bearer token issuance requires DIBBLE_AUTH_TOKEN_SECRET.")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.token_ttl_seconds)
        claims = AuthTokenClaims(
            sub=identity.principal_id,
            role=identity.role,
            iat=int(now.timestamp()),
            exp=int(expires_at.timestamp()),
            iss=self.token_issuer,
        )
        token = self._encode_token(claims)
        return AuthToken(
            access_token=token,
            expires_in=self.token_ttl_seconds,
            identity=AuthIdentity(
                principal_id=identity.principal_id,
                role=identity.role,
                auth_scheme="bearer",
            ),
        )

    def authenticate_bearer_token(self, token: str) -> AuthSession:
        claims = self._decode_token(token)
        authenticated_at = datetime.fromtimestamp(claims.iat, tz=timezone.utc)
        expires_at = datetime.fromtimestamp(claims.exp, tz=timezone.utc)
        return AuthSession(
            identity=AuthIdentity(
                principal_id=claims.sub,
                role=claims.role,
                auth_scheme="bearer",
            ),
            authenticated_at=authenticated_at,
            expires_at=expires_at,
        )

    def _encode_token(self, claims: AuthTokenClaims) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        encoded_header = _urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        encoded_payload = _urlsafe_b64encode(claims.model_dump_json().encode("utf-8"))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        signature = hmac.new(self.token_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        encoded_signature = _urlsafe_b64encode(signature)
        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    def _decode_token(self, token: str) -> AuthTokenClaims:
        if not self.token_secret:
            raise AuthenticationError("Bearer token authentication requires DIBBLE_AUTH_TOKEN_SECRET.")

        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationError("Bearer token is malformed.")

        encoded_header, encoded_payload, encoded_signature = parts
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        expected_signature = hmac.new(self.token_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_signature = _urlsafe_b64decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise AuthenticationError("Bearer token signature is invalid.")

        try:
            header = json.loads(_urlsafe_b64decode(encoded_header).decode("utf-8"))
            payload = json.loads(_urlsafe_b64decode(encoded_payload).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise AuthenticationError("Bearer token payload is invalid.") from exc

        if header.get("alg") != "HS256":
            raise AuthenticationError("Bearer token algorithm is not supported.")

        claims = AuthTokenClaims.model_validate(payload)
        now = int(datetime.now(timezone.utc).timestamp())
        if claims.iss != self.token_issuer:
            raise AuthenticationError("Bearer token issuer is invalid.")
        if claims.exp < now:
            raise AuthenticationError("Bearer token has expired.")
        return claims


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


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))
