"""Unit tests for `_helpers.expression_parser`."""

import pytest

from _helpers.expression_parser import evaluate_expression


class TestEvaluateExpression:
    """Tests for `evaluate_expression`."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1234", 1234.0),
            ("10,0", 10.0),
            ("1.234,56", 1234.56),
            ("10,0 + 2,3 - 5", 7.3),
            ("2 * 3", 6.0),
            ("10 / 4", 2.5),
            ("-5 + 10", 5.0),
            ("10 - -5", 15.0),
            ("3 * -5", -15.0),
            ("+5", 5.0),
            ("2 + 3 * 4", 14.0),
            ("(2 + 3) * 4", 20.0),
        ],
    )
    def test_evaluates_numbers_and_expressions(self, raw: str, expected: float) -> None:
        """Plain numbers and arithmetic expressions are evaluated to the expected result."""
        assert evaluate_expression(raw) == pytest.approx(expected)

    def test_raises_on_division_by_zero(self) -> None:
        """Dividing by zero is reported as an invalid expression, not a raw `ZeroDivisionError`."""
        with pytest.raises(ValueError, match="zero"):
            evaluate_expression("10 / 0")

    def test_raises_on_unbalanced_parentheses(self) -> None:
        """An unclosed parenthesis is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("(10 + 2")

    def test_raises_on_empty_input(self) -> None:
        """An empty string is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("")

    def test_raises_on_blank_input(self) -> None:
        """A whitespace-only string is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("   ")

    def test_raises_on_disallowed_power_operator(self) -> None:
        """The `**` operator is outside the +,-,*,/ whitelist and is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("2 ** 3")

    def test_raises_on_disallowed_floor_division(self) -> None:
        """The `//` operator is outside the +,-,*,/ whitelist and is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("10 // 3")

    def test_raises_on_disallowed_modulo(self) -> None:
        """The `%` operator is outside the +,-,*,/ whitelist and is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("10 % 3")

    def test_raises_on_non_numeric_identifier(self) -> None:
        """A bare identifier (not a number) is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("10 + abc")

    def test_raises_on_boolean_literal_masquerading_as_number(self) -> None:
        """`True`/`False` parse as `ast.Constant` but must not be treated as numbers."""
        with pytest.raises(ValueError):
            evaluate_expression("10 + True")

    def test_raises_on_garbage_input(self) -> None:
        """Non-expression free text is rejected."""
        with pytest.raises(ValueError):
            evaluate_expression("not a number")
