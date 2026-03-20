from __future__ import annotations

import re

from dibble.models.generation import (
    DeferredTextReveal,
    GeneratedBlock,
    MultipleChoiceInteraction,
    MultipleChoiceOption,
)

_OPTION_PATTERN = re.compile(
    r"\*\*Option\s+(?P<label>[A-Z])\s*\((?P<title>[^)]+)\):\*\*\s*"
    r"(?P<body>.*?)(?=(?:\n\s*\*\*Option\s+[A-Z]\s*\(|\Z))",
    re.DOTALL,
)


def normalize_generated_blocks(blocks: list[GeneratedBlock]) -> list[GeneratedBlock]:
    normalized = _assign_block_ids(blocks)
    return _normalize_markdown_multiple_choice(normalized)


def _assign_block_ids(blocks: list[GeneratedBlock]) -> list[GeneratedBlock]:
    normalized: list[GeneratedBlock] = []
    for index, block in enumerate(blocks):
        normalized.append(
            block.model_copy(
                update={"block_id": block.block_id or f"block-{index}"}
            )
        )
    return normalized


def _normalize_markdown_multiple_choice(
    blocks: list[GeneratedBlock],
) -> list[GeneratedBlock]:
    normalized: list[GeneratedBlock] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        next_block = blocks[index + 1] if index + 1 < len(blocks) else None
        interaction = _parse_multiple_choice(block, next_block)
        if interaction is None:
            normalized.append(block)
            index += 1
            continue

        normalized.append(
            block.model_copy(
                update={
                    "kind": "practice_problem",
                    "body": _clean_multiple_choice_body(block.body),
                    "interaction": interaction,
                }
            )
        )
        index += 2 if next_block is not None else 1

    return normalized


def _parse_multiple_choice(
    block: GeneratedBlock,
    next_block: GeneratedBlock | None,
) -> MultipleChoiceInteraction | None:
    matches = list(_OPTION_PATTERN.finditer(block.body))
    if len(matches) < 2 or next_block is None:
        return None

    reveal = _parse_reveal(next_block.body)
    if reveal is None:
        return None

    options = [
        MultipleChoiceOption(
            option_id=match.group("label"),
            label=f"Option {match.group('label')}",
            body=_clean_option_body(match.group("body"), match.group("title")),
        )
        for match in matches
    ]
    correct_option = options[-1].option_id
    prompt = _clean_multiple_choice_body(block.body)

    if not prompt:
        prompt = "Choose the setup that best matches the intended strategy."

    return MultipleChoiceInteraction(
        prompt=prompt,
        options=options,
        correct_option_id=correct_option,
        reveal=reveal,
    )


def _parse_reveal(body: str) -> DeferredTextReveal | None:
    prompt_match = re.search(
        r"\*\*Answer Check:\*\*\s*(?P<prompt>.*?)(?=(?:\n\s*\*\*Support:\*\*|\Z))",
        body,
        re.DOTALL,
    )
    if prompt_match is None:
        return None

    support_match = re.search(r"\*\*Support:\*\*\s*(?P<support>.*)", body, re.DOTALL)
    return DeferredTextReveal(
        prompt=_clean_inline_text(prompt_match.group("prompt")),
        support=_clean_inline_text(support_match.group("support"))
        if support_match is not None
        else None,
        placeholder="Explain what made your choice correct.",
    )


def _clean_multiple_choice_body(body: str) -> str:
    prefix = _OPTION_PATTERN.split(body, maxsplit=1)[0]
    return _clean_inline_text(prefix)


def _clean_option_body(body: str, title: str) -> str:
    stripped = body.replace("```", "").strip()
    lines = [line.rstrip() for line in stripped.splitlines() if line.strip()]
    joined = "\n".join(lines)
    joined = joined.replace("*", "")
    return f"{title}\n{joined}".strip()


def _clean_inline_text(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(text.replace("*", "").split())
    return cleaned or None
