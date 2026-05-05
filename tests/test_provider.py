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
from dibble.services.harness.policy import HarnessAuthoringPolicyBuilder
from dibble.services.harness.request_adapter import CurriculumContentRequestAdapter
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
def request_adapter():
    return CurriculumContentRequestAdapter()


@pytest.fixture
def policy_builder():
    return HarnessAuthoringPolicyBuilder()


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


@pytest.fixture
def sample_curriculum_request(
    sample_profile, sample_request, sample_route, request_adapter, policy_builder
):
    policy = policy_builder.build(
        profile=sample_profile,
        request=sample_request,
        route=sample_route,
    )
    return request_adapter.adapt(
        grade_level=sample_profile.grade_level,
        request=sample_request,
        policy=policy,
    )


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
        self, *, system_prompt: str, user_prompt: str, temperature: float | None = None
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
        self, *, system_prompt: str, user_prompt: str, temperature: float | None = None
    ):
        self.stream_calls += 1
        if self.clock is not None:
            self.clock["value"] += self.duration_seconds
        if self.error is not None:
            raise self.error
        for part in self.stream_parts:
            yield part


def test_prompt_builder_mentions_grounding_and_curriculum_request(
    sample_curriculum_request, sample_route, sample_grounding
):
    prompts = build_generation_prompts(
        sample_curriculum_request,
        sample_route,
        sample_grounding,
    )

    assert "Equivalent Fractions Foundations" in prompts.user_prompt
    assert "excerpt=Use visual fraction models" in prompts.user_prompt
    assert "Curriculum grade level:" in prompts.user_prompt
    assert "Frustration signal:" not in prompts.user_prompt
    assert "Accommodations:" not in prompts.user_prompt
    assert "Router rationale:" not in prompts.user_prompt
    assert '"blocks"' in prompts.system_prompt
    assert prompts.template_name.startswith("remedial_micro_module.")
    assert prompts.template_version == "1.0"
    assert prompts.template_variant == "baseline"


def test_prompt_builder_omits_private_router_and_learner_prompt_text(
    sample_profile, sample_grounding, request_adapter, policy_builder
):
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.step_back,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="high",
        reasons=["frustration=high total_load=0.87 confidence=0.21"],
    )
    request = GenerationRequest(
        student_id=sample_profile.student_id,
        target_kc_ids=["KC-1"],
        intent="remediation",
        learner_prompt="learner said they were confused after missing the last step",
        curriculum_context=["Equivalent fractions"],
    )
    prompts = build_generation_prompts(
        request_adapter.adapt(
            grade_level=sample_profile.grade_level,
            request=request,
            policy=policy_builder.build(
                profile=sample_profile,
                request=request,
                route=route,
            ),
        ),
        route,
        sample_grounding,
    )

    assert "frustration=high" not in prompts.user_prompt
    assert "learner said they were confused" not in prompts.user_prompt


def test_prompt_builder_omits_learner_state_explanations_from_guidance(
    sample_profile, sample_grounding, request_adapter, policy_builder
):
    route = AdaptiveRouteDecision(
        intervention_type=InterventionType.step_back,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="high",
        reasons=["support need remains high after recent Socratic turn"],
    )
    request = GenerationRequest(
        student_id=sample_profile.student_id,
        target_kc_ids=["KC-1"],
        intent="practice",
        curriculum_context=["Equivalent fractions"],
        mode_calibration=GenerationModeCalibration(
            signal="negative",
            source="session_controller",
            confidence=0.8,
            support_bias=-1,
            session_signal="negative",
            session_source="session_controller",
            session_confidence=0.8,
            session_assessment_count=1,
            session_phase="repair",
            session_arc_action="reprobe_new_angle",
            socratic_steering_action="clarify_then_check",
            rationale="test",
        ),
    )

    prompts = build_generation_prompts(
        request_adapter.adapt(
            grade_level=sample_profile.grade_level,
            request=request,
            policy=policy_builder.build(
                profile=sample_profile,
                request=request,
                route=route,
            ),
        ),
        route,
        sample_grounding,
    )

    lowered = prompts.user_prompt.lower()
    assert "support need" not in lowered
    assert "recent socratic turn" not in lowered
    assert "recent socratic follow-up" not in lowered


def test_prompt_builder_includes_distractor_and_fade_plans(
    sample_profile, sample_route, sample_grounding, request_adapter, policy_builder
):
    prompts = build_generation_prompts(
        request_adapter.adapt(
            request=GenerationRequest(
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
            grade_level=sample_profile.grade_level,
            policy=policy_builder.build(
                profile=sample_profile,
                request=GenerationRequest(
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
                route=sample_route,
            ),
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
    assert '"type":"multiple_choice"' in prompts.system_prompt
    assert '"correct_option_id":"B"' in prompts.system_prompt


def test_prompt_builder_includes_worked_example_transfer_plan(
    sample_profile, sample_route, sample_grounding, request_adapter, policy_builder
):
    prompts = build_generation_prompts(
        request_adapter.adapt(
            request=GenerationRequest(
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
            grade_level=sample_profile.grade_level,
            policy=policy_builder.build(
                profile=sample_profile,
                request=GenerationRequest(
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
                route=sample_route,
            ),
        ),
        sample_route,
        sample_grounding,
    )

    assert "transfer_plan_preserve=" in prompts.user_prompt
    assert "learner_owned_move=" in prompts.user_prompt


def test_prompt_builder_omits_private_reliability_details(
    sample_profile, sample_route, sample_grounding, request_adapter, policy_builder
):
    prompts = build_generation_prompts(
        request_adapter.adapt(
            request=GenerationRequest(
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
            grade_level=sample_profile.grade_level,
            policy=policy_builder.build(
                profile=sample_profile,
                request=GenerationRequest(
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
                route=sample_route,
            ),
        ),
        sample_route,
        sample_grounding,
    )

    assert "Reliability plan:" not in prompts.user_prompt
    assert "state=independence_ready" not in prompts.user_prompt
    assert "traits=stable" not in prompts.user_prompt
    assert "current=productive_struggle" not in prompts.user_prompt


def test_provider_uses_llm_output_when_response_is_valid(
    sample_curriculum_request,
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
        sample_curriculum_request,
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
    sample_curriculum_request,
    sample_route,
    sample_grounding,
):
    provider = LLMOrchestrationProvider(
        clients=[("primary", FakeClient(error=LLMClientError("boom")))],
        fallback_provider=MockLLMProvider(),
    )

    blocks = provider.generate(
        sample_curriculum_request,
        sample_route,
        sample_grounding,
    )

    assert blocks[0].title == "Learning focus"
    assert blocks[1].kind == "instruction"
    assert "Cue: Use visual fraction models" in blocks[0].body


def test_provider_logs_generate_failure_details_in_debug_telemetry(
    sample_request,
    sample_curriculum_request,
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
                sample_curriculum_request,
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
        max_tokens=512,
        thinking_enabled=False,
        response_format_json=True,
        transport=transport,
    )

    completion = client.complete(system_prompt="sys", user_prompt="usr")

    assert completion.finish_reason == "stop"
    assert completion.content.startswith('{"blocks"')
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "demo-model"
    assert captured["payload"]["max_tokens"] == 512
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["response_format"] == {"type": "json_object"}


def test_chat_client_retries_with_temperature_one_when_provider_requires_it():
    temperatures: list[float] = []

    def transport(url, payload, headers, timeout):
        temperatures.append(payload["temperature"])
        if len(temperatures) == 1:
            raise LLMClientError(
                'LLM request failed with status 400: {"error":{"message":"invalid temperature: only 1 is allowed for this model","type":"invalid_request_error"}}'
            )
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
        transport=transport,
    )

    completion = client.complete(system_prompt="sys", user_prompt="usr")

    assert completion.finish_reason == "stop"
    assert temperatures == [0.2, 1.0]


def test_chat_client_wraps_transport_disconnects():
    def transport(url, payload, headers, timeout):
        raise TimeoutError("provider stalled")

    client = OpenAICompatibleChatClient(
        api_base="https://example.test/v1",
        api_key="secret",
        model="demo-model",
        transport=transport,
    )

    with pytest.raises(LLMClientError, match="transport failed"):
        client.complete(system_prompt="sys", user_prompt="usr")


def test_provider_retries_transient_client_transport_failure(
    sample_curriculum_request,
    sample_route,
    sample_grounding,
):
    class FlakyClient(FakeClient):
        def complete(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            temperature: float | None = None,
        ):
            self.complete_calls += 1
            if self.complete_calls == 1:
                raise LLMClientError("LLM request transport failed: dropped")

            class Result:
                finish_reason = "stop"

                def __init__(self) -> None:
                    self.content = (
                        '{"blocks":[{"kind":"summary","title":"Ready","body":"Body"}]}'
                    )

            return Result()

    client = FlakyClient()
    provider = LLMOrchestrationProvider(clients=[("primary", client)])

    blocks = provider.generate(sample_curriculum_request, sample_route, sample_grounding)

    assert client.complete_calls == 2
    assert blocks[0].title == "Ready"


def test_provider_retries_transient_provider_overload(
    sample_curriculum_request,
    sample_route,
    sample_grounding,
):
    class OverloadedClient(FakeClient):
        def complete(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            temperature: float | None = None,
        ):
            self.complete_calls += 1
            if self.complete_calls == 1:
                raise LLMClientError(
                    'LLM request failed with status 429: {"error":{"type":"engine_overloaded_error"}}'
                )

            class Result:
                finish_reason = "stop"

                def __init__(self) -> None:
                    self.content = (
                        '{"blocks":[{"kind":"summary","title":"Ready","body":"Body"}]}'
                    )

            return Result()

    client = OverloadedClient()
    provider = LLMOrchestrationProvider(clients=[("primary", client)])

    blocks = provider.generate(sample_curriculum_request, sample_route, sample_grounding)

    assert client.complete_calls == 2
    assert blocks[0].title == "Ready"


def test_provider_uses_configured_retry_attempts_for_overload(
    sample_curriculum_request,
    sample_route,
    sample_grounding,
):
    class VeryOverloadedClient(FakeClient):
        def complete(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            temperature: float | None = None,
        ):
            self.complete_calls += 1
            if self.complete_calls < 5:
                raise LLMClientError(
                    'LLM request failed with status 429: {"error":{"type":"engine_overloaded_error"}}'
                )

            class Result:
                finish_reason = "stop"

                def __init__(self) -> None:
                    self.content = (
                        '{"blocks":[{"kind":"summary","title":"Recovered","body":"Body"}]}'
                    )

            return Result()

    client = VeryOverloadedClient()
    provider = LLMOrchestrationProvider(
        clients=[("primary", client)],
        retry_attempts=5,
    )

    blocks = provider.generate(sample_curriculum_request, sample_route, sample_grounding)

    assert client.complete_calls == 5
    assert blocks[0].title == "Recovered"


def test_provider_retries_transient_gateway_failure(
    sample_curriculum_request,
    sample_route,
    sample_grounding,
):
    class GatewayClient(FakeClient):
        def complete(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            temperature: float | None = None,
        ):
            self.complete_calls += 1
            if self.complete_calls == 1:
                raise LLMClientError("LLM request failed with status 502: Bad Gateway")

            class Result:
                finish_reason = "stop"

                def __init__(self) -> None:
                    self.content = (
                        '{"blocks":[{"kind":"summary","title":"Gateway recovered","body":"Body"}]}'
                    )

            return Result()

    client = GatewayClient()
    provider = LLMOrchestrationProvider(clients=[("primary", client)])

    blocks = provider.generate(sample_curriculum_request, sample_route, sample_grounding)

    assert client.complete_calls == 2
    assert blocks[0].title == "Gateway recovered"


def test_provider_extracts_json_blocks_from_wrapped_llm_text(
    sample_curriculum_request,
    sample_route,
    sample_grounding,
):
    client = FakeClient(
        """
        Here is the requested content:

        {
          "blocks": [
            {"kind": "summary", "title": "Ready", "body": "Body"}
          ]
        }
        """
    )
    provider = LLMOrchestrationProvider(clients=[("primary", client)])

    blocks = provider.generate(sample_curriculum_request, sample_route, sample_grounding)

    assert blocks[0].title == "Ready"


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


def test_chat_client_stream_retries_with_temperature_one_when_provider_requires_it():
    temperatures: list[float] = []

    def stream_transport(url, payload, headers, timeout):
        temperatures.append(payload["temperature"])
        if len(temperatures) == 1:
            raise LLMClientError(
                'LLM request failed with status 400: {"error":{"message":"invalid temperature: only 1 is allowed for this model","type":"invalid_request_error"}}'
            )
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
    assert temperatures == [0.2, 1.0]


def test_provider_streams_upstream_ndjson_chunks(
    sample_curriculum_request,
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
            sample_curriculum_request,
            sample_route,
            sample_grounding,
        )
    )

    assert [chunk.kind for chunk in chunks] == ["summary", "summary", "instruction"]
    assert chunks[-1].done is True


def test_provider_logs_stream_failure_details_in_debug_telemetry(
    sample_request,
    sample_curriculum_request,
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
                    sample_curriculum_request,
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
    sample_curriculum_request, sample_route, sample_grounding
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
        sample_curriculum_request,
        sample_route,
        sample_grounding,
    )

    assert blocks[0].title == "Secondary"


def test_provider_stream_fails_over_to_secondary_client(
    sample_curriculum_request,
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
            sample_curriculum_request,
            sample_route,
            sample_grounding,
        )
    )

    assert chunks[0].title == "Secondary"
    assert chunks[-1].done is True


def test_provider_opens_circuit_after_repeated_primary_failures(
    sample_curriculum_request,
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

    provider.generate(sample_curriculum_request, sample_route, sample_grounding)
    provider.generate(sample_curriculum_request, sample_route, sample_grounding)
    provider.generate(sample_curriculum_request, sample_route, sample_grounding)

    assert primary.complete_calls == 2
    assert secondary.complete_calls == 3


def test_provider_retries_primary_after_circuit_cooldown(
    sample_curriculum_request,
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

    provider.generate(sample_curriculum_request, sample_route, sample_grounding)
    current_time["value"] = 110.0
    provider.generate(sample_curriculum_request, sample_route, sample_grounding)
    current_time["value"] = 131.0
    provider.generate(sample_curriculum_request, sample_route, sample_grounding)

    assert primary.complete_calls == 2


def test_provider_round_robin_balances_healthy_clients(
    sample_curriculum_request,
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
        sample_curriculum_request, sample_route, sample_grounding
    )
    second = provider.generate(
        sample_curriculum_request, sample_route, sample_grounding
    )

    assert first[0].title == "Primary"
    assert second[0].title == "Secondary"
    assert primary.complete_calls == 1
    assert secondary.complete_calls == 1


def test_provider_latency_aware_prefers_faster_healthy_client(
    sample_curriculum_request,
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
        sample_curriculum_request, sample_route, sample_grounding
    )
    second = provider.generate(
        sample_curriculum_request, sample_route, sample_grounding
    )
    third = provider.generate(
        sample_curriculum_request, sample_route, sample_grounding
    )

    assert first[0].title == "Primary"
    assert second[0].title == "Secondary"
    assert third[0].title == "Secondary"
    assert primary.complete_calls == 1
    assert secondary.complete_calls == 2


def test_provider_hydrates_latency_history_from_health_store(
    tmp_path,
    sample_curriculum_request,
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
        sample_curriculum_request, sample_route, sample_grounding
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
        sample_curriculum_request, sample_route, sample_grounding
    )

    assert blocks[0].title == "Secondary"
    assert fresh_primary.complete_calls == 0
    assert fresh_secondary.complete_calls == 1


def test_provider_hydrates_open_circuit_from_health_store(
    tmp_path,
    sample_curriculum_request,
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
        sample_curriculum_request, sample_route, sample_grounding
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
        sample_curriculum_request, sample_route, sample_grounding
    )

    assert blocks[0].title == "Secondary"
    assert fresh_primary.complete_calls == 0
    assert fresh_secondary.complete_calls == 1
