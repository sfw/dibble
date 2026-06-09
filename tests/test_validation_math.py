from dibble.services.validation.math import find_equation_checks


def test_find_equation_checks_validates_fraction_and_parentheses_arithmetic():
    checks = find_equation_checks(
        "Use the model to confirm that (1/2) + (1/4) = 3/4 and 2*(3 + 4) = 14."
    )

    assert [check.expression for check in checks] == [
        "(1/2) + (1/4) = 3/4",
        "2*(3 + 4) = 14",
    ]
    assert all(check.is_valid is True for check in checks)


def test_find_equation_checks_recognizes_symbolic_identity_and_skips_generic_equation():
    checks = find_equation_checks(
        "A learner wrote 2*x + 3 = x + x + 3 and x/2 + 1 = x/2 + 2."
    )

    assert [check.is_valid for check in checks] == [True, None]
    assert checks[0].verifier == "linear_symbolic"
    assert checks[1].verifier == "linear_symbolic"


def test_find_equation_checks_ignores_unsupported_nonlinear_expression():
    checks = find_equation_checks("Check whether x^2 + 1 = x + 1 looks right.")

    assert len(checks) == 1
    assert checks[0].expression == "x^2 + 1 = x + 1"
    assert checks[0].is_valid is None
    assert checks[0].verifier == "unsupported"
