from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass

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
    api_base: str
    api_key: str | None
    model: str | None
    timeout_seconds: float
    allow_mock_fallback: bool = True


class LLMOrchestrationProvider:
    def __init__(
        self,
        *,
        client: OpenAICompatibleChatClient | None,
        fallback_provider: MockLLMProvider | None = None,
    ) -> None:
        self.client = client
        self.fallback_provider = fallback_provider

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMOrchestrationProvider":
        config = LLMProviderConfig(
            api_base=settings.llm_api_base,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            allow_mock_fallback=settings.llm_allow_mock_fallback,
        )
        fallback_provider = MockLLMProvider() if config.allow_mock_fallback else None

        if not config.api_key or not config.model:
            return cls(client=None, fallback_provider=fallback_provider)

        client = OpenAICompatibleChatClient(
            api_base=config.api_base,
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
        )
        return cls(client=client, fallback_provider=fallback_provider)

    def generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> list[GeneratedBlock]:
        if self.client is None:
            return self._fallback(profile, request, route, grounding_titles, "LLM client not configured.")

        prompts = build_generation_prompts(profile, request, route, grounding_titles)

        try:
            completion = self.client.complete(
                system_prompt=prompts.system_prompt,
                user_prompt=prompts.user_prompt,
            )
            return self._parse_blocks(completion.content)
        except (LLMClientError, LLMProviderError):
            return self._fallback(profile, request, route, grounding_titles, "LLM call failed.")

    def stream_generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> Iterator[GeneratedBlockChunk]:
        if self.client is None:
            yield from iter_block_chunks(self._fallback(profile, request, route, grounding_titles, "LLM client not configured."))
            return

        prompts = build_stream_generation_prompts(profile, request, route, grounding_titles)
        parser = StreamingChunkParser()
        try:
            for delta in self.client.stream_complete(
                system_prompt=prompts.system_prompt,
                user_prompt=prompts.user_prompt,
            ):
                for chunk in parser.push(delta):
                    yield chunk

            for chunk in parser.flush():
                yield chunk
        except (LLMClientError, LLMProviderError):
            yield from iter_block_chunks(self._fallback(profile, request, route, grounding_titles, "LLM stream failed."))

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
