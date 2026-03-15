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
from dibble.services.provider_health import ProviderRoutingSnapshot, SQLiteProviderHealthStore
from dibble.services.protocols import ProviderHealthStore
from dibble.services.prompt_manager import PromptManager
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.generation_prompt_selector import GenerationPromptSelector
from dibble.services.socratic_prompt_selector import SocraticPromptSelector
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
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float | None = None


class LLMOrchestrationProvider:
    def __init__(
        self,
        *,
        clients: list[tuple[str, OpenAICompatibleChatClient]],
        client_models: dict[str, str] | None = None,
        fallback_provider: MockLLMProvider | None = None,
        circuit_breaker_threshold: int = 2,
        circuit_breaker_cooldown_seconds: float = 30.0,
        selection_strategy: str = "ordered",
        time_provider: Callable[[], float] = monotonic,
        health_store: ProviderHealthStore | None = None,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        self.clients = clients
        self.client_models = client_models or {}
        self.fallback_provider = fallback_provider
        self.circuit_breaker_threshold = max(1, circuit_breaker_threshold)
        self.circuit_breaker_cooldown_seconds = max(0.0, circuit_breaker_cooldown_seconds)
        self.selection_strategy = selection_strategy
        self.time_provider = time_provider
        self.client_states = {name: ClientCircuitState() for name, _ in clients}
        self.health_store = health_store
        self.prompt_manager = prompt_manager or PromptManager()
        self.round_robin_cursor = 0
        self.last_used_descriptor = {
            "provider_name": None,
            "model_used": None,
            "prompt_template_name": None,
            "prompt_template_version": None,
            "prompt_template_variant": None,
        }
        self._hydrate_client_states()

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
        client_models: dict[str, str] = {}
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
            client_models[config.name] = config.model

        return cls(
            clients=clients,
            client_models=client_models,
            fallback_provider=fallback_provider,
            circuit_breaker_threshold=settings.llm_circuit_breaker_threshold,
            circuit_breaker_cooldown_seconds=settings.llm_circuit_breaker_cooldown_seconds,
            selection_strategy=settings.llm_selection_strategy,
            health_store=SQLiteProviderHealthStore(settings.database_path),
            prompt_manager=PromptManager.from_settings(
                settings,
                generation_prompt_selector=(
                    GenerationPromptSelector(SQLiteAuditStore(settings.database_path))
                    if settings.prompt_adaptive_selection_enabled
                    else None
                ),
                socratic_prompt_selector=(
                    SocraticPromptSelector(SQLiteAuditStore(settings.database_path))
                    if settings.prompt_adaptive_selection_enabled
                    else None
                ),
            ),
        )

    def generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> list[GeneratedBlock]:
        prompts = build_generation_prompts(
            profile,
            request,
            route,
            grounding_titles,
            prompt_manager=self.prompt_manager,
        )
        if not self.clients:
            return self._fallback(profile, request, route, grounding_titles, prompts, "LLM client not configured.")

        for name, client in self._iter_candidate_clients():
            started_at = self.time_provider()
            try:
                completion = client.complete(
                    system_prompt=prompts.system_prompt,
                    user_prompt=prompts.user_prompt,
                )
                blocks = self._parse_blocks(completion.content)
                self._set_last_used_descriptor(name, prompts)
                self._record_success(name, latency_ms=(self.time_provider() - started_at) * 1000.0)
                return blocks
            except (LLMClientError, LLMProviderError):
                self._record_failure(name, latency_ms=(self.time_provider() - started_at) * 1000.0)
                continue

        return self._fallback(profile, request, route, grounding_titles, prompts, "LLM call failed.")

    def stream_generate(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
    ) -> Iterator[GeneratedBlockChunk]:
        prompts = build_stream_generation_prompts(
            profile,
            request,
            route,
            grounding_titles,
            prompt_manager=self.prompt_manager,
        )
        if not self.clients:
            yield from iter_block_chunks(
                self._fallback(profile, request, route, grounding_titles, prompts, "LLM client not configured.")
            )
            return
        for name, client in self._iter_candidate_clients():
            parser = StreamingChunkParser()
            started_at = self.time_provider()
            try:
                for delta in client.stream_complete(
                    system_prompt=prompts.system_prompt,
                    user_prompt=prompts.user_prompt,
                ):
                    for chunk in parser.push(delta):
                        yield chunk

                for chunk in parser.flush():
                    yield chunk
                self._set_last_used_descriptor(name, prompts)
                self._record_success(name, latency_ms=(self.time_provider() - started_at) * 1000.0)
                return
            except (LLMClientError, LLMProviderError):
                self._record_failure(name, latency_ms=(self.time_provider() - started_at) * 1000.0)
                continue

        yield from iter_block_chunks(self._fallback(profile, request, route, grounding_titles, prompts, "LLM stream failed."))

    def _is_available(self, name: str) -> bool:
        state = self.client_states.get(name)
        if state is None or state.open_until is None:
            return True
        now = self.time_provider()
        if now >= state.open_until:
            state.open_until = None
            return True
        return False

    def _iter_candidate_clients(self) -> Iterator[tuple[str, OpenAICompatibleChatClient]]:
        available: list[tuple[str, OpenAICompatibleChatClient]] = []
        for name, client in self.clients:
            if self._is_available(name):
                available.append((name, client))
            else:
                self._record_health(name, "circuit_skip")

        if not available:
            return iter(())

        if self.selection_strategy == "round_robin":
            start = self.round_robin_cursor % len(available)
            ordered = available[start:] + available[:start]
            self.round_robin_cursor = (self.round_robin_cursor + 1) % len(available)
            return iter(ordered)

        if self.selection_strategy == "latency_aware":
            unexplored: list[tuple[str, OpenAICompatibleChatClient]] = []
            explored: list[tuple[int, tuple[str, OpenAICompatibleChatClient]]] = []

            for index, item in enumerate(available):
                state = self.client_states.get(item[0])
                if state is None or state.average_latency_ms is None:
                    unexplored.append(item)
                    continue
                explored.append((index, item))

            explored.sort(
                key=lambda item: self._latency_rank(item[1][0], item[0]),
            )
            return iter(unexplored + [item[1] for item in explored])

        return iter(available)

    def _record_success(self, name: str, *, latency_ms: float) -> None:
        state = self.client_states.get(name)
        if state is None:
            return
        recovered = state.open_until is not None or state.consecutive_failures > 0
        state.consecutive_failures = 0
        state.open_until = None
        state.successful_requests += 1
        state.average_latency_ms = self._smoothed_latency(state.average_latency_ms, latency_ms)
        self._record_health(
            name,
            "success" if not recovered else "circuit_recovered",
            latency_ms=round(latency_ms, 2),
            average_latency_ms=round(state.average_latency_ms, 2),
        )

    def _record_failure(self, name: str, *, latency_ms: float) -> None:
        state = self.client_states.get(name)
        if state is None:
            return
        state.consecutive_failures += 1
        state.failed_requests += 1
        state.average_latency_ms = self._smoothed_latency(state.average_latency_ms, latency_ms)
        self._record_health(
            name,
            "failure",
            consecutive_failures=state.consecutive_failures,
            latency_ms=round(latency_ms, 2),
            average_latency_ms=round(state.average_latency_ms, 2),
        )
        if state.consecutive_failures >= self.circuit_breaker_threshold:
            state.open_until = self.time_provider() + self.circuit_breaker_cooldown_seconds
            self._record_health(name, "circuit_open", open_until=state.open_until)

    def _latency_rank(self, name: str, original_index: int) -> tuple[float, float, int]:
        state = self.client_states.get(name)
        if state is None:
            return (-1.0, float("inf"), original_index)

        total_requests = state.successful_requests + state.failed_requests
        if total_requests == 0:
            return (-1.0, float("inf"), original_index)

        success_rate = (state.successful_requests / total_requests) if total_requests else 1.0
        latency = state.average_latency_ms if state.average_latency_ms is not None else float("inf")
        return (-success_rate, latency, original_index)

    def _smoothed_latency(self, current: float | None, observed: float) -> float:
        if current is None:
            return observed
        return (current * 0.7) + (observed * 0.3)

    def _hydrate_client_states(self) -> None:
        if self.health_store is None or not self.clients:
            return

        snapshots = self.health_store.routing_snapshots(
            provider_names=[name for name, _ in self.clients],
        )
        for snapshot in snapshots:
            self._apply_routing_snapshot(snapshot)

    def _apply_routing_snapshot(self, snapshot: ProviderRoutingSnapshot) -> None:
        state = self.client_states.get(snapshot.provider_name)
        if state is None:
            return

        state.successful_requests = snapshot.successful_requests
        state.failed_requests = snapshot.failed_requests
        state.consecutive_failures = snapshot.consecutive_failures
        state.average_latency_ms = snapshot.average_latency_ms
        state.open_until = snapshot.open_until

    def _record_health(self, name: str, status: str, **detail: object) -> None:
        if self.health_store is None:
            return
        self.health_store.append(provider_name=name, status=status, detail=detail)

    def _set_last_used_descriptor(self, name: str, prompts) -> None:
        self.last_used_descriptor = {
            "provider_name": name,
            "model_used": self.client_models.get(name),
            "prompt_template_name": prompts.template_name,
            "prompt_template_version": prompts.template_version,
            "prompt_template_variant": prompts.template_variant,
        }

    def _fallback(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        grounding_titles: list[str],
        prompts,
        reason: str,
    ) -> list[GeneratedBlock]:
        if self.fallback_provider is None:
            raise LLMProviderError(reason)

        blocks = self.fallback_provider.generate(profile, request, route, grounding_titles)
        fallback_descriptor = getattr(
            self.fallback_provider,
            "last_used_descriptor",
            {"provider_name": "fallback", "model_used": None},
        )
        self.last_used_descriptor = {
            "provider_name": fallback_descriptor.get("provider_name"),
            "model_used": fallback_descriptor.get("model_used"),
            "prompt_template_name": prompts.template_name,
            "prompt_template_version": prompts.template_version,
            "prompt_template_variant": prompts.template_variant,
        }
        return blocks

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
