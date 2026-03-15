from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from time import monotonic
from typing import Callable

from dibble.config import Settings
from dibble.models.generation import AdaptiveRouteDecision, GeneratedBlock, GeneratedBlockChunk, GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.services.content_provider import MockLLMProvider
from dibble.services.llm_client import LLMClientError, OpenAICompatibleChatClient
from dibble.services.llm_prompting import build_generation_prompts, build_stream_generation_prompts
from dibble.services.streaming import iter_block_chunks


class LLMProviderError(RuntimeError):
    """Raised when a model response cannot be transformed into generated blocks."""


@dataclass(slots=True)
class LLMProviderConfig:
    name: str
    api_base: str
    api_key: str | None
    model: str | None
    timeout_seconds: float
    allow_mock_fallback: bool = True


@dataclass(slots=True)
class ClientCircuitState:
    consecutive_failures: int = 0
    open_until: float | None = None


class LLMOrchestrationProvider:
    def __init__(
        self,
        *,
        clients: list[tuple[str, OpenAICompatibleChatClient]],
        fallback_provider: MockLLMProvider | None = None,
        circuit_breaker_threshold: int = 2,
        circuit_breaker_cooldown_seconds: float = 30.0,
        time_provider: Callable[[], float] = monotonic,
    ) -> None:
        self.clients = clients
        self.fallback_provider = fallback_provider
        self.circuit_breaker_threshold = max(1, circuit_breaker_threshold)
        self.circuit_breaker_cooldown_seconds = max(0.0, circuit_breaker_cooldown_seconds)
        self.time_provider = time_provider
        self.client_states = {name: ClientCircuitState() for name, _ in clients}

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMOrchestrationProvider":
        configs = [
            LLMProviderConfig(
                name="primary",
                api_base=settings.llm_api_base,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                allow_mock_fallback=settings.llm_allow_mock_fallback,
            ),
            LLMProviderConfig(
                name="secondary",
                api_base=settings.llm_secondary_api_base or settings.llm_api_base,
                api_key=settings.llm_secondary_api_key,
                model=settings.llm_secondary_model,
                timeout_seconds=settings.llm_secondary_timeout_seconds or settings.llm_timeout_seconds,
                allow_mock_fallback=settings.llm_allow_mock_fallback,
            ),
        ]
        fallback_provider = MockLLMProvider() if settings.llm_allow_mock_fallback else None
        clients: list[tuple[str, OpenAICompatibleChatClient]] = []
        for config in configs:
            if not config.api_key or not config.model:
                continue
            clients.append(
                (
                    config.name,
                    OpenAICompatibleChatClient(
                        api_base=config.api_base,
                        api_key=config.api_key,
                        model=config.model,
                        timeout_seconds=config.timeout_seconds,
                    ),
                )
            )

        return cls(
            clients=clients,
            fallback_provider=fallback_provider,
            circuit_breaker_threshold=settings.llm_circuit_breaker_threshold,
            circuit_breaker_cooldown_seconds=settings.llm_circuit_breaker_cooldown_seconds,
        )

    def generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> list[GeneratedBlock]:
        if not self.clients:
            return self._fallback(profile, request, route, grounding_titles, "LLM client not configured.")

        prompts = build_generation_prompts(profile, request, route, grounding_titles)

        for name, client in self.clients:
            if not self._is_available(name):
                continue
            try:
                completion = client.complete(
                    system_prompt=prompts.system_prompt,
                    user_prompt=prompts.user_prompt,
                )
                blocks = self._parse_blocks(completion.content)
                self._record_success(name)
                return blocks
            except (LLMClientError, LLMProviderError):
                self._record_failure(name)
                continue

        return self._fallback(profile, request, route, grounding_titles, "LLM call failed.")

    def stream_generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> Iterator[GeneratedBlockChunk]:
        if not self.clients:
            yield from iter_block_chunks(self._fallback(profile, request, route, grounding_titles, "LLM client not configured."))
            return

        prompts = build_stream_generation_prompts(profile, request, route, grounding_titles)
        for name, client in self.clients:
            if not self._is_available(name):
                continue
            parser = StreamingChunkParser()
            try:
                for delta in client.stream_complete(
                    system_prompt=prompts.system_prompt,
                    user_prompt=prompts.user_prompt,
                ):
                    for chunk in parser.push(delta):
                        yield chunk

                for chunk in parser.flush():
                    yield chunk
                self._record_success(name)
                return
            except (LLMClientError, LLMProviderError):
                self._record_failure(name)
                continue

        yield from iter_block_chunks(self._fallback(profile, request, route, grounding_titles, "LLM stream failed."))

    def _is_available(self, name: str) -> bool:
        state = self.client_states.get(name)
        if state is None or state.open_until is None:
            return True
        now = self.time_provider()
        if now >= state.open_until:
            state.open_until = None
            return True
        return False

    def _record_success(self, name: str) -> None:
        state = self.client_states.get(name)
        if state is None:
            return
        state.consecutive_failures = 0
        state.open_until = None

    def _record_failure(self, name: str) -> None:
        state = self.client_states.get(name)
        if state is None:
            return
        state.consecutive_failures += 1
        if state.consecutive_failures >= self.circuit_breaker_threshold:
            state.open_until = self.time_provider() + self.circuit_breaker_cooldown_seconds

    def _fallback(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
        reason: str,
    ) -> list[GeneratedBlock]:
        if self.fallback_provider is None:
            raise LLMProviderError(reason)

        return self.fallback_provider.generate(profile, request, route, grounding_titles)

    def _parse_blocks(self, response_text: str) -> list[GeneratedBlock]:
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            cleaned = self._strip_code_fence(cleaned)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("LLM output was not valid JSON.") from exc

        blocks_payload = payload.get("blocks")
        if not isinstance(blocks_payload, list) or not blocks_payload:
            raise LLMProviderError("LLM output did not include any generated blocks.")

        try:
            return [GeneratedBlock.model_validate(item) for item in blocks_payload]
        except Exception as exc:  # pragma: no cover - pydantic already exercises the shape checks.
            raise LLMProviderError("LLM output blocks did not match the Dibble schema.") from exc

    def _strip_code_fence(self, value: str) -> str:
        lines = value.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
        return value


class StreamingChunkParser:
    def __init__(self) -> None:
        self.buffer = ""

    def push(self, delta: str) -> list[GeneratedBlockChunk]:
        self.buffer += delta
        chunks: list[GeneratedBlockChunk] = []

        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            parsed = self._parse_line(line)
            if parsed is not None:
                chunks.append(parsed)

        return chunks

    def flush(self) -> list[GeneratedBlockChunk]:
        parsed = self._parse_line(self.buffer)
        self.buffer = ""
        return [parsed] if parsed is not None else []

    def _parse_line(self, line: str) -> GeneratedBlockChunk | None:
        stripped = line.strip()
        if not stripped:
            return None

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("Streamed LLM output was not valid NDJSON.") from exc

        try:
            return GeneratedBlockChunk.model_validate(payload)
        except Exception as exc:  # pragma: no cover
            raise LLMProviderError("Streamed LLM chunk did not match the Dibble schema.") from exc
