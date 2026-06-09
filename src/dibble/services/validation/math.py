from __future__ import annotations

import ast
from dataclasses import dataclass
from fractions import Fraction
import re

_EQUATION_ALLOWED_CHARS = frozenset(
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_+-*/^().= \t×÷−"
)
_MATH_TOKEN_PATTERN = re.compile(r"[\dA-Za-z]")
_NUMERIC_MULTIPLICATION_X_PATTERN = re.compile(r"(?<=\d)\s*[xX]\s*(?=\d)")
_EQUATION_CLAUSE_SPLIT_PATTERN = re.compile(
    r"(?:[.;?!]\s*|,\s*|\b(?:and|then|because|therefore|so)\b)"
)


@dataclass(frozen=True, slots=True)
class EquationCheck:
    expression: str
    is_valid: bool | None
    verifier: str


@dataclass(frozen=True, slots=True)
class LinearExpression:
    coefficients: dict[str, Fraction]
    constant: Fraction = Fraction(0, 1)

    def add(self, other: LinearExpression) -> LinearExpression:
        coefficients = dict(self.coefficients)
        for name, value in other.coefficients.items():
            coefficients[name] = coefficients.get(name, Fraction(0, 1)) + value
            if coefficients[name] == 0:
                del coefficients[name]
        return LinearExpression(
            coefficients=coefficients,
            constant=self.constant + other.constant,
        )

    def subtract(self, other: LinearExpression) -> LinearExpression:
        return self.add(other.scale(Fraction(-1, 1)))

    def scale(self, scalar: Fraction) -> LinearExpression:
        if scalar == 0:
            return LinearExpression(coefficients={})
        return LinearExpression(
            coefficients={
                name: value * scalar for name, value in self.coefficients.items()
            },
            constant=self.constant * scalar,
        )

    def is_zero(self) -> bool:
        return self.constant == 0 and not self.coefficients


def find_equation_checks(text: str) -> list[EquationCheck]:
    checks: list[EquationCheck] = []
    seen: set[str] = set()

    for candidate in _extract_equation_candidates(text):
        if candidate in seen:
            continue
        seen.add(candidate)
        checks.append(_evaluate_equation(candidate))

    return checks


def _extract_equation_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for clause in _EQUATION_CLAUSE_SPLIT_PATTERN.split(text):
        candidate = clause.strip()
        if "=" not in candidate:
            continue
        if not _looks_math_like(candidate):
            continue
        candidates.append(candidate)
    return candidates


def _looks_math_like(candidate: str) -> bool:
    if "=" not in candidate:
        return False
    left, right = [part.strip() for part in candidate.split("=", 1)]
    if not left or not right:
        return False
    if not _MATH_TOKEN_PATTERN.search(left) or not _MATH_TOKEN_PATTERN.search(right):
        return False
    return any(token in candidate for token in "+-*/^×÷") or any(
        char.isdigit() for char in candidate
    )


def _evaluate_equation(candidate: str) -> EquationCheck:
    raw_left, raw_right = [part.strip() for part in candidate.split("=", 1)]
    raw_left = _trim_left_expression(raw_left)
    raw_right = _trim_right_expression(raw_right)
    expression = f"{raw_left} = {raw_right}".strip()
    left = _parse_linear_expression(_normalize_expression(raw_left))
    right = _parse_linear_expression(_normalize_expression(raw_right))
    if left is None or right is None:
        return EquationCheck(
            expression=expression,
            is_valid=None,
            verifier="unsupported",
        )
    if left.coefficients or right.coefficients:
        difference = left.subtract(right)
        return EquationCheck(
            expression=expression,
            is_valid=True if difference.is_zero() else None,
            verifier="linear_symbolic",
        )
    return EquationCheck(
        expression=expression,
        is_valid=left.subtract(right).is_zero(),
        verifier="linear_symbolic",
    )


def _normalize_expression(source: str) -> str:
    normalized = source.replace("−", "-").replace("×", "*").replace("÷", "/")
    normalized = normalized.replace("^", "**").replace(",", "")
    normalized = _NUMERIC_MULTIPLICATION_X_PATTERN.sub("*", normalized)
    return normalized.strip()


def _parse_linear_expression(source: str) -> LinearExpression | None:
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError:
        return None
    return _from_ast(tree.body)


def _trim_left_expression(source: str) -> str:
    tokens = source.split()
    if not tokens:
        return source.strip()
    for index in range(len(tokens)):
        candidate = " ".join(tokens[index:]).strip()
        if _has_valid_expression_syntax(candidate):
            return candidate
    return source.strip()


def _trim_right_expression(source: str) -> str:
    tokens = source.split()
    if not tokens:
        return source.strip()
    for index in range(len(tokens), 0, -1):
        candidate = " ".join(tokens[:index]).strip()
        if _has_valid_expression_syntax(candidate):
            return candidate
    return source.strip()


def _has_valid_expression_syntax(source: str) -> bool:
    try:
        tree = ast.parse(_normalize_expression(source), mode="eval")
    except SyntaxError:
        return False
    return all(len(identifier) == 1 for identifier in _expression_identifiers(tree))


def _expression_identifiers(tree: ast.AST) -> set[str]:
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }


def _from_ast(node: ast.AST) -> LinearExpression | None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return None
        if isinstance(node.value, int):
            return LinearExpression(coefficients={}, constant=Fraction(node.value, 1))
        if isinstance(node.value, float):
            return LinearExpression(
                coefficients={}, constant=Fraction(str(node.value))
            )
        return None

    if isinstance(node, ast.Name):
        return LinearExpression(coefficients={node.id: Fraction(1, 1)})

    if isinstance(node, ast.UnaryOp):
        operand = _from_ast(node.operand)
        if operand is None:
            return None
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return operand.scale(Fraction(-1, 1))
        return None

    if isinstance(node, ast.BinOp):
        left = _from_ast(node.left)
        right = _from_ast(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left.add(right)
        if isinstance(node.op, ast.Sub):
            return left.subtract(right)
        if isinstance(node.op, ast.Mult):
            return _multiply_linear(left, right)
        if isinstance(node.op, ast.Div):
            return _divide_linear(left, right)
        if isinstance(node.op, ast.Pow):
            return _power_linear(left, right)
        return None

    return None


def _multiply_linear(
    left: LinearExpression, right: LinearExpression
) -> LinearExpression | None:
    if left.coefficients and right.coefficients:
        return None
    if left.coefficients:
        return left.scale(right.constant)
    if right.coefficients:
        return right.scale(left.constant)
    return LinearExpression(coefficients={}, constant=left.constant * right.constant)


def _divide_linear(
    left: LinearExpression, right: LinearExpression
) -> LinearExpression | None:
    if right.coefficients or right.constant == 0:
        return None
    return left.scale(Fraction(1, 1) / right.constant)


def _power_linear(
    left: LinearExpression, right: LinearExpression
) -> LinearExpression | None:
    if right.coefficients:
        return None
    if right.constant == 0:
        return LinearExpression(coefficients={}, constant=Fraction(1, 1))
    if right.constant == 1:
        return left
    if left.coefficients:
        return None
    exponent = right.constant
    if exponent.denominator != 1:
        return None
    exponent_value = exponent.numerator
    if exponent_value < 0:
        return None
    return LinearExpression(coefficients={}, constant=left.constant**exponent_value)
