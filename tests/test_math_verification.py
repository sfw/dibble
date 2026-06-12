from __future__ import annotations

from dibble.models.generation import (
    BlockVerification,
    GeneratedBlock,
    MultipleChoiceInteraction,
    MultipleChoiceOption,
)
from dibble.services.math_verification import MathVerificationService


def _practice_block(
    verification: BlockVerification | None = None,
    interaction: MultipleChoiceInteraction | None = None,
) -> GeneratedBlock:
    return GeneratedBlock(
        kind="practice_problem",
        title="Fraction sums",
        body="What is 3/4 + 1/8?",
        interaction=interaction,
        verification=verification,
    )


def _interaction(
    options: list[tuple[str, str]], correct_option_id: str
) -> MultipleChoiceInteraction:
    return MultipleChoiceInteraction(
        prompt="Pick the sum.",
        options=[
            MultipleChoiceOption(option_id=option_id, label=option_id, body=body)
            for option_id, body in options
        ],
        correct_option_id=correct_option_id,
    )


def test_verified_when_answer_and_distractors_check_out() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression="3/4 + 1/8",
                    answer_value="7/8",
                    distractor_values=["4/12", "1/2"],
                )
            )
        ]
    )

    assert outcome.status == "verified"
    assert outcome.issues == []
    assert outcome.checked_block_count == 1


def test_fails_when_answer_value_is_wrong() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression="3/4 + 1/8",
                    answer_value="4/12",
                    distractor_values=["1/2"],
                )
            )
        ]
    )

    assert outcome.status == "failed"
    assert any("does not evaluate" in issue for issue in outcome.issues)


def test_fails_when_distractor_equals_answer() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression="3/4 + 1/8",
                    answer_value="7/8",
                    distractor_values=["14/16"],
                )
            )
        ]
    )

    assert outcome.status == "failed"
    assert any("equals the answer key" in issue for issue in outcome.issues)


def test_partial_coverage_marks_outcome_partial() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression="12 * 4",
                    answer_value="48",
                    coverage="partial",
                )
            )
        ]
    )

    assert outcome.status == "partial"


def test_handles_latex_lite_and_mixed_numbers() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression=r"\frac{1}{2} + \frac{1}{4}",
                    answer_value="3/4",
                    distractor_values=["1 1/2", "2/6"],
                )
            )
        ]
    )

    assert outcome.status == "verified"


def test_unparseable_answer_fails() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression="import os",
                    answer_value="7/8",
                )
            )
        ]
    )

    assert outcome.status == "failed"
    assert any("could not be parsed" in issue for issue in outcome.issues)


def test_out_of_range_answer_fails() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression="10**9",
                    answer_value="1000000000",
                )
            )
        ]
    )

    assert outcome.status == "failed"
    assert any("grade-band range" in issue for issue in outcome.issues)


def test_marked_correct_option_must_match_verified_answer() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                BlockVerification(
                    answer_expression="3/4 + 1/8",
                    answer_value="7/8",
                ),
                interaction=_interaction(
                    [("A", "7/8"), ("B", "1/2")], correct_option_id="B"
                ),
            )
        ]
    )

    assert outcome.status == "failed"
    assert any("marked-correct option" in issue for issue in outcome.issues)


def test_practice_block_without_contract_is_partial() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                interaction=_interaction(
                    [("A", "7/8"), ("B", "1/2")], correct_option_id="A"
                )
            )
        ]
    )

    assert outcome.status == "partial"


def test_opportunistic_check_catches_duplicate_numeric_options() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                interaction=_interaction(
                    [("A", "7/8"), ("B", "14/16")], correct_option_id="A"
                )
            )
        ]
    )

    assert outcome.status == "failed"
    assert any("equals the correct option" in issue for issue in outcome.issues)


def test_non_practice_blocks_are_skipped() -> None:
    outcome = MathVerificationService().verify_blocks(
        [GeneratedBlock(kind="summary", title="Recap", body="Fractions add up.")]
    )

    assert outcome.status == "skipped"
    assert outcome.checked_block_count == 0


def test_reasoning_text_options_do_not_false_positive() -> None:
    outcome = MathVerificationService().verify_blocks(
        [
            _practice_block(
                interaction=_interaction(
                    [
                        ("A", "Adding numerators and denominators directly"),
                        ("B", "Finding a common denominator first"),
                    ],
                    correct_option_id="B",
                )
            )
        ]
    )

    # Options are reasoning text, not parseable values: stays partial, no failure.
    assert outcome.status == "partial"
    assert outcome.issues == []
