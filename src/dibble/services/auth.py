from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.config import Settings
from dibble.models.auth import AuthIdentity, AuthSession, AuthToken, AuthTokenClaims
from dibble.services.access_control import allows_role
from dibble.services.auth_sessions import StoredAuthSession
from dibble.services.protocols import AuthSessionStore


class AuthenticationError(RuntimeError):
    """Raised when a request is not authorized."""


class AuthorizationError(RuntimeError):
    """Raised when an authenticated principal lacks a required role."""

    def __init__(self, message: str, *, identity: AuthIdentity | None = None) -> None:
        super().__init__(message)
        self.identity = identity


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
    refresh_ttl_seconds: int = 604800
    session_store: AuthSessionStore | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        session_store: AuthSessionStore | None = None,
    ) -> "AuthService":
        return cls(
            enabled=settings.auth_enabled,
            principals=_build_principals(settings),
            header_name=settings.auth_header_name,
            token_secret=settings.auth_token_secret,
            token_issuer=settings.auth_token_issuer,
            token_ttl_seconds=settings.auth_token_ttl_seconds,
            refresh_ttl_seconds=settings.auth_refresh_ttl_seconds,
            session_store=session_store,
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
            raise AuthorizationError("Your role does not allow access to this endpoint.", identity=identity)
        return session

    def issue_token(self, identity: AuthIdentity) -> AuthToken:
        if not self.token_secret:
            raise TokenConfigurationError("Bearer token issuance requires DIBBLE_AUTH_TOKEN_SECRET.")

        now = datetime.now(timezone.utc)
        session_id = str(uuid4())
        access_expires_at = now + timedelta(seconds=self.token_ttl_seconds)
        refresh_expires_at = now + timedelta(seconds=self.refresh_ttl_seconds)
        access_claims = AuthTokenClaims(
            sub=identity.principal_id,
            role=identity.role,
            sid=session_id,
            jti=str(uuid4()),
            typ="access",
            iat=int(now.timestamp()),
            exp=int(access_expires_at.timestamp()),
            iss=self.token_issuer,
        )
        refresh_claims = AuthTokenClaims(
            sub=identity.principal_id,
            role=identity.role,
            sid=session_id,
            jti=str(uuid4()),
            typ="refresh",
            iat=int(now.timestamp()),
            exp=int(refresh_expires_at.timestamp()),
            iss=self.token_issuer,
        )
        token = self._encode_token(access_claims)
        refresh_token = self._encode_token(refresh_claims)
        self._store_session(
            session_id=session_id,
            identity=identity,
            refresh_token=refresh_token,
            created_at=now,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )
        return AuthToken(
            access_token=token,
            refresh_token=refresh_token,
            expires_in=self.token_ttl_seconds,
            identity=AuthIdentity(
                principal_id=identity.principal_id,
                role=identity.role,
                auth_scheme="bearer",
            ),
        )

    def authenticate_bearer_token(self, token: str) -> AuthSession:
        claims = self._decode_token(token)
        if claims.typ != "access":
            raise AuthenticationError("Bearer token must be an access token.")
        self._assert_session_active(claims.sid)
        authenticated_at = datetime.fromtimestamp(claims.iat, tz=timezone.utc)
        expires_at = datetime.fromtimestamp(claims.exp, tz=timezone.utc)
        return AuthSession(
            identity=AuthIdentity(
                principal_id=claims.sub,
                role=claims.role,
                auth_scheme="bearer",
            ),
            session_id=claims.sid,
            authenticated_at=authenticated_at,
            expires_at=expires_at,
        )

    def refresh_session(self, refresh_token: str) -> AuthToken:
        claims = self._decode_token(refresh_token)
        if claims.typ != "refresh":
            raise AuthenticationError("Refresh requires a refresh token.")

        session = self._get_session(claims.sid)
        if session.revoked_at is not None:
            raise AuthenticationError("Session has been revoked.")
        if session.refresh_token_hash != self._hash_token(refresh_token):
            raise AuthenticationError("Refresh token is no longer active.")
        if session.principal_id != claims.sub or session.role != claims.role:
            raise AuthenticationError("Refresh token session does not match the current principal.")

        identity = AuthIdentity(principal_id=claims.sub, role=claims.role, auth_scheme="bearer")
        now = datetime.now(timezone.utc)
        access_expires_at = now + timedelta(seconds=self.token_ttl_seconds)
        refresh_expires_at = now + timedelta(seconds=self.refresh_ttl_seconds)
        access_claims = AuthTokenClaims(
            sub=identity.principal_id,
            role=identity.role,
            sid=claims.sid,
            jti=str(uuid4()),
            typ="access",
            iat=int(now.timestamp()),
            exp=int(access_expires_at.timestamp()),
            iss=self.token_issuer,
        )
        refresh_claims = AuthTokenClaims(
            sub=identity.principal_id,
            role=identity.role,
            sid=claims.sid,
            jti=str(uuid4()),
            typ="refresh",
            iat=int(now.timestamp()),
            exp=int(refresh_expires_at.timestamp()),
            iss=self.token_issuer,
        )
        access_token = self._encode_token(access_claims)
        rotated_refresh_token = self._encode_token(refresh_claims)
        self._store_session(
            session_id=claims.sid,
            identity=identity,
            refresh_token=rotated_refresh_token,
            created_at=datetime.fromisoformat(session.created_at),
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )
        return AuthToken(
            access_token=access_token,
            refresh_token=rotated_refresh_token,
            expires_in=self.token_ttl_seconds,
            identity=identity,
        )

    def revoke_session(self, *, refresh_token: str | None = None, bearer_token: str | None = None) -> None:
        if refresh_token:
            claims = self._decode_token(refresh_token)
            if claims.typ != "refresh":
                raise AuthenticationError("Revocation refresh token is invalid.")
            session_id = claims.sid
        elif bearer_token:
            claims = self._decode_token(bearer_token)
            session_id = claims.sid
        else:
            raise AuthenticationError("No token was provided for revocation.")

        self._assert_session_active(session_id)
        if self.session_store is None:
            raise AuthenticationError("Session revocation is unavailable.")
        self.session_store.revoke(session_id, revoked_at=datetime.now(timezone.utc).isoformat())

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

    def _store_session(
        self,
        *,
        session_id: str,
        identity: AuthIdentity,
        refresh_token: str,
        created_at: datetime,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> None:
        if self.session_store is None:
            raise TokenConfigurationError("Bearer token sessions require a session store.")
        self.session_store.upsert(
            StoredAuthSession(
                session_id=session_id,
                principal_id=identity.principal_id,
                role=identity.role,
                refresh_token_hash=self._hash_token(refresh_token),
                created_at=created_at.isoformat(),
                access_expires_at=access_expires_at.isoformat(),
                refresh_expires_at=refresh_expires_at.isoformat(),
            )
        )

    def _get_session(self, session_id: str) -> StoredAuthSession:
        if self.session_store is None:
            raise AuthenticationError("Session storage is unavailable.")
        session = self.session_store.get(session_id)
        if session is None:
            raise AuthenticationError("Session was not found.")
        return session

    def _assert_session_active(self, session_id: str) -> None:
        session = self._get_session(session_id)
        if session.revoked_at is not None:
            raise AuthenticationError("Session has been revoked.")
        refresh_expiry = datetime.fromisoformat(session.refresh_expires_at)
        if refresh_expiry < datetime.now(timezone.utc):
            raise AuthenticationError("Session has expired.")

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
