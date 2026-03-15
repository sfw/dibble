from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dibble.models.generation import GeneratedBlock, GroundingReference
from dibble.services.validation.math import find_equation_checks
from dibble.services.validation.text import (
    average_word_length,
    contains_grounding_language,
    infer_target_grade,
    longest_sentence_word_count,
)


class ValidationRule(Protocol):
    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]: ...


@dataclass(slots=True)
class GroundingRule:
    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        if grounding:
            return []
        return ["No curriculum grounding was found; fallback or human review is recommended."]


@dataclass(slots=True)
class InstructionBlockRule:
    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        if any(block.kind == "instruction" for block in blocks):
            return []
        return ["Generated content is missing an instructional block."]


@dataclass(slots=True)
class LengthGuardrailRule:
    max_length: int = 600

    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        if any(len(block.body) > self.max_length for block in blocks):
            return ["One or more generated blocks exceed the current length guardrail."]
        return []


@dataclass(slots=True)
class CurriculumAlignmentRule:
    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        if not grounding:
            return []
        if not any(block.kind == "instruction" for block in blocks):
            return []

        combined_text = " ".join(f"{block.title} {block.body}" for block in blocks)
        if contains_grounding_language(combined_text, grounding):
            return []

        return ["Generated content does not clearly reflect the retrieved curriculum grounding."]


@dataclass(slots=True)
class GradeLevelReadabilityRule:
    max_sentence_words: int = 24
    max_average_word_length: float = 5.8

    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        target_grade = infer_target_grade(grounding)
        if target_grade is None or target_grade > 5:
            return []

        combined_text = " ".join(block.body for block in blocks)
        if not combined_text.strip():
            return []

        longest_sentence = longest_sentence_word_count(combined_text)
        average_length = average_word_length(combined_text)
        if longest_sentence <= self.max_sentence_words and average_length <= self.max_average_word_length:
            return []

        return ["Generated content may exceed the current reading-level heuristic for the target grade band."]


@dataclass(slots=True)
class AccessibilityRule:
    max_instruction_sentences: int = 3

    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        instruction_blocks = [block for block in blocks if block.kind == "instruction"]
        if not instruction_blocks:
            return []

        for block in instruction_blocks:
            sentence_count = sum(1 for token in block.body.split(".") if token.strip())
            if sentence_count > self.max_instruction_sentences:
                return ["Instruction content may be too dense for accessible scanning and chunking."]
            if block.body.isupper() and len(block.body) >= 20:
                return ["Instruction content relies on all-caps emphasis, which may reduce accessibility."]

        return []


@dataclass(slots=True)
class SafetyLanguageRule:
    flagged_terms: tuple[str, ...] = (
        "ignore safety",
        "punish",
        "shame",
        "diagnose",
        "withhold support",
    )

    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        combined_text = " ".join(f"{block.title} {block.body}" for block in blocks).lower()
        if any(term in combined_text for term in self.flagged_terms):
            return ["Generated content includes language that should trigger safety review before delivery."]
        return []


@dataclass(slots=True)
class MathSanityRule:
    def validate(self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]) -> list[str]:
        combined_text = " ".join(block.body for block in blocks)
        invalid_equations = [check.expression for check in find_equation_checks(combined_text) if not check.is_valid]
        if invalid_equations:
            return ["Generated content includes a math statement that failed a basic arithmetic check."]
        return []
