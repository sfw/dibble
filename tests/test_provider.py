from uuid import uuid4

import pytest

from dibble.config import Settings
from dibble.models.generation import AdaptiveRouteDecision, DeliveryMode, GenerationRequest, InterventionType
from dibble.models.profile import LearnerProfile
from dibble.plugins.loader import build_generation_plugins
from dibble.services.content_provider import MockLLMProvider
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.llm_client import LLMClientError, OpenAICompatibleChatClient
from dibble.services.llm_prompting import build_generation_prompts
from dibble.services.llm_provider import LLMOrchestrationProvider
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


class FakeClient:
    def __init__(
        self,
        content: str | None = None,
        *,
        stream_parts: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.content = content
        self.stream_parts = stream_parts or []
        self.error = error

    def complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        if self.error is not None:
            raise self.error

        class Result:
            def __init__(self, content: str) -> None:
                self.content = content

        return Result(self.content or "")

    def stream_complete(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        if self.error is not None:
            raise self.error
        for part in self.stream_parts:
            yield part


def test_prompt_builder_mentions_grounding_and_preferences(sample_profile, sample_request, sample_route):
    prompts = build_generation_prompts(
        sample_profile,
        sample_request,
        sample_route,
        ["Equivalent Fractions Foundations"],
    )

    assert "Equivalent Fractions Foundations" in prompts.user_prompt
    assert "slower_than_average" in prompts.user_prompt
    assert '"blocks"' in prompts.system_prompt


def test_provider_uses_llm_output_when_response_is_valid(sample_profile, sample_request, sample_route):
    provider = LLMOrchestrationProvider(
        clients=[("primary", FakeClient(
            """
            {
              "blocks": [
                {"kind": "summary", "title": "Focus", "body": "Equivalent fractions name the same amount."},
                {"kind": "instruction", "title": "Try it", "body": "Compare 1/2 and 2/4 with a visual model."}
              ]
            }
            """
        ))],
        fallback_provider=MockLLMProvider(),
    )

    blocks = provider.generate(
        sample_profile,
        sample_request,
        sample_route,
        ["Equivalent Fractions Foundations"],
    )

    assert [block.kind for block in blocks] == ["summary", "instruction"]
    assert blocks[0].title == "Focus"


def test_provider_falls_back_to_mock_when_llm_call_fails(sample_profile, sample_request, sample_route):
    provider = LLMOrchestrationProvider(
        clients=[("primary", FakeClient(error=LLMClientError("boom")))],
        fallback_provider=MockLLMProvider(),
    )

    blocks = provider.generate(
        sample_profile,
        sample_request,
        sample_route,
        ["Equivalent Fractions Foundations"],
    )

    assert blocks[0].title == "Learning focus"
    assert blocks[1].kind == "instruction"


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


def test_provider_streams_upstream_ndjson_chunks(sample_profile, sample_request, sample_route):
    provider = LLMOrchestrationProvider(
        clients=[("primary", FakeClient(
            stream_parts=[
                '{"block_index":0,"kind":"summary","title":"Focus","body_delta":"Equivalent fractions ","done":false}\n',
                '{"block_index":0,"kind":"summary","title":"Focus","body_delta":"name the same amount.","done":true}\n',
                '{"block_index":1,"kind":"instruction","title":"Try it","body_delta":"Compare 1/2 and 2/4.","done":true}\n',
            ]
        ))],
        fallback_provider=MockLLMProvider(),
    )

    chunks = list(
        provider.stream_generate(
            sample_profile,
            sample_request,
            sample_route,
            ["Equivalent Fractions Foundations"],
        )
    )

    assert [chunk.kind for chunk in chunks] == ["summary", "summary", "instruction"]
    assert chunks[-1].done is True


def test_plugin_loader_passes_settings_to_provider_factory(tmp_path):
    database_path = str(tmp_path / "provider-loader.db")
    ensure_database(database_path)
    curriculum_store = SQLiteCurriculumStore(database_path)
    settings = Settings(
        database_path=database_path,
        llm_api_key="secret",
        llm_model="demo-model",
    )

    plugins = build_generation_plugins(settings, curriculum_store=curriculum_store)

    assert isinstance(plugins.provider, LLMOrchestrationProvider)
    assert plugins.provider.clients


def test_provider_fails_over_to_secondary_client(sample_profile, sample_request, sample_route):
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
        ["Equivalent Fractions Foundations"],
    )

    assert blocks[0].title == "Secondary"


def test_provider_stream_fails_over_to_secondary_client(sample_profile, sample_request, sample_route):
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
            ["Equivalent Fractions Foundations"],
        )
    )

    assert chunks[0].title == "Secondary"
    assert chunks[-1].done is True
