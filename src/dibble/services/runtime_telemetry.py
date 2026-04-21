from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dibble.config import Settings, ensure_dibble_logs_dir

DEFAULT_SESSION_ID = "system"
_SESSION_ID = ContextVar("dibble_runtime_session_id", default=DEFAULT_SESSION_ID)
_REQUEST_ID = ContextVar("dibble_runtime_request_id", default="system")
_TELEMETRY_LEVEL = ContextVar("dibble_runtime_telemetry_level", default="off")
_LOG_LEVELS = {
    "off": logging.CRITICAL + 1,
    "normal": logging.INFO,
    "debug": logging.DEBUG,
}
_SENSITIVE_KEYS = {
    "api-key",
    "api_key",
    "authorization",
    "auth_token_secret",
    "bearer_token",
    "cookie",
    "credential",
    "password",
    "proxy-authorization",
    "refresh_token",
    "refresh_token_hash",
    "set-cookie",
    "token",
    "token_secret",
    "x-api-key",
    "x-openai-api-key",
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


@dataclass(slots=True)
class CapturedRequest:
    body: bytes
    payload: object | None
    request: Request
    receive: Receive


def telemetry_debug_enabled() -> bool:
    return _TELEMETRY_LEVEL.get() == "debug"


def current_session_id() -> str:
    return _SESSION_ID.get()


def current_request_id() -> str:
    return _REQUEST_ID.get()


def bind_runtime_telemetry(
    *,
    session_id: str | None = None,
    request_id: str | None = None,
    telemetry_level: str = "off",
) -> tuple[Token[str], Token[str], Token[str]]:
    normalized_level = telemetry_level.strip().lower()
    normalized_session = _normalize_session_id(session_id)
    normalized_request = _normalize_request_id(request_id)
    return (
        _SESSION_ID.set(normalized_session),
        _REQUEST_ID.set(normalized_request),
        _TELEMETRY_LEVEL.set(normalized_level),
    )


def reset_runtime_telemetry(tokens: tuple[Token[str], Token[str], Token[str]]) -> None:
    session_token, request_token, level_token = tokens
    _SESSION_ID.reset(session_token)
    _REQUEST_ID.reset(request_token)
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


class RuntimeTelemetryMiddleware:
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        captured = await capture_request(scope, receive)
        session_id = resolve_request_session_id(captured.request, captured.payload)
        request_id = resolve_request_id(captured.request)
        tokens = bind_runtime_telemetry(
            session_id=session_id,
            request_id=request_id,
            telemetry_level=self.settings.telemetry_level,
        )
        started_at = monotonic()
        status_code = 500
        content_type: str | None = None

        async def send_with_capture(message: Message) -> None:
            nonlocal status_code, content_type
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("utf-8")))
                message["headers"] = headers
                status_code = int(message["status"])
                header_map = {
                    key.decode("latin-1"): value.decode("latin-1")
                    for key, value in headers
                }
                content_type = header_map.get("content-type")
            await send(message)

        try:
            log_runtime_event(
                logging.getLogger(__name__),
                logging.INFO,
                "request.started",
                **request_summary(captured.request),
            )
            if telemetry_debug_enabled():
                log_runtime_event(
                    logging.getLogger(__name__),
                    logging.DEBUG,
                    "request.payload",
                    payload=scrub_payload(captured.payload),
                )
                log_runtime_event(
                    logging.getLogger(__name__),
                    logging.DEBUG,
                    "request.headers",
                    headers=_scrub_headers(captured.request.headers),
                )
            await self.app(scope, captured.receive, send_with_capture)
            log_runtime_event(
                logging.getLogger(__name__),
                logging.INFO,
                "request.completed",
                **request_summary(captured.request),
                **response_summary(
                    status_code=status_code,
                    duration_ms=duration_ms(started_at),
                    content_type=content_type,
                ),
            )
        except Exception:
            log_runtime_event(
                logging.getLogger(__name__),
                logging.ERROR,
                "request.failed",
                **request_summary(captured.request),
                duration_ms=duration_ms(started_at),
            )
            logging.getLogger(__name__).exception("Unhandled application exception")
            raise
        finally:
            reset_runtime_telemetry(tokens)


async def capture_request(scope: Scope, receive: Receive) -> CapturedRequest:
    body_chunks: list[bytes] = []
    disconnected = False

    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            disconnected = True
            break
        if message["type"] != "http.request":
            continue
        body_chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break

    body = b"".join(body_chunks)
    payload = _parse_json_payload(scope, body)
    request_sent = False

    async def replay_receive() -> Message:
        nonlocal request_sent, disconnected
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        if disconnected:
            return {"type": "http.disconnect"}
        message = await receive()
        if message["type"] == "http.disconnect":
            disconnected = True
        return message

    request = Request(scope, receive=replay_receive)
    return CapturedRequest(
        body=body,
        payload=payload,
        request=request,
        receive=replay_receive,
    )


def _parse_json_payload(scope: Scope, body: bytes) -> object | None:
    if not body:
        return None
    headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }
    if "application/json" not in headers.get("content-type", ""):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


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


def resolve_request_id(request: Request) -> str:
    return _normalize_request_id(request.headers.get("X-Request-ID") or str(uuid4()))


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


def _scrub_headers(headers) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_KEYS:
            redacted[key] = "***"
            continue
        redacted[key] = value
    return redacted


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
        record.request_id = current_request_id()
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


def _normalize_request_id(request_id: str | None) -> str:
    if request_id is None:
        return "system"
    normalized = re.sub(r"[^A-Za-z0-9._:-]+", "-", request_id.strip())
    normalized = normalized.strip(".-:")
    return normalized or "system"


def _encode_log_fields(fields: dict[str, object]) -> str:
    return json.dumps(fields, default=_json_default, sort_keys=True)


def _json_default(value: Any) -> str:
    return str(value)
