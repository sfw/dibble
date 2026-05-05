from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPException
import json
from typing import Any, Callable, Iterator
from urllib import error, request


class LLMClientError(RuntimeError):
    """Raised when an upstream LLM call fails or returns an invalid payload."""


@dataclass(slots=True)
class LLMCompletion:
    content: str
    finish_reason: str | None = None
    raw_response: dict[str, Any] | None = None


Transport = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]
StreamTransport = Callable[[str, dict[str, Any], dict[str, str], float], Iterator[str]]


def post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(url=url, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise LLMClientError(
            f"LLM request failed with status {exc.code}: {details}"
        ) from exc
    except error.URLError as exc:
        raise LLMClientError(
            f"LLM request could not be completed: {exc.reason}"
        ) from exc
    except (TimeoutError, ConnectionError, HTTPException, OSError) as exc:
        raise LLMClientError(f"LLM request transport failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMClientError("LLM response was not valid JSON.") from exc


def post_event_stream(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> Iterator[str]:
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(url=url, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            for raw_line in response:
                yield raw_line.decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise LLMClientError(
            f"LLM request failed with status {exc.code}: {details}"
        ) from exc
    except error.URLError as exc:
        raise LLMClientError(
            f"LLM request could not be completed: {exc.reason}"
        ) from exc
    except (TimeoutError, ConnectionError, HTTPException, OSError) as exc:
        raise LLMClientError(f"LLM stream transport failed: {exc}") from exc


class OpenAICompatibleChatClient:
    DEFAULT_TEMPERATURE = 0.2

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 20.0,
        temperature: float | None = None,
        max_tokens: int | None = None,
        thinking_enabled: bool | None = None,
        response_format_json: bool = False,
        transport: Transport = post_json,
        stream_transport: StreamTransport = post_event_stream,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.default_temperature = (
            temperature if temperature is not None else self.DEFAULT_TEMPERATURE
        )
        self.max_tokens = max_tokens
        self.thinking_enabled = thinking_enabled
        self.response_format_json = response_format_json
        self.transport = transport
        self.stream_transport = stream_transport

    def complete(
        self, *, system_prompt: str, user_prompt: str, temperature: float | None = None
    ) -> LLMCompletion:
        response = self._complete_with_temperature(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature if temperature is not None else self.default_temperature,
        )
        return LLMCompletion(
            content=self._extract_content(response),
            finish_reason=self._extract_finish_reason(response),
            raw_response=response,
        )

    def stream_complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> Iterator[str]:
        for line in self._stream_lines_with_temperature(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature if temperature is not None else self.default_temperature,
        ):
            stripped = line.strip()
            if not stripped or not stripped.startswith("data: "):
                continue

            data = stripped.removeprefix("data: ").strip()
            if data == "[DONE]":
                return

            try:
                chunk = json.loads(data)
            except json.JSONDecodeError as exc:
                raise LLMClientError("LLM stream chunk was not valid JSON.") from exc

            for part in self._extract_stream_content_parts(chunk):
                yield part

    def _complete_with_temperature(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> dict[str, Any]:
        try:
            return self.transport(
                f"{self.api_base}/chat/completions",
                payload=self._build_payload(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                ),
                headers=self._request_headers(),
                timeout=self.timeout_seconds,
            )
        except LLMClientError as exc:
            if temperature != 1.0 and self._requires_fixed_temperature(exc):
                return self._complete_with_temperature(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=1.0,
                )
            raise
        except (TimeoutError, ConnectionError, HTTPException, OSError) as exc:
            raise LLMClientError(f"LLM request transport failed: {exc}") from exc

    def _stream_lines_with_temperature(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> Iterator[str]:
        try:
            lines = self.stream_transport(
                f"{self.api_base}/chat/completions",
                payload=self._build_payload(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    stream=True,
                ),
                headers=self._request_headers(stream=True),
                timeout=self.timeout_seconds,
            )
            for line in lines:
                yield line
        except LLMClientError as exc:
            if temperature != 1.0 and self._requires_fixed_temperature(exc):
                yield from self._stream_lines_with_temperature(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=1.0,
                )
                return
            raise
        except (TimeoutError, ConnectionError, HTTPException, OSError) as exc:
            raise LLMClientError(f"LLM stream transport failed: {exc}") from exc

    def _build_payload(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if stream:
            payload["stream"] = True
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.thinking_enabled is not None:
            payload["thinking"] = {
                "type": "enabled" if self.thinking_enabled else "disabled"
            }
        if self.response_format_json:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _request_headers(self, *, stream: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def _requires_fixed_temperature(self, exc: LLMClientError) -> bool:
        message = str(exc).lower()
        return "invalid temperature" in message and "only 1 is allowed" in message

    def _extract_content(self, response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("LLM response did not include any choices.")

        message = choices[0].get("message", {})
        content = self._coerce_content_text(message.get("content"))
        if content is not None:
            return content.strip()

        raise LLMClientError(
            "LLM response did not include a supported message content format."
        )

    def _extract_finish_reason(self, response: dict[str, Any]) -> str | None:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        finish_reason = choices[0].get("finish_reason")
        if isinstance(finish_reason, str):
            return finish_reason
        return None

    def _extract_stream_content_parts(self, response: dict[str, Any]) -> list[str]:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return []

        delta = choices[0].get("delta", {})
        content = self._coerce_content_text(delta.get("content"))
        if content is None or content == "":
            return []
        return [content]

    def _coerce_content_text(self, content: Any) -> str | None:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
            if parts:
                return "".join(parts)
        return None
