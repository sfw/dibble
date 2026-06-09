from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol
from xml.etree import ElementTree

from xml.etree.ElementTree import ParseError

from dibble.models.generation import GeneratedBlock, GroundingReference
from dibble.services.validation.math import find_equation_checks
from dibble.services.validation.text import (
    average_word_length,
    curriculum_alignment_score,
    grounding_coverage_score,
    infer_target_grade,
    longest_sentence_word_count,
)


class ValidationRule(Protocol):
    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]: ...


DIAGRAM_BLOCK_KINDS = {"diagram", "visual_representation"}
SUPPORTED_DIAGRAM_SHAPES = {
    "compare_invariant",
    "target_invariant",
    "step_relationship",
}
ALLOWED_SVG_ELEMENTS = {
    "svg",
    "title",
    "desc",
    "rect",
    "line",
    "path",
    "text",
    "g",
    "defs",
    "marker",
}
BANNED_SVG_ATTRIBUTES = {
    "class",
    "style",
    "href",
    "src",
    "xlink:href",
}
GENERIC_LABEL_TOKENS = {
    "and",
    "caption",
    "concept",
    "diagram",
    "for",
    "img",
    "model",
    "see",
    "the",
    "this",
    "visual",
}


@dataclass(slots=True)
class GroundingRule:
    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        if grounding:
            return []
        return [
            "No curriculum grounding was found; fallback or human review is recommended."
        ]


@dataclass(slots=True)
class InstructionBlockRule:
    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        if any(
            block.kind == "instruction"
            or (
                block.kind == "practice_problem"
                and block.interaction is not None
                and block.interaction.reveal is not None
            )
            for block in blocks
        ):
            return []
        return ["Generated content is missing an instructional block."]


@dataclass(slots=True)
class LengthGuardrailRule:
    max_length: int = 600

    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        if any(_guardrail_body_length(block) > self.max_length for block in blocks):
            return ["One or more generated blocks exceed the current length guardrail."]
        return []


@dataclass(slots=True)
class CurriculumAlignmentRule:
    minimum_alignment_score: float = 0.3

    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        if not grounding:
            return []
        if not any(block.kind == "instruction" for block in blocks):
            return []

        combined_text = " ".join(_block_text(block) for block in blocks)
        score = curriculum_alignment_score(combined_text, grounding)
        if score >= self.minimum_alignment_score:
            return []

        return [
            "Generated content does not clearly reflect the retrieved curriculum grounding."
        ]


@dataclass(slots=True)
class InstructionGroundingCoverageRule:
    minimum_alignment_score: float = 0.3
    minimum_coverage_score: float = 0.2

    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        if not grounding:
            return []

        instruction_blocks = [block for block in blocks if block.kind == "instruction"]
        if not instruction_blocks:
            return []

        combined_text = " ".join(_block_text(block) for block in blocks)
        if (
            curriculum_alignment_score(combined_text, grounding)
            < self.minimum_alignment_score
        ):
            return []

        instruction_text = " ".join(
            _block_text(block) for block in instruction_blocks
        )
        coverage_score = grounding_coverage_score(instruction_text, grounding)
        if coverage_score >= self.minimum_coverage_score:
            return []

        return [
            "Instruction blocks do not clearly carry forward the retrieved curriculum language."
        ]


@dataclass(slots=True)
class GradeLevelReadabilityRule:
    max_sentence_words: int = 24
    max_average_word_length: float = 5.8

    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        target_grade = infer_target_grade(grounding)
        if target_grade is None or target_grade > 5:
            return []

        combined_text = " ".join(_block_text(block) for block in blocks)
        if not combined_text.strip():
            return []

        longest_sentence = longest_sentence_word_count(combined_text)
        average_length = average_word_length(combined_text)
        if (
            longest_sentence <= self.max_sentence_words
            and average_length <= self.max_average_word_length
        ):
            return []

        return [
            "Generated content may exceed the current reading-level heuristic for the target grade band."
        ]


@dataclass(slots=True)
class AccessibilityRule:
    max_instruction_sentences: int = 3

    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        instruction_blocks = [block for block in blocks if block.kind == "instruction"]
        if not instruction_blocks:
            return []

        for block in instruction_blocks:
            sentence_count = sum(1 for token in block.body.split(".") if token.strip())
            if sentence_count > self.max_instruction_sentences:
                return [
                    "Instruction content may be too dense for accessible scanning and chunking."
                ]
            if block.body.isupper() and len(block.body) >= 20:
                return [
                    "Instruction content relies on all-caps emphasis, which may reduce accessibility."
                ]

        return []


@dataclass(slots=True)
class NarrativeCoherenceRule:
    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        narrative_blocks = [block for block in blocks if block.kind == "narrative"]
        if not narrative_blocks:
            return []
        combined_text = " ".join(_block_text(block).lower() for block in narrative_blocks)
        if "learner" not in combined_text or "teacher" not in combined_text:
            return [
                "Narrative modality content should include both learner and teacher perspectives."
            ]
        if not any(token in combined_text for token in {"ask", "question", "what stays the same"}):
            return [
                "Narrative modality content should end in a reflective teaching move."
            ]
        return []


@dataclass(slots=True)
class DiagramAccessibilityRule:
    max_svg_characters: int = 2500
    max_svg_elements: int = 24
    max_text_elements: int = 8

    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        diagram_blocks = [
            block for block in blocks if block.kind in DIAGRAM_BLOCK_KINDS
        ]
        if not diagram_blocks:
            return []
        issues: list[str] = []
        if not any(
            block.kind == "instruction" and _display_text(block).strip()
            for block in blocks
        ):
            issues.append(
                "Diagram modality content should include an instructional companion block."
            )
        for block in diagram_blocks:
            body = block.body.strip()
            issues.extend(self._validate_svg_body(body))
        return issues

    def _validate_svg_body(self, body: str) -> list[str]:
        if not body.startswith("<svg"):
            return ["Diagram modality content body must be inline SVG."]

        issues: list[str] = []
        if len(body) > self.max_svg_characters:
            issues.append(
                "Diagram modality SVG exceeds the supported complexity limit."
            )
        lowered = body.lower()
        if "<!doctype" in lowered or "<!entity" in lowered or "<?xml" in lowered:
            issues.append(
                "Diagram modality SVG includes unsupported document-level markup."
            )
            return issues

        try:
            root = ElementTree.fromstring(body)
        except ParseError:
            return ["Diagram modality SVG is malformed and could not be parsed."]

        if _local_name(root.tag) != "svg":
            issues.append("Diagram modality content body must be inline SVG.")
            return issues

        elements = list(root.iter())
        if len(elements) > self.max_svg_elements:
            issues.append(
                "Diagram modality SVG exceeds the supported complexity limit."
            )
        text_elements = [
            element for element in elements if _local_name(element.tag) == "text"
        ]
        if len(text_elements) > self.max_text_elements:
            issues.append(
                "Diagram modality SVG exceeds the supported text-label limit."
            )

        unsupported_tags = sorted(
            {
                _local_name(element.tag)
                for element in elements
                if _local_name(element.tag) not in ALLOWED_SVG_ELEMENTS
            }
        )
        if unsupported_tags:
            issues.append(
                "Diagram modality SVG includes unsupported SVG constructs."
            )

        if any(_has_unsupported_svg_attribute(element) for element in elements):
            issues.append(
                "Diagram modality SVG includes unsupported SVG constructs."
            )

        aria_label = _attribute(root, "aria-label").strip()
        if not aria_label:
            issues.append("Diagram modality content is missing accessible SVG labeling.")

        if _attribute(root, "role").strip().lower() != "img":
            issues.append("Diagram modality SVG must declare role='img'.")

        if not _attribute(root, "viewBox").strip():
            issues.append("Diagram modality SVG must include a viewBox.")

        diagram_shape = _attribute(root, "data-diagram-shape").strip()
        if diagram_shape not in SUPPORTED_DIAGRAM_SHAPES:
            issues.append(
                "Diagram modality SVG uses an unsupported diagram shape."
            )

        title_text = _first_child_text(root, "title")
        desc_text = _first_child_text(root, "desc")
        caption_text = _caption_text(root)
        if not title_text or not desc_text or not caption_text:
            issues.append(
                "Diagram modality SVG is missing required title, description, or caption structure."
            )

        if aria_label and title_text and not _shares_label_token(
            aria_label, title_text
        ):
            issues.append(
                "Diagram modality SVG title and accessible label should describe the same concept."
            )

        return _deduplicate_issues(issues)


@dataclass(slots=True)
class ModalityCompositionRule:
    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        block_kinds = {block.kind for block in blocks}
        if "narrative" in block_kinds and "instruction" not in block_kinds:
            return [
                "Narrative composition should include a follow-through instructional block."
            ]
        if block_kinds.intersection(DIAGRAM_BLOCK_KINDS) and not any(
            block.kind in {"summary", "instruction", "worked_example"}
            and _display_text(block).strip()
            for block in blocks
        ):
            return [
                "Diagram composition should include text guidance alongside the visual."
            ]
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

    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        combined_text = " ".join(_block_text(block) for block in blocks).lower()
        if any(term in combined_text for term in self.flagged_terms):
            return [
                "Generated content includes language that should trigger safety review before delivery."
            ]
        return []


@dataclass(slots=True)
class MathSanityRule:
    def validate(
        self, blocks: list[GeneratedBlock], grounding: list[GroundingReference]
    ) -> list[str]:
        combined_text = " ".join(_block_text(block) for block in blocks)
        invalid_equations = [
            check.expression
            for check in find_equation_checks(combined_text)
            if not check.is_valid
        ]
        if invalid_equations:
            return [
                "Generated content includes a math statement that failed an arithmetic or symbolic consistency check."
            ]
        return []


def _block_text(block: GeneratedBlock) -> str:
    fragments = [block.title, _display_text(block)]
    if block.interaction is not None:
        fragments.append(block.interaction.prompt)
        fragments.extend(option.body for option in block.interaction.options)
        if block.interaction.reveal is not None:
            fragments.append(block.interaction.reveal.prompt)
            if block.interaction.reveal.support:
                fragments.append(block.interaction.reveal.support)
    return " ".join(fragment for fragment in fragments if fragment)


def _display_text(block: GeneratedBlock) -> str:
    body = block.body or ""
    if block.kind in DIAGRAM_BLOCK_KINDS and body.strip().startswith("<svg"):
        return ""
    return body


def _guardrail_body_length(block: GeneratedBlock) -> int:
    return len(_display_text(block))


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _attribute(element: ElementTree.Element, name: str) -> str:
    for attribute_name, value in element.attrib.items():
        if _local_name(attribute_name).lower() == name.lower():
            return value
    return ""


def _first_child_text(root: ElementTree.Element, tag_name: str) -> str:
    for child in root:
        if _local_name(child.tag) == tag_name:
            return "".join(child.itertext()).strip()
    return ""


def _caption_text(root: ElementTree.Element) -> str:
    for element in root.iter():
        if _local_name(element.tag) != "text":
            continue
        if _attribute(element, "data-role").strip().lower() != "caption":
            continue
        return "".join(element.itertext()).strip()
    return ""


def _has_unsupported_svg_attribute(element: ElementTree.Element) -> bool:
    for attribute_name, value in element.attrib.items():
        name = _local_name(attribute_name).lower()
        normalized_value = value.strip().lower()
        if name.startswith("on") or name in BANNED_SVG_ATTRIBUTES:
            return True
        if name.startswith("data-") and name not in {
            "data-diagram-shape",
            "data-role",
        }:
            return True
        if "javascript:" in normalized_value or normalized_value.startswith("data:"):
            return True
    return False


def _shares_label_token(left: str, right: str) -> bool:
    left_tokens = _label_tokens(left)
    right_tokens = _label_tokens(right)
    if not left_tokens or not right_tokens:
        return True
    return bool(left_tokens.intersection(right_tokens))


def _label_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 3 and token not in GENERIC_LABEL_TOKENS
    }


def _deduplicate_issues(issues: list[str]) -> list[str]:
    deduplicated: list[str] = []
    for issue in issues:
        if issue not in deduplicated:
            deduplicated.append(issue)
    return deduplicated
