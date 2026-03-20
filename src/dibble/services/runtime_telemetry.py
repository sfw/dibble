from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar, Token
from pathlib import Path
from time import monotonic
from typing import Any

from fastapi import Request

from dibble.config import Settings, ensure_dibble_logs_dir

DEFAULT_SESSION_ID = "system"
_SESSION_ID = ContextVar("dibble_runtime_session_id", default=DEFAULT_SESSION_ID)
_TELEMETRY_LEVEL = ContextVar("dibble_runtime_telemetry_level", default="off")
_LOG_LEVELS = {
    "off": logging.CRITICAL + 1,
    "normal": logging.INFO,
    "debug": logging.DEBUG,
}
_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "auth_token_secret",
    "bearer_token",
    "credential",
    "password",
    "refresh_token",
    "refresh_token_hash",
    "token",
    "token_secret",
}
_SESSION_KEY_PRIORITY = (
    "learning_session_id",
    "session_id",
    "remediation_session_id",
    "socratic_session_id",
)
_SESSION_PATH_PATTERNS = (
    re.compile(r"^/api/remedial/sessions/(?P<session_id>[^/]+)"),
    re.compile(r"^/api/assessments/socratic/(?P<session_id>[^/]+)"),
)
_LOGGER = logging.getLogger("dibble.runtime")


def telemetry_debug_enabled() -> bool:
    return _TELEMETRY_LEVEL.get() == "debug"


def current_session_id() -> str:
    return _SESSION_ID.get()


def bind_runtime_telemetry(
    *, session_id: str | None = None, telemetry_level: str = "off"
) -> tuple[Token[str], Token[str]]:
    normalized_level = telemetry_level.strip().lower()
    normalized_session = _normalize_session_id(session_id)
    return (
        _SESSION_ID.set(normalized_session),
        _TELEMETRY_LEVEL.set(normalized_level),
    )


def reset_runtime_telemetry(tokens: tuple[Token[str], Token[str]]) -> None:
    session_token, level_token = tokens
    _SESSION_ID.reset(session_token)
    _TELEMETRY_LEVEL.reset(level_token)


def log_runtime_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    if not logger.isEnabledFor(level):
        return
    if fields:
        logger.log(level, "%s %s", event, _encode_log_fields(fields))
        return
    logger.log(level, event)


def setup_runtime_telemetry(
    settings: Settings, *, logs_dir: Path | None = None
) -> Path:
    path = logs_dir or ensure_dibble_logs_dir()
    logger = logging.getLogger("dibble")
    logger.handlers.clear()
    logger.filters.clear()
    logger.propagate = False
    logger.disabled = False

    if settings.telemetry_level == "off":
        logger.setLevel(_LOG_LEVELS["off"])
        logger.addHandler(logging.NullHandler())
        return path

    logger.setLevel(_LOG_LEVELS[settings.telemetry_level])
    handler = SessionFileHandler(path)
    handler.setLevel(_LOG_LEVELS[settings.telemetry_level])
    handler.addFilter(SessionContextFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] [session:%(session_id)s] %(message)s"
        )
    )
    logger.addHandler(handler)
    log_runtime_event(
        _LOGGER,
        logging.INFO,
        "runtime.telemetry.initialized",
        telemetry_level=settings.telemetry_level,
        logs_dir=str(path),
    )
    return path


async def extract_request_payload(request: Request) -> tuple[bytes, object | None]:
    body = await request.body()
    if not body:
        return body, None

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[attr-defined]

    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return body, None

    try:
        return body, json.loads(body)
    except json.JSONDecodeError:
        return body, None


def resolve_request_session_id(request: Request, payload: object | None) -> str:
    header_value = request.headers.get("X-Dibble-Session-Id")
    if header_value:
        return _normalize_session_id(header_value)

    if isinstance(payload, dict):
        direct = _extract_session_id_from_mapping(payload)
        if direct is not None:
            return _normalize_session_id(direct)

        requests_payload = payload.get("requests")
        if isinstance(requests_payload, list):
            session_ids = {
                candidate
                for item in requests_payload
                for candidate in [_extract_session_id_from_mapping(item)]
                if candidate is not None
            }
            if len(session_ids) == 1:
                return _normalize_session_id(next(iter(session_ids)))
            if len(session_ids) > 1:
                return "multi-session"

    for pattern in _SESSION_PATH_PATTERNS:
        match = pattern.match(request.url.path)
        if match:
            return _normalize_session_id(match.group("session_id"))

    return DEFAULT_SESSION_ID


def scrub_payload(payload: object | None) -> object | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        redacted: dict[str, object] = {}
        for key, value in payload.items():
            if key.lower() in _SENSITIVE_KEYS:
                redacted[key] = "***"
                continue
            redacted[key] = scrub_payload(value)
        return redacted
    if isinstance(payload, list):
        return [scrub_payload(item) for item in payload]
    return payload


def request_summary(request: Request) -> dict[str, object]:
    summary: dict[str, object] = {
        "method": request.method,
        "path": request.url.path,
    }
    if request.url.query:
        summary["query"] = request.url.query
    client = request.client
    if client is not None:
        summary["client"] = f"{client.host}:{client.port}"
    return summary


def response_summary(
    *, status_code: int, duration_ms: int, content_type: str | None = None
) -> dict[str, object]:
    summary: dict[str, object] = {
        "status_code": status_code,
        "duration_ms": duration_ms,
    }
    if content_type:
        summary["content_type"] = content_type
    return summary


def duration_ms(started_at: float) -> int:
    return int(round((monotonic() - started_at) * 1000))


class SessionContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = current_session_id()
        return True


class SessionFileHandler(logging.Handler):
    def __init__(self, logs_dir: Path) -> None:
        super().__init__()
        self._logs_dir = logs_dir

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            session_id = _normalize_session_id(
                getattr(record, "session_id", DEFAULT_SESSION_ID)
            )
            path = self._logs_dir / f"{session_id}.log"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(message)
                handle.write("\n")
        except Exception:
            self.handleError(record)


def _extract_session_id_from_mapping(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in _SESSION_KEY_PRIORITY:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_session_id(session_id: str | None) -> str:
    if session_id is None:
        return DEFAULT_SESSION_ID
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", session_id.strip())
    normalized = normalized.strip(".-")
    return normalized or DEFAULT_SESSION_ID


def _encode_log_fields(fields: dict[str, object]) -> str:
    return json.dumps(fields, default=_json_default, sort_keys=True)


def _json_default(value: Any) -> str:
    return str(value)
