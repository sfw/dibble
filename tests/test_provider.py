from uuid import uuid4

import pytest

from dibble.config import Settings
from dibble.models.generation import (
    AdaptiveRouteDecision,
    DeliveryMode,
    GenerationModeCalibration,
    GenerationRequest,
    GroundingReference,
    InterventionType,
    RequestedContentType,
    TargetKcGenerationHint,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.loader import build_generation_plugins
from dibble.services.content_provider import MockLLMProvider
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.llm_client import LLMClientError, OpenAICompatibleChatClient
from dibble.services.llm_prompting import build_generation_prompts
from dibble.services.llm_provider import LLMOrchestrationProvider
from dibble.services.provider_health import SQLiteProviderHealthStore
from dibble.services.runtime_telemetry import (
    bind_runtime_telemetry,
    reset_runtime_telemetry,
)
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database
from tests.support import build_profile


@pytest.fixture
def sample_profile():
    return LearnerProfile.model_validate(build_profile(uuid4()))


@pytest.fixture
def sample_request(sample_profile):
    return GenerationRequest(
        student_id=sample_profile.student_id,
        target_kc_ids=["KC-1"],
        intent="remediation",
        learner_prompt="Use a calm tone.",
        curriculum_context=["Equivalent fractions"],
    )


@pytest.fixture
def sample_route():
    return AdaptiveRouteDecision(
        intervention_type=InterventionType.step_back,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="high",
        reasons=["High frustration and low mastery suggest a step-back explanation."],
    )


@pytest.fixture
def sample_grounding():
    return [
        GroundingReference(
            outcome_id="CURR-1",
            title="Equivalent Fractions Foundations",
            grade_level="5",
            subject="math",
            score=2.0,
            matched_terms=["equivalent fractions", "fraction models"],
            excerpt="Use visual fraction models to explain why equivalent fractions name the same amount.",
        )
    ]


class FakeClient:
    def __init__(
        self,
        content: str | None = None,
        *,
        stream_parts: list[str] | None = None,
        error: Exception | None = None,
        clock: dict[str, float] | None = None,
        duration_seconds: float = 0.0,
    ) -> None:
        self.content = content
        self.stream_parts = stream_parts or []
        self.error = error
        self.clock = clock
        self.duration_seconds = duration_seconds
        self.complete_calls = 0
        self.stream_calls = 0

    def complete(
        self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2
    ):
        self.complete_calls += 1
        if self.clock is not None:
            self.clock["value"] += self.duration_seconds
        if self.error is not None:
            raise self.error

        class Result:
            def __init__(self, content: str) -> None:
                self.content = content

        return Result(self.content or "")

    def stream_complete(
        self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2
    ):
        self.stream_calls += 1
        if self.clock is not None:
            self.clock["value"] += self.duration_seconds
        if self.error is not None:
            raise self.error
        for part in self.stream_parts:
            yield part


def test_prompt_builder_mentions_grounding_and_preferences(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    prompts = build_generation_prompts(
        sample_profile,
        sample_request,
        sample_route,
        sample_grounding,
    )

    assert "Equivalent Fractions Foundations" in prompts.user_prompt
    assert "excerpt=Use visual fraction models" in prompts.user_prompt
    assert "slower_than_average" in prompts.user_prompt
    assert '"blocks"' in prompts.system_prompt
    assert prompts.template_name.startswith("remedial_micro_module.")
    assert prompts.template_version == "1.0"
    assert prompts.template_variant == "baseline"


def test_prompt_builder_includes_distractor_and_fade_plans(
    sample_profile, sample_route, sample_grounding
):
    prompts = build_generation_prompts(
        sample_profile,
        GenerationRequest(
            student_id=sample_profile.student_id,
            target_kc_ids=["KC-1"],
            requested_content_type=RequestedContentType.practice_problem,
            target_kc_hints=[
                TargetKcGenerationHint(
                    kc_id="KC-1",
                    kc_name="Generate equivalent fractions",
                    misconception_ids=["fraction-whole-number-bias"],
                    misconception_labels=["Whole-number bias"],
                    remediation_hints=["Compare the whole amount first."],
                )
            ],
        ),
        sample_route,
        sample_grounding,
    )

    assert "Practice distractor plan:" in prompts.user_prompt
    assert "Whole-number bias" in prompts.user_prompt
    assert "practice_distractor_blueprint=" in prompts.user_prompt
    assert "repair_cue=" in prompts.user_prompt
    assert "distractor_slots=" in prompts.user_prompt
    assert "answer_check_focus=" in prompts.user_prompt
    assert "Worked example fade plan: none" in prompts.user_prompt


def test_prompt_builder_includes_worked_example_transfer_plan(
    sample_profile, sample_route, sample_grounding
):
    prompts = build_generation_prompts(
        sample_profile,
        GenerationRequest(
            student_id=sample_profile.student_id,
            target_kc_ids=["KC-1"],
            requested_content_type=RequestedContentType.worked_example,
            target_kc_hints=[
                TargetKcGenerationHint(
                    kc_id="KC-1",
                    kc_name="Generate equivalent fractions",
                    nearby_kc_names=["Compare equivalent fractions"],
                )
            ],
        ),
        sample_route,
        sample_grounding,
    )

    assert "transfer_plan_preserve=" in prompts.user_prompt
    assert "learner_owned_move=" in prompts.user_prompt


def test_prompt_builder_includes_reliability_plan(
    sample_profile, sample_route, sample_grounding
):
    prompts = build_generation_prompts(
        sample_profile,
        GenerationRequest(
            student_id=sample_profile.student_id,
            target_kc_ids=["KC-1"],
            requested_content_type=RequestedContentType.worked_example,
            mode_calibration=GenerationModeCalibration(
                signal="positive",
                source="state_profile",
                confidence=0.72,
                support_bias=1,
                state_profile_signal="independence_ready",
                state_profile_source="state_profile",
                state_profile_overload_risk=0.24,
                state_profile_load_reliability=0.74,
                state_profile_metacognitive_reliability=0.78,
                trait_profile_signal="stable",
                trait_profile_source="trait_profile",
                trait_profile_trait_stability=0.82,
                trait_profile_challenge_tolerance=0.74,
                trait_profile_challenge_evidence_strength=0.78,
                current_evidence_signal="productive_struggle",
                current_evidence_confidence=0.7,
            ),
        ),
        sample_route,
        sample_grounding,
    )

    assert "Reliability plan:" in prompts.user_prompt
    assert "state=independence_ready" in prompts.user_prompt
    assert "traits=stable" in prompts.user_prompt
    assert "current=productive_struggle" in prompts.user_prompt


def test_provider_uses_llm_output_when_response_is_valid(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    provider = LLMOrchestrationProvider(
        clients=[
            (
                "primary",
                FakeClient(
                    """
            {
              "blocks": [
                {"kind": "summary", "title": "Focus", "body": "Equivalent fractions name the same amount."},
                {"kind": "instruction", "title": "Try it", "body": "Compare 1/2 and 2/4 with a visual model."}
              ]
            }
            """
                ),
            )
        ],
        fallback_provider=MockLLMProvider(),
    )

    blocks = provider.generate(
        sample_profile,
        sample_request,
        sample_route,
        sample_grounding,
    )

    assert [block.kind for block in blocks] == ["summary", "instruction"]
    assert blocks[0].title == "Focus"
    assert provider.last_used_descriptor["prompt_template_name"].startswith(
        "remedial_micro_module."
    )
    assert provider.last_used_descriptor["prompt_template_variant"] == "baseline"


def test_provider_falls_back_to_mock_when_llm_call_fails(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    provider = LLMOrchestrationProvider(
        clients=[("primary", FakeClient(error=LLMClientError("boom")))],
        fallback_provider=MockLLMProvider(),
    )

    blocks = provider.generate(
        sample_profile,
        sample_request,
        sample_route,
        sample_grounding,
    )

    assert blocks[0].title == "Learning focus"
    assert blocks[1].kind == "instruction"
    assert "Cue: Use visual fraction models" in blocks[0].body


def test_provider_logs_generate_failure_details_in_debug_telemetry(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
    caplog: pytest.LogCaptureFixture,
):
    provider = LLMOrchestrationProvider(
        clients=[("primary", FakeClient(error=LLMClientError("boom")))],
        fallback_provider=MockLLMProvider(),
    )
    tokens = bind_runtime_telemetry(
        session_id=sample_request.learning_session_id,
        telemetry_level="debug",
    )

    try:
        with caplog.at_level("DEBUG", logger="dibble.services.llm_provider"):
            provider.generate(
                sample_profile,
                sample_request,
                sample_route,
                sample_grounding,
            )
    finally:
        reset_runtime_telemetry(tokens)

    assert 'llm.generate.failure {"error": "boom"' in caplog.text
    assert '"error_type": "LLMClientError"' in caplog.text


def test_chat_client_parses_openai_compatible_payload():
    captured: dict[str, object] = {}

    def transport(url, payload, headers, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"blocks":[{"kind":"summary","title":"Ready","body":"Body"}]}'
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    client = OpenAICompatibleChatClient(
        api_base="https://example.test/v1",
        api_key="secret",
        model="demo-model",
        timeout_seconds=12.5,
        transport=transport,
    )

    completion = client.complete(system_prompt="sys", user_prompt="usr")

    assert completion.finish_reason == "stop"
    assert completion.content.startswith('{"blocks"')
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "demo-model"


def test_chat_client_streams_openai_compatible_sse_chunks():
    def stream_transport(url, payload, headers, timeout):
        assert payload["stream"] is True
        yield 'data: {"choices":[{"delta":{"content":"hello "}}]}\n'
        yield 'data: {"choices":[{"delta":{"content":"world"}}]}\n'
        yield "data: [DONE]\n"

    client = OpenAICompatibleChatClient(
        api_base="https://example.test/v1",
        api_key="secret",
        model="demo-model",
        stream_transport=stream_transport,
    )

    parts = list(client.stream_complete(system_prompt="sys", user_prompt="usr"))

    assert parts == ["hello ", "world"]


def test_provider_streams_upstream_ndjson_chunks(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    provider = LLMOrchestrationProvider(
        clients=[
            (
                "primary",
                FakeClient(
                    stream_parts=[
                        '{"block_index":0,"kind":"summary","title":"Focus","body_delta":"Equivalent fractions ","done":false}\n',
                        '{"block_index":0,"kind":"summary","title":"Focus","body_delta":"name the same amount.","done":true}\n',
                        '{"block_index":1,"kind":"instruction","title":"Try it","body_delta":"Compare 1/2 and 2/4.","done":true}\n',
                    ]
                ),
            )
        ],
        fallback_provider=MockLLMProvider(),
    )

    chunks = list(
        provider.stream_generate(
            sample_profile,
            sample_request,
            sample_route,
            sample_grounding,
        )
    )

    assert [chunk.kind for chunk in chunks] == ["summary", "summary", "instruction"]
    assert chunks[-1].done is True


def test_provider_logs_stream_failure_details_in_debug_telemetry(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
    caplog: pytest.LogCaptureFixture,
):
    provider = LLMOrchestrationProvider(
        clients=[("primary", FakeClient(error=LLMClientError("stream boom")))],
        fallback_provider=MockLLMProvider(),
    )
    tokens = bind_runtime_telemetry(
        session_id=sample_request.learning_session_id,
        telemetry_level="debug",
    )

    try:
        with caplog.at_level("DEBUG", logger="dibble.services.llm_provider"):
            list(
                provider.stream_generate(
                    sample_profile,
                    sample_request,
                    sample_route,
                    sample_grounding,
                )
            )
    finally:
        reset_runtime_telemetry(tokens)

    assert 'llm.stream.failure {"chunk_count": 0' in caplog.text
    assert '"error": "stream boom"' in caplog.text
    assert '"error_type": "LLMClientError"' in caplog.text
    assert '"partial_content": ""' in caplog.text


def test_plugin_loader_passes_settings_to_provider_factory(tmp_path):
    database_path = str(tmp_path / "provider-loader.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    outcome_store = SQLiteOutcomeStore(conn)
    settings = Settings(
        database_path=database_path,
        llm_api_key="secret",
        llm_model="demo-model",
    )

    plugins = build_generation_plugins(
        settings, outcome_store=outcome_store, connection=conn
    )

    assert isinstance(plugins.provider, LLMOrchestrationProvider)
    assert plugins.provider.clients


def test_provider_fails_over_to_secondary_client(
    sample_profile, sample_request, sample_route, sample_grounding
):
    provider = LLMOrchestrationProvider(
        clients=[
            ("primary", FakeClient(error=LLMClientError("primary boom"))),
            (
                "secondary",
                FakeClient(
                    """
                    {
                      "blocks": [
                        {"kind": "summary", "title": "Secondary", "body": "Fallback model answered."},
                        {"kind": "instruction", "title": "Try it", "body": "Use the secondary provider output."}
                      ]
                    }
                    """
                ),
            ),
        ],
        fallback_provider=MockLLMProvider(),
    )

    blocks = provider.generate(
        sample_profile,
        sample_request,
        sample_route,
        sample_grounding,
    )

    assert blocks[0].title == "Secondary"


def test_provider_stream_fails_over_to_secondary_client(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    provider = LLMOrchestrationProvider(
        clients=[
            ("primary", FakeClient(error=LLMClientError("primary boom"))),
            (
                "secondary",
                FakeClient(
                    stream_parts=[
                        '{"block_index":0,"kind":"summary","title":"Secondary","body_delta":"Fallback ","done":false}\n',
                        '{"block_index":0,"kind":"summary","title":"Secondary","body_delta":"streamed output.","done":true}\n',
                    ]
                ),
            ),
        ],
        fallback_provider=MockLLMProvider(),
    )

    chunks = list(
        provider.stream_generate(
            sample_profile,
            sample_request,
            sample_route,
            sample_grounding,
        )
    )

    assert chunks[0].title == "Secondary"
    assert chunks[-1].done is True


def test_provider_opens_circuit_after_repeated_primary_failures(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    current_time = {"value": 100.0}
    primary = FakeClient(error=LLMClientError("primary boom"))
    secondary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Secondary", "body": "Recovered."},
            {"kind": "instruction", "title": "Try it", "body": "Use backup."}
          ]
        }
        """
    )
    provider = LLMOrchestrationProvider(
        clients=[("primary", primary), ("secondary", secondary)],
        fallback_provider=MockLLMProvider(),
        circuit_breaker_threshold=2,
        circuit_breaker_cooldown_seconds=30.0,
        time_provider=lambda: current_time["value"],
    )

    provider.generate(sample_profile, sample_request, sample_route, sample_grounding)
    provider.generate(sample_profile, sample_request, sample_route, sample_grounding)
    provider.generate(sample_profile, sample_request, sample_route, sample_grounding)

    assert primary.complete_calls == 2
    assert secondary.complete_calls == 3


def test_provider_retries_primary_after_circuit_cooldown(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    current_time = {"value": 100.0}
    primary = FakeClient(error=LLMClientError("primary boom"))
    secondary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Secondary", "body": "Recovered."},
            {"kind": "instruction", "title": "Try it", "body": "Use backup."}
          ]
        }
        """
    )
    provider = LLMOrchestrationProvider(
        clients=[("primary", primary), ("secondary", secondary)],
        fallback_provider=MockLLMProvider(),
        circuit_breaker_threshold=1,
        circuit_breaker_cooldown_seconds=30.0,
        time_provider=lambda: current_time["value"],
    )

    provider.generate(sample_profile, sample_request, sample_route, sample_grounding)
    current_time["value"] = 110.0
    provider.generate(sample_profile, sample_request, sample_route, sample_grounding)
    current_time["value"] = 131.0
    provider.generate(sample_profile, sample_request, sample_route, sample_grounding)

    assert primary.complete_calls == 2


def test_provider_round_robin_balances_healthy_clients(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    primary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Primary", "body": "Primary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use primary."}
          ]
        }
        """
    )
    secondary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Secondary", "body": "Secondary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use secondary."}
          ]
        }
        """
    )
    provider = LLMOrchestrationProvider(
        clients=[("primary", primary), ("secondary", secondary)],
        fallback_provider=MockLLMProvider(),
        selection_strategy="round_robin",
    )

    first = provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )
    second = provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )

    assert first[0].title == "Primary"
    assert second[0].title == "Secondary"
    assert primary.complete_calls == 1
    assert secondary.complete_calls == 1


def test_provider_latency_aware_prefers_faster_healthy_client(
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    clock = {"value": 100.0}
    primary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Primary", "body": "Primary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use primary."}
          ]
        }
        """,
        clock=clock,
        duration_seconds=0.2,
    )
    secondary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Secondary", "body": "Secondary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use secondary."}
          ]
        }
        """,
        clock=clock,
        duration_seconds=0.02,
    )
    provider = LLMOrchestrationProvider(
        clients=[("primary", primary), ("secondary", secondary)],
        fallback_provider=MockLLMProvider(),
        selection_strategy="latency_aware",
        time_provider=lambda: clock["value"],
    )

    first = provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )
    second = provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )
    third = provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )

    assert first[0].title == "Primary"
    assert second[0].title == "Secondary"
    assert third[0].title == "Secondary"
    assert primary.complete_calls == 1
    assert secondary.complete_calls == 2


def test_provider_hydrates_latency_history_from_health_store(
    tmp_path,
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    database_path = str(tmp_path / "provider-latency-history.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    health_store = SQLiteProviderHealthStore(conn)
    clock = {"value": 100.0}

    warm_primary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Primary", "body": "Primary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use primary."}
          ]
        }
        """,
        clock=clock,
        duration_seconds=0.2,
    )
    warm_secondary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Secondary", "body": "Secondary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use secondary."}
          ]
        }
        """,
        clock=clock,
        duration_seconds=0.02,
    )
    warm_provider = LLMOrchestrationProvider(
        clients=[("primary", warm_primary), ("secondary", warm_secondary)],
        fallback_provider=MockLLMProvider(),
        selection_strategy="latency_aware",
        time_provider=lambda: clock["value"],
        health_store=health_store,
    )

    warm_provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )

    fresh_primary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Primary", "body": "Primary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use primary."}
          ]
        }
        """,
        clock=clock,
        duration_seconds=0.2,
    )
    fresh_secondary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Secondary", "body": "Secondary output."},
            {"kind": "instruction", "title": "Try it", "body": "Use secondary."}
          ]
        }
        """,
        clock=clock,
        duration_seconds=0.02,
    )
    hydrated_provider = LLMOrchestrationProvider(
        clients=[("primary", fresh_primary), ("secondary", fresh_secondary)],
        fallback_provider=MockLLMProvider(),
        selection_strategy="latency_aware",
        time_provider=lambda: clock["value"],
        health_store=health_store,
    )

    blocks = hydrated_provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )

    assert blocks[0].title == "Secondary"
    assert fresh_primary.complete_calls == 0
    assert fresh_secondary.complete_calls == 1


def test_provider_hydrates_open_circuit_from_health_store(
    tmp_path,
    sample_profile,
    sample_request,
    sample_route,
    sample_grounding,
):
    database_path = str(tmp_path / "provider-circuit-history.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    health_store = SQLiteProviderHealthStore(conn)
    current_time = {"value": 100.0}
    warm_provider = LLMOrchestrationProvider(
        clients=[
            ("primary", FakeClient(error=LLMClientError("primary boom"))),
            (
                "secondary",
                FakeClient(
                    """
                    {
                      "blocks": [
                        {"kind": "summary", "title": "Secondary", "body": "Recovered."},
                        {"kind": "instruction", "title": "Try it", "body": "Use backup."}
                      ]
                    }
                    """
                ),
            ),
        ],
        fallback_provider=MockLLMProvider(),
        circuit_breaker_threshold=1,
        circuit_breaker_cooldown_seconds=30.0,
        time_provider=lambda: current_time["value"],
        health_store=health_store,
    )

    warm_provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )

    fresh_primary = FakeClient(error=LLMClientError("primary still down"))
    fresh_secondary = FakeClient(
        """
        {
          "blocks": [
            {"kind": "summary", "title": "Secondary", "body": "Recovered."},
            {"kind": "instruction", "title": "Try it", "body": "Use backup."}
          ]
        }
        """
    )
    hydrated_provider = LLMOrchestrationProvider(
        clients=[("primary", fresh_primary), ("secondary", fresh_secondary)],
        fallback_provider=MockLLMProvider(),
        circuit_breaker_threshold=1,
        circuit_breaker_cooldown_seconds=30.0,
        time_provider=lambda: current_time["value"],
        health_store=health_store,
    )

    blocks = hydrated_provider.generate(
        sample_profile, sample_request, sample_route, sample_grounding
    )

    assert blocks[0].title == "Secondary"
    assert fresh_primary.complete_calls == 0
    assert fresh_secondary.complete_calls == 1
