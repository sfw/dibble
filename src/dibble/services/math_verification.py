"""Symbolic verification of generated practice and assessment items.

Every numeric practice item must carry a machine-checkable ``verification``
contract (answer expression, claimed answer value, distractor values). This
service parses those expressions with sympy and confirms the key is correct,
every distractor differs from the key, and values stay inside the grade-band
range. Items that fail are regenerated — never repaired — by the generation
engine. (POC roadmap 1.3)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    parse_expr,
    standard_transformations,
)

from dibble.models.generation import GeneratedBlock

VERIFICATION_FAILED_EVENT_TYPE = "generation.verification.failed"

_PRACTICE_BLOCK_KINDS = {"practice_problem", "practice", "assessment_probe"}
_TRANSFORMATIONS = (*standard_transformations, convert_xor)
_ALLOWED_FUNCTIONS = {
    "sqrt": sympy.sqrt,
    "Abs": sympy.Abs,
    "abs": sympy.Abs,
    "gcd": sympy.gcd,
    "lcm": sympy.lcm,
    "Rational": sympy.Rational,
    "pi": sympy.pi,
}
# After LaTeX-lite normalisation an expression may only contain digits,
# arithmetic operators, parentheses, whitespace, decimal points, commas,
# percent signs, and short function names.
_SAFE_EXPRESSION_PATTERN = re.compile(r"^[0-9A-Za-z_+\-*/^(). ,%]*$")
_MAX_EXPRESSION_LENGTH = 200


class MathVerificationOutcome(BaseModel):
    status: Literal["verified", "partial", "failed", "fallback", "skipped"] = "skipped"
    issues: list[str] = Field(default_factory=list)
    checked_block_count: int = 0


@dataclass(slots=True)
class MathVerificationService:
    """Verifies generated blocks; pure computation, no side effects."""

    minimum_value: float = -1_000_000.0
    maximum_value: float = 1_000_000.0
    equality_tolerance: float = 1e-9

    def verify_blocks(self, blocks: list[GeneratedBlock]) -> MathVerificationOutcome:
        issues: list[str] = []
        checked = 0
        any_partial = False
        for block in blocks:
            if block.verification is not None:
                checked += 1
                block_issues, partial = self._verify_block(block)
                issues.extend(block_issues)
                any_partial = any_partial or partial
            elif self._is_practice_block(block):
                checked += 1
                block_issues = self._opportunistic_interaction_check(block)
                issues.extend(block_issues)
                # No structured contract: only the distractor inequality could
                # be checked, so the item is at best partially verified.
                any_partial = True
        if checked == 0:
            return MathVerificationOutcome(status="skipped")
        if issues:
            return MathVerificationOutcome(
                status="failed", issues=issues, checked_block_count=checked
            )
        return MathVerificationOutcome(
            status="partial" if any_partial else "verified",
            checked_block_count=checked,
        )

    # -- single block --------------------------------------------------------

    def _verify_block(self, block: GeneratedBlock) -> tuple[list[str], bool]:
        verification = block.verification
        assert verification is not None
        issues: list[str] = []
        label = block.title or block.kind

        answer_value = self._parse(verification.answer_value)
        if verification.answer_value and answer_value is None:
            issues.append(
                f"{label}: answer value {verification.answer_value!r} could not be parsed."
            )

        if verification.answer_expression:
            answer_expression = self._parse(verification.answer_expression)
            if answer_expression is None:
                issues.append(
                    f"{label}: answer expression {verification.answer_expression!r} could not be parsed."
                )
            elif answer_value is not None and not self._equal(
                answer_expression, answer_value
            ):
                issues.append(
                    f"{label}: answer expression {verification.answer_expression!r} "
                    f"does not evaluate to the claimed answer {verification.answer_value!r}."
                )

        if answer_value is not None:
            range_issue = self._range_issue(answer_value, label=label)
            if range_issue is not None:
                issues.append(range_issue)
            for distractor in verification.distractor_values:
                distractor_value = self._parse(distractor)
                if distractor_value is None:
                    issues.append(
                        f"{label}: distractor {distractor!r} could not be parsed."
                    )
                    continue
                if self._equal(distractor_value, answer_value):
                    issues.append(
                        f"{label}: distractor {distractor!r} equals the answer key."
                    )

        if (
            answer_value is not None
            and block.interaction is not None
            and block.interaction.options
        ):
            issues.extend(
                self._interaction_consistency_issues(
                    block=block, answer_value=answer_value, label=label
                )
            )

        partial = verification.coverage == "partial"
        return issues, partial

    def _interaction_consistency_issues(
        self,
        *,
        block: GeneratedBlock,
        answer_value: sympy.Expr,
        label: str,
    ) -> list[str]:
        interaction = block.interaction
        assert interaction is not None
        issues: list[str] = []
        for option in interaction.options:
            option_value = self._parse(option.body)
            if option_value is None:
                continue
            is_correct_option = option.option_id == interaction.correct_option_id
            if is_correct_option and not self._equal(option_value, answer_value):
                issues.append(
                    f"{label}: the marked-correct option {option.body!r} does not "
                    f"match the verified answer."
                )
            if not is_correct_option and self._equal(option_value, answer_value):
                issues.append(
                    f"{label}: option {option.body!r} equals the answer key but is "
                    f"not marked correct."
                )
        return issues

    def _opportunistic_interaction_check(self, block: GeneratedBlock) -> list[str]:
        """Without a verification contract we can still confirm no distractor
        equals the marked-correct option when option bodies parse as math."""
        interaction = block.interaction
        if interaction is None or not interaction.options:
            return []
        correct = next(
            (
                option
                for option in interaction.options
                if option.option_id == interaction.correct_option_id
            ),
            None,
        )
        if correct is None:
            return [
                f"{block.title or block.kind}: the correct option id "
                f"{interaction.correct_option_id!r} does not match any option."
            ]
        correct_value = self._parse(correct.body)
        if correct_value is None:
            return []
        issues: list[str] = []
        for option in interaction.options:
            if option.option_id == correct.option_id:
                continue
            option_value = self._parse(option.body)
            if option_value is not None and self._equal(option_value, correct_value):
                issues.append(
                    f"{block.title or block.kind}: distractor option {option.body!r} "
                    f"equals the correct option {correct.body!r}."
                )
        return issues

    # -- parsing -----------------------------------------------------------

    def _parse(self, raw: str | None) -> sympy.Expr | None:
        if raw is None:
            return None
        normalized = self._normalize(raw)
        if not normalized or len(normalized) > _MAX_EXPRESSION_LENGTH:
            return None
        if not _SAFE_EXPRESSION_PATTERN.match(normalized):
            return None
        try:
            expression = parse_expr(
                normalized,
                transformations=_TRANSFORMATIONS,
                local_dict=dict(_ALLOWED_FUNCTIONS),
                evaluate=True,
            )
        except Exception:  # noqa: BLE001 - any parse failure means unverifiable
            return None
        if expression is None or expression.free_symbols:
            # Free symbols mean the expression is not a closed-form value the
            # grade band can answer with — treat as unparseable.
            return None
        return expression

    def _normalize(self, raw: str) -> str:
        text = raw.strip()
        text = text.replace("$", "")
        # LaTeX-lite conversions for the notation the band actually uses.
        text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", text)
        text = re.sub(r"\\d?frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", text)
        text = text.replace("\\times", "*").replace("\\cdot", "*")
        text = text.replace("\\div", "/")
        text = text.replace("\\left", "").replace("\\right", "")
        text = text.replace("×", "*").replace("÷", "/").replace("−", "-")
        text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # thousands separators
        # Mixed numbers like "1 1/2" become "(1 + 1/2)".
        text = re.sub(
            r"\b(\d+)\s+(\d+)\s*/\s*(\d+)\b",
            r"(\1 + (\2)/(\3))",
            text,
        )
        if text.endswith("%"):
            text = f"({text[:-1]})/100"
        return text.strip()

    # -- comparison --------------------------------------------------------

    def _equal(self, left: sympy.Expr, right: sympy.Expr) -> bool:
        try:
            difference = sympy.simplify(left - right)
            if difference == 0:
                return True
            numeric = sympy.Abs(difference).evalf()
            if numeric.is_number:
                return bool(numeric < self.equality_tolerance)
            return False
        except Exception:  # noqa: BLE001 - comparison failure means not equal
            return False

    def _range_issue(self, value: sympy.Expr, *, label: str) -> str | None:
        try:
            numeric = float(value.evalf())
        except (TypeError, ValueError):
            return None
        if numeric < self.minimum_value or numeric > self.maximum_value:
            return (
                f"{label}: answer {numeric} falls outside the expected "
                f"grade-band range."
            )
        return None

    def _is_practice_block(self, block: GeneratedBlock) -> bool:
        return block.kind in _PRACTICE_BLOCK_KINDS or (
            block.interaction is not None and bool(block.interaction.options)
        )
