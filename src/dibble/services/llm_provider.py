from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Callable

from dibble.config import Settings
from dibble.models.generation import (
    AdaptiveRouteDecision,
    CurriculumContentRequest,
    GeneratedBlock,
    GeneratedBlockChunk,
    GroundingReference,
)
from dibble.services.content_provider import MockLLMProvider
from dibble.services.llm_client import LLMClientError, OpenAICompatibleChatClient
from dibble.services.llm_prompting import (
    build_generation_prompts,
    build_stream_generation_prompts,
)
from dibble.services.provider_health import ProviderRoutingSnapshot
from dibble.services.protocols import AuditStore, ProviderHealthStore
from dibble.services.prompt_manager import PromptManager
from dibble.services.runtime_telemetry import log_runtime_event, telemetry_debug_enabled
from dibble.services.generation_prompt_selector import GenerationPromptSelector
from dibble.services.socratic_prompt_selector import SocraticPromptSelector
from dibble.services.streaming import iter_block_chunks

logger = logging.getLogger(__name__)
DEFAULT_CLIENT_RETRY_ATTEMPTS = 4


class LLMProviderError(RuntimeError):
    """Raised when a model response cannot be transformed into generated blocks."""


@dataclass(slots=True)
class LLMProviderConfig:
    name: str
    api_base: str
    api_key: str | None
    model: str | None
    timeout_seconds: float
    temperature: float | None = None
    max_tokens: int | None = None
    thinking_enabled: bool | None = None
    response_format_json: bool = False
    allow_mock_fallback: bool = True


@dataclass(slots=True)
class ClientCircuitState:
    consecutive_failures: int = 0
    open_until: float | None = None
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float | None = None


def build_llm_clients(
    settings: Settings,
) -> tuple[list[tuple[str, OpenAICompatibleChatClient]], dict[str, str]]:
    configs = [
        LLMProviderConfig(
            name="primary",
            api_base=settings.llm_api_base,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            thinking_enabled=settings.llm_thinking_enabled,
            response_format_json=settings.llm_response_format_json,
            allow_mock_fallback=settings.llm_allow_mock_fallback,
        ),
        LLMProviderConfig(
            name="secondary",
            api_base=settings.llm_secondary_api_base or settings.llm_api_base,
            api_key=settings.llm_secondary_api_key,
            model=settings.llm_secondary_model,
            timeout_seconds=settings.llm_secondary_timeout_seconds
            or settings.llm_timeout_seconds,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            thinking_enabled=settings.llm_thinking_enabled,
            response_format_json=settings.llm_response_format_json,
            allow_mock_fallback=settings.llm_allow_mock_fallback,
        ),
    ]
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
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    thinking_enabled=config.thinking_enabled,
                    response_format_json=config.response_format_json,
                ),
            )
        )
        client_models[config.name] = config.model
    return clients, client_models


def build_prompt_manager_from_settings(
    settings: Settings,
    *,
    audit_store: AuditStore | None = None,
) -> PromptManager:
    selector_store = audit_store if settings.prompt_adaptive_selection_enabled else None
    return PromptManager.from_settings(
        settings,
        generation_prompt_selector=(
            GenerationPromptSelector(selector_store)
            if selector_store is not None
            else None
        ),
        socratic_prompt_selector=(
            SocraticPromptSelector(selector_store)
            if selector_store is not None
            else None
        ),
    )


class LLMOrchestrationProvider:
    def __init__(
        self,
        *,
        clients: list[tuple[str, OpenAICompatibleChatClient]],
        client_models: dict[str, str] | None = None,
        fallback_provider: MockLLMProvider | None = None,
        circuit_breaker_threshold: int = 2,
        circuit_breaker_cooldown_seconds: float = 30.0,
        retry_backoff_seconds: float = 0.0,
        retry_attempts: int = DEFAULT_CLIENT_RETRY_ATTEMPTS,
        selection_strategy: str = "ordered",
        time_provider: Callable[[], float] = monotonic,
        health_store: ProviderHealthStore | None = None,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        self.clients = clients
        self.client_models = client_models or {}
        self.fallback_provider = fallback_provider
        self.circuit_breaker_threshold = max(1, circuit_breaker_threshold)
        self.circuit_breaker_cooldown_seconds = max(
            0.0, circuit_breaker_cooldown_seconds
        )
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.retry_attempts = max(1, retry_attempts)
        self.selection_strategy = selection_strategy
        self.time_provider = time_provider
        self.client_states = {name: ClientCircuitState() for name, _ in clients}
        self.health_store = health_store
        self.prompt_manager = prompt_manager or PromptManager()
        self.debug_prompts = False
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
    def from_settings(
        cls,
        settings: Settings,
        *,
        health_store: ProviderHealthStore | None = None,
        prompt_manager: PromptManager | None = None,
    ) -> "LLMOrchestrationProvider":
        fallback_provider = (
            MockLLMProvider() if settings.llm_allow_mock_fallback else None
        )
        clients, client_models = build_llm_clients(settings)

        provider = cls(
            clients=clients,
            client_models=client_models,
            fallback_provider=fallback_provider,
            circuit_breaker_threshold=settings.llm_circuit_breaker_threshold,
            circuit_breaker_cooldown_seconds=settings.llm_circuit_breaker_cooldown_seconds,
            retry_backoff_seconds=settings.llm_retry_backoff_seconds,
            retry_attempts=settings.llm_retry_attempts,
            selection_strategy=settings.llm_selection_strategy,
            health_store=health_store,
            prompt_manager=prompt_manager
            or build_prompt_manager_from_settings(settings),
        )
        provider.debug_prompts = settings.llm_debug_prompts_enabled
        if clients:
            logger.info(
                "LLM provider ready with %d client(s): %s",
                len(clients),
                ", ".join(f"{n} ({client_models.get(n, '?')})" for n, _ in clients),
            )
        else:
            logger.warning(
                "No LLM clients configured (llm_api_key=%s, llm_model=%s). "
                "All generation will use mock fallback.",
                "set" if settings.llm_api_key else "MISSING",
                settings.llm_model or "MISSING",
            )
        return provider

    def generate(
        self,
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> list[GeneratedBlock]:
        prompts = build_generation_prompts(
            request,
            route,
            grounding,
            prompt_manager=self.prompt_manager,
        )
        self._log_prompts(prompts)
        log_runtime_event(
            logger,
            logging.DEBUG,
            "llm.generate.start",
            curriculum_selection_key=request.prompt_selection_key(),
            template_name=prompts.template_name,
            template_variant=prompts.template_variant,
            client_names=[name for name, _ in self.clients],
            selection_strategy=self.selection_strategy,
        )
        if telemetry_debug_enabled():
            log_runtime_event(
                logger,
                logging.DEBUG,
                "llm.generate.prompts",
                system_prompt=prompts.system_prompt,
                user_prompt=prompts.user_prompt,
            )
        if not self.clients:
            return self._fallback(
                request,
                route,
                grounding,
                prompts,
                "LLM client not configured.",
            )

        failure_reasons: list[str] = []
        for name, client in self._iter_candidate_clients():
            started_at = self.time_provider()
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    completion = client.complete(
                        system_prompt=prompts.system_prompt,
                        user_prompt=prompts.user_prompt,
                    )
                    if telemetry_debug_enabled():
                        log_runtime_event(
                            logger,
                            logging.DEBUG,
                            "llm.generate.response",
                            provider_name=name,
                            model_used=self.client_models.get(name),
                            finish_reason=completion.finish_reason,
                            content=completion.content,
                            raw_response=completion.raw_response,
                        )
                    try:
                        blocks = self._parse_blocks(completion.content)
                    except LLMProviderError:
                        if telemetry_debug_enabled():
                            log_runtime_event(
                                logger,
                                logging.DEBUG,
                                "llm.generate.parse_failure",
                                provider_name=name,
                                model_used=self.client_models.get(name),
                                content=completion.content,
                                raw_response=completion.raw_response,
                            )
                        raise
                    self._set_last_used_descriptor(
                        name,
                        prompts,
                        usage=self._extract_usage(
                            getattr(completion, "raw_response", None)
                        ),
                    )
                    self._record_success(
                        name, latency_ms=(self.time_provider() - started_at) * 1000.0
                    )
                    log_runtime_event(
                        logger,
                        logging.DEBUG,
                        "llm.generate.success",
                        provider_name=name,
                        model_used=self.client_models.get(name),
                        block_count=len(blocks),
                        blocks=[block.model_dump(mode="json") for block in blocks],
                    )
                    return blocks
                except LLMClientError as exc:
                    if (
                        attempt < self.retry_attempts
                        and self._is_retryable_client_error(exc)
                    ):
                        logger.warning(
                            "LLM client %r transport failed on attempt %d/%d; retrying",
                            name,
                            attempt,
                            self.retry_attempts,
                            exc_info=True,
                        )
                        self._backoff_before_retry(attempt)
                        continue
                    failure_reasons.append(
                        f"{name}: {type(exc).__name__}: {str(exc)}"
                    )
                    self._record_client_failure(name, started_at, exc)
                    break
                except LLMProviderError as exc:
                    failure_reasons.append(
                        f"{name}: {type(exc).__name__}: {str(exc)}"
                    )
                    self._record_client_failure(name, started_at, exc)
                    break

        logger.warning("All LLM clients exhausted; falling back to mock provider")
        failure_summary = "; ".join(failure_reasons) or "LLM call failed."
        return self._fallback(request, route, grounding, prompts, failure_summary)

    def stream_generate(
        self,
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
    ) -> Iterator[GeneratedBlockChunk]:
        prompts = build_stream_generation_prompts(
            request,
            route,
            grounding,
            prompt_manager=self.prompt_manager,
        )
        self._log_prompts(prompts)
        log_runtime_event(
            logger,
            logging.DEBUG,
            "llm.stream.start",
            curriculum_selection_key=request.prompt_selection_key(),
            template_name=prompts.template_name,
            template_variant=prompts.template_variant,
            client_names=[name for name, _ in self.clients],
            selection_strategy=self.selection_strategy,
        )
        if telemetry_debug_enabled():
            log_runtime_event(
                logger,
                logging.DEBUG,
                "llm.stream.prompts",
                system_prompt=prompts.system_prompt,
                user_prompt=prompts.user_prompt,
            )
        if not self.clients:
            yield from iter_block_chunks(
                self._fallback(
                    request,
                    route,
                    grounding,
                    prompts,
                    "LLM client not configured.",
                )
            )
            return
        for name, client in self._iter_candidate_clients():
            parser = StreamingChunkParser()
            started_at = self.time_provider()
            raw_deltas: list[str] = []
            try:
                for delta in client.stream_complete(
                    system_prompt=prompts.system_prompt,
                    user_prompt=prompts.user_prompt,
                ):
                    raw_deltas.append(delta)
                    for chunk in parser.push(delta):
                        yield chunk

                for chunk in parser.flush():
                    yield chunk
                if telemetry_debug_enabled():
                    log_runtime_event(
                        logger,
                        logging.DEBUG,
                        "llm.stream.response",
                        provider_name=name,
                        model_used=self.client_models.get(name),
                        content="".join(raw_deltas),
                        chunk_count=len(raw_deltas),
                    )
                self._set_last_used_descriptor(name, prompts)
                self._record_success(
                    name, latency_ms=(self.time_provider() - started_at) * 1000.0
                )
                log_runtime_event(
                    logger,
                    logging.DEBUG,
                    "llm.stream.success",
                    provider_name=name,
                    model_used=self.client_models.get(name),
                )
                return
            except (LLMClientError, LLMProviderError) as exc:
                if telemetry_debug_enabled():
                    log_runtime_event(
                        logger,
                        logging.DEBUG,
                        "llm.stream.failure",
                        provider_name=name,
                        model_used=self.client_models.get(name),
                        error_type=type(exc).__name__,
                        error=str(exc),
                        chunk_count=len(raw_deltas),
                        partial_content="".join(raw_deltas),
                    )
                logger.warning(
                    "LLM stream client %r failed, trying next",
                    name,
                    exc_info=True,
                )
                self._record_failure(
                    name, latency_ms=(self.time_provider() - started_at) * 1000.0
                )
                continue

        logger.warning("All LLM stream clients exhausted; falling back to mock provider")
        yield from iter_block_chunks(
            self._fallback(request, route, grounding, prompts, "LLM stream failed.")
        )

    def _is_available(self, name: str) -> bool:
        state = self.client_states.get(name)
        if state is None or state.open_until is None:
            return True
        now = self.time_provider()
        if now >= state.open_until:
            state.open_until = None
            return True
        return False

    def _iter_candidate_clients(
        self,
    ) -> Iterator[tuple[str, OpenAICompatibleChatClient]]:
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
        state.average_latency_ms = self._smoothed_latency(
            state.average_latency_ms, latency_ms
        )
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
        state.average_latency_ms = self._smoothed_latency(
            state.average_latency_ms, latency_ms
        )
        self._record_health(
            name,
            "failure",
            consecutive_failures=state.consecutive_failures,
            latency_ms=round(latency_ms, 2),
            average_latency_ms=round(state.average_latency_ms, 2),
        )
        if state.consecutive_failures >= self.circuit_breaker_threshold:
            state.open_until = (
                self.time_provider() + self.circuit_breaker_cooldown_seconds
            )
            self._record_health(name, "circuit_open", open_until=state.open_until)

    def _latency_rank(self, name: str, original_index: int) -> tuple[float, float, int]:
        state = self.client_states.get(name)
        if state is None:
            return (-1.0, float("inf"), original_index)

        total_requests = state.successful_requests + state.failed_requests
        if total_requests == 0:
            return (-1.0, float("inf"), original_index)

        success_rate = (
            (state.successful_requests / total_requests) if total_requests else 1.0
        )
        latency = (
            state.average_latency_ms
            if state.average_latency_ms is not None
            else float("inf")
        )
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

    def _log_prompts(self, prompts) -> None:
        if not self.debug_prompts:
            return
        logger.info(
            "[LLM DEBUG] template=%s v=%s variant=%s\n"
            "--- SYSTEM PROMPT ---\n%s\n"
            "--- USER PROMPT ---\n%s\n"
            "--- END ---",
            prompts.template_name,
            prompts.template_version,
            prompts.template_variant,
            prompts.system_prompt,
            prompts.user_prompt,
        )

    def _set_last_used_descriptor(
        self, name: str, prompts, usage: dict[str, int] | None = None
    ) -> None:
        self.last_used_descriptor = {
            "provider_name": name,
            "model_used": self.client_models.get(name),
            "prompt_template_name": prompts.template_name,
            "prompt_template_version": prompts.template_version,
            "prompt_template_variant": prompts.template_variant,
            "prompt_tokens": (usage or {}).get("prompt_tokens", 0),
            "completion_tokens": (usage or {}).get("completion_tokens", 0),
        }

    @staticmethod
    def _extract_usage(raw_response: dict[str, object] | None) -> dict[str, int]:
        if not isinstance(raw_response, dict):
            return {}
        usage = raw_response.get("usage")
        if not isinstance(usage, dict):
            return {}
        extracted: dict[str, int] = {}
        for key in ("prompt_tokens", "completion_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                extracted[key] = int(value)
        return extracted

    def _record_client_failure(
        self,
        name: str,
        started_at: float,
        exc: Exception,
    ) -> None:
        if telemetry_debug_enabled():
            log_runtime_event(
                logger,
                logging.DEBUG,
                "llm.generate.failure",
                provider_name=name,
                model_used=self.client_models.get(name),
                error_type=type(exc).__name__,
                error=str(exc),
            )
        logger.warning(
            "LLM client %r failed, trying next",
            name,
            exc_info=True,
        )
        self._record_failure(
            name,
            latency_ms=(self.time_provider() - started_at) * 1000.0,
        )

    @staticmethod
    def _is_retryable_client_error(exc: LLMClientError) -> bool:
        message = str(exc).lower()
        return (
            "transport failed" in message
            or "status 429" in message
            or "status 500" in message
            or "status 502" in message
            or "status 503" in message
            or "status 504" in message
            or "internal server error" in message
            or "bad gateway" in message
            or "gateway timeout" in message
            or "engine_overloaded" in message
            or "overloaded" in message
            or "rate limit" in message
        )

    def _backoff_before_retry(self, attempt: int) -> None:
        if self.retry_backoff_seconds <= 0:
            return
        sleep(self.retry_backoff_seconds * attempt)

    def _fallback(
        self,
        request: CurriculumContentRequest,
        route: AdaptiveRouteDecision,
        grounding: list[GroundingReference],
        prompts,
        reason: str,
    ) -> list[GeneratedBlock]:
        if self.fallback_provider is None:
            raise LLMProviderError(reason)

        blocks = self.fallback_provider.generate(request, route, grounding)
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
        log_runtime_event(
            logger,
            logging.DEBUG,
            "llm.fallback",
            provider_name=self.last_used_descriptor.get("provider_name"),
            model_used=self.last_used_descriptor.get("model_used"),
            reason=reason,
        )
        if telemetry_debug_enabled():
            log_runtime_event(
                logger,
                logging.DEBUG,
                "llm.fallback.blocks",
                blocks=[block.model_dump(mode="json") for block in blocks],
            )
        return blocks

    def _parse_blocks(self, response_text: str) -> list[GeneratedBlock]:
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            cleaned = self._strip_code_fence(cleaned)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            payload = self._extract_json_payload(cleaned)
            if payload is None:
                raise LLMProviderError("LLM output was not valid JSON.") from None

        blocks_payload = payload.get("blocks")
        if not isinstance(blocks_payload, list) or not blocks_payload:
            raise LLMProviderError("LLM output did not include any generated blocks.")

        try:
            return [GeneratedBlock.model_validate(item) for item in blocks_payload]
        except (
            Exception
        ) as exc:  # pragma: no cover - pydantic already exercises the shape checks.
            raise LLMProviderError(
                "LLM output blocks did not match the Dibble schema."
            ) from exc

    def _strip_code_fence(self, value: str) -> str:
        lines = value.splitlines()
        if (
            len(lines) >= 2
            and lines[0].startswith("```")
            and lines[-1].startswith("```")
        ):
            return "\n".join(lines[1:-1]).strip()
        return value

    def _extract_json_payload(self, value: str) -> dict[str, object] | None:
        for start, char in enumerate(value):
            if char != "{":
                continue
            candidate = self._balanced_json_object(value[start:])
            if candidate is None:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "blocks" in payload:
                return payload
        return None

    @staticmethod
    def _balanced_json_object(value: str) -> str | None:
        depth = 0
        in_string = False
        escaped = False
        for index, char in enumerate(value):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return value[: index + 1]
        return None


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
            raise LLMProviderError(
                "Streamed LLM chunk did not match the Dibble schema."
            ) from exc
