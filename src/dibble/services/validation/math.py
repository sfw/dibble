from __future__ import annotations

import re
from dataclasses import dataclass


_EQUATION_PATTERN = re.compile(r"(?P<left>\d+)\s*(?P<operator>[+\-*/xX])\s*(?P<right>\d+)\s*=\s*(?P<result>\d+)")


@dataclass(frozen=True, slots=True)
class EquationCheck:
    expression: str
    is_valid: bool


def find_equation_checks(text: str) -> list[EquationCheck]:
    checks: list[EquationCheck] = []

    for match in _EQUATION_PATTERN.finditer(text):
        left = int(match.group("left"))
        right = int(match.group("right"))
        result = int(match.group("result"))
        operator = match.group("operator").lower()
        checks.append(
            EquationCheck(
                expression=match.group(0),
                is_valid=_evaluate(left, right, operator) == result,
            )
        )

    return checks


def _evaluate(left: int, right: int, operator: str) -> int | None:
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator in {"*", "x"}:
        return left * right
    if operator == "/" and right != 0 and left % right == 0:
        return left // right
    return None
