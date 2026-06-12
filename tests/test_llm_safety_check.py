from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import GeneratedBlock
from dibble.services.content_moderation import ContentModerationService
from dibble.services.llm_safety_check import LLMSafetyChecker


@dataclass
class StubCompletion:
    content: str


class StubClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[str] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> StubCompletion:
        self.calls.append(user_prompt)
        return StubCompletion(self.content)


class FailingClient:
    def complete(self, *, system_prompt: str, user_prompt: str) -> StubCompletion:
        raise RuntimeError("provider down")


def _blocks(body: str = "Add the fractions 3/4 and 1/8.") -> list[GeneratedBlock]:
    return [GeneratedBlock(kind="summary", title="Fractions", body=body)]


def test_checker_parses_safe_verdict() -> None:
    checker = LLMSafetyChecker(
        client=StubClient('{"safe": true, "categories": [], "reason": null}')
    )

    verdict = checker.check_text("Adding fractions is fun.")

    assert verdict.status == "safe"
    assert verdict.categories == []


def test_checker_parses_flagged_verdict_with_code_fence() -> None:
    checker = LLMSafetyChecker(
        client=StubClient(
            '```json\n{"safe": false, "categories": ["shaming"], "reason": "Demeans the learner."}\n```'
        )
    )

    verdict = checker.check_text("You are too slow for this, give up.")

    assert verdict.status == "flagged"
    assert verdict.categories == ["shaming"]
    assert verdict.reason == "Demeans the learner."


def test_checker_unavailable_on_client_failure() -> None:
    verdict = LLMSafetyChecker(client=FailingClient()).check_text("anything")

    assert verdict.status == "unavailable"


def test_checker_unavailable_on_garbage_output() -> None:
    verdict = LLMSafetyChecker(client=StubClient("not json at all")).check_text("x")

    assert verdict.status == "unavailable"


def test_checker_skipped_without_client() -> None:
    assert LLMSafetyChecker().check_text("anything").status == "skipped"


def test_moderation_records_both_verdicts_when_llm_safe() -> None:
    service = ContentModerationService(
        llm_safety_checker=LLMSafetyChecker(
            client=StubClient('{"safe": true, "categories": [], "reason": null}')
        )
    )

    result = service.moderate_blocks(_blocks())

    assert result.status == "clear"
    assert result.llm_verdict == "safe"


def test_moderation_escalates_when_llm_flags_clear_content() -> None:
    service = ContentModerationService(
        llm_safety_checker=LLMSafetyChecker(
            client=StubClient(
                '{"safe": false, "categories": ["shaming"], "reason": "Demeaning tone."}'
            )
        )
    )

    result = service.moderate_blocks(_blocks())

    assert result.status == "flagged"
    assert result.llm_verdict == "flagged"
    assert "shaming" in result.categories
    assert any("Demeaning tone." in reason for reason in result.reasons)


def test_moderation_fails_open_when_llm_unavailable() -> None:
    service = ContentModerationService(
        llm_safety_checker=LLMSafetyChecker(client=FailingClient())
    )

    result = service.moderate_blocks(_blocks())

    assert result.status == "clear"
    assert result.llm_verdict == "unavailable"


def test_moderation_without_checker_is_unchanged() -> None:
    result = ContentModerationService().moderate_blocks(_blocks())

    assert result.status == "clear"
    assert result.llm_verdict == "skipped"
