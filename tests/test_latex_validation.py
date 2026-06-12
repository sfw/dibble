from __future__ import annotations

from dibble.models.generation import GeneratedBlock
from dibble.services.validation.rules import LatexWellFormednessRule


def _block(body: str) -> GeneratedBlock:
    return GeneratedBlock(kind="summary", title="Math block", body=body)


def test_well_formed_latex_passes() -> None:
    issues = LatexWellFormednessRule().validate(
        [
            _block(
                r"Add the fractions: $\frac{3}{4} + \frac{1}{8}$ equals $\frac{7}{8}$."
            )
        ],
        [],
    )

    assert issues == []


def test_display_math_passes() -> None:
    issues = LatexWellFormednessRule().validate(
        [_block(r"Solve: $$\frac{1}{2} \times 6 = 3$$")],
        [],
    )

    assert issues == []


def test_unbalanced_inline_delimiter_is_flagged() -> None:
    issues = LatexWellFormednessRule().validate(
        [_block(r"The sum is $\frac{7}{8} and that is the answer.")],
        [],
    )

    assert any("unbalanced inline math delimiter" in issue for issue in issues)


def test_unbalanced_display_delimiter_is_flagged() -> None:
    issues = LatexWellFormednessRule().validate(
        [_block(r"$$\frac{1}{2} + \frac{1}{4}")],
        [],
    )

    assert any("unbalanced display math delimiter" in issue for issue in issues)


def test_unbalanced_braces_are_flagged() -> None:
    issues = LatexWellFormednessRule().validate(
        [_block(r"The sum is $\frac{3}{4 + \frac{1}{8}$.")],
        [],
    )

    assert any("unbalanced braces" in issue for issue in issues)


def test_unknown_command_is_flagged() -> None:
    issues = LatexWellFormednessRule().validate(
        [_block(r"The answer is $\fraktur{7}{8}$.")],
        [],
    )

    assert any("unsupported LaTeX command" in issue for issue in issues)


def test_plain_text_is_ignored() -> None:
    issues = LatexWellFormednessRule().validate(
        [_block("Three quarters plus one eighth equals seven eighths.")],
        [],
    )

    assert issues == []
