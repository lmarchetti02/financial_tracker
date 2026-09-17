"""Unit tests for `_helpers.formatting`."""

from enum import Enum, auto

import pytest

from _helpers.formatting import enum_label, format_amount, parse_amount, parse_year, validate_profile_name


class _Color(Enum):
    """Minimal enum used to exercise `enum_label`."""

    RED = auto()
    DARK_BLUE = auto()


class TestEnumLabel:
    """Tests for `enum_label`."""

    def test_formats_a_single_word_member(self) -> None:
        """A single-word member name is title-cased."""
        assert enum_label(_Color.RED) == "Red"

    def test_formats_a_multi_word_member(self) -> None:
        """Underscores in a multi-word member name become spaces, and every word is capitalized."""
        assert enum_label(_Color.DARK_BLUE) == "Dark Blue"


class TestFormatAmount:
    """Tests for `format_amount`."""

    def test_formats_with_two_decimals_by_default(self) -> None:
        """The default precision is 2 decimal places."""
        assert format_amount(1234.5) == "1.234,50"

    def test_formats_with_zero_decimals(self) -> None:
        """`decimals=0` rounds to the nearest whole euro with no decimal part."""
        assert format_amount(1234.6, decimals=0) == "1.235"

    def test_groups_thousands_with_a_period(self) -> None:
        """Every group of three digits is separated by a period."""
        assert format_amount(1234567.89) == "1.234.567,89"

    def test_below_the_thousands_boundary_has_no_grouping(self) -> None:
        """A value under 1000 has no thousands separator."""
        assert format_amount(123.4) == "123,40"

    def test_formats_a_negative_value(self) -> None:
        """The minus sign is preserved and doesn't confuse the separator swap."""
        assert format_amount(-1234.5) == "-1.234,50"


class TestParseAmount:
    """Tests for `parse_amount`."""

    def test_parses_comma_decimal_with_no_grouping(self) -> None:
        """A comma-decimal value with no thousands separator parses correctly."""
        assert parse_amount("1234,56") == pytest.approx(1234.56)

    def test_parses_a_value_with_thousands_grouping(self) -> None:
        """Periods are stripped as thousands separators before the comma becomes the decimal point."""
        assert parse_amount("1.234,56") == pytest.approx(1234.56)

    def test_parses_a_whole_number_with_grouping(self) -> None:
        """A grouped value with no decimal part parses to the correct whole number."""
        assert parse_amount("1.234") == pytest.approx(1234.0)

    def test_round_trips_with_format_amount(self) -> None:
        """Formatting then parsing a value crossing the thousands boundary returns the original."""
        assert parse_amount(format_amount(1234567.89)) == pytest.approx(1234567.89)

    def test_raises_on_non_numeric_input(self) -> None:
        """Garbage input raises `ValueError`, matching `float`'s own behavior."""
        with pytest.raises(ValueError, match="could not convert"):
            parse_amount("not a number")


class TestParseYear:
    """Tests for `parse_year`."""

    def test_parses_a_valid_year(self) -> None:
        """A plain positive integer string parses to its `int` value."""
        assert parse_year("2026") == 2026

    def test_strips_surrounding_whitespace(self) -> None:
        """Leading/trailing whitespace is ignored."""
        assert parse_year("  2026  ") == 2026

    def test_raises_on_blank_input(self) -> None:
        """A blank string is rejected."""
        with pytest.raises(ValueError, match="positive whole number"):
            parse_year("   ")

    def test_raises_on_non_numeric_input(self) -> None:
        """Non-digit input is rejected."""
        with pytest.raises(ValueError, match="positive whole number"):
            parse_year("abcd")

    def test_raises_on_zero(self) -> None:
        """Zero is not a positive year."""
        with pytest.raises(ValueError, match="positive whole number"):
            parse_year("0")

    def test_raises_on_negative_input(self) -> None:
        """A minus sign makes the string non-digit, so it's rejected too."""
        with pytest.raises(ValueError, match="positive whole number"):
            parse_year("-5")


class TestValidateProfileName:
    """Tests for `validate_profile_name`."""

    def test_accepts_a_simple_name(self) -> None:
        """A plain alphanumeric name is accepted unchanged."""
        assert validate_profile_name("Shared") == "Shared"

    def test_strips_surrounding_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped from the returned name."""
        assert validate_profile_name("  Shared  ") == "Shared"

    def test_accepts_hyphens_and_underscores(self) -> None:
        """Hyphens and underscores are allowed alongside letters/digits."""
        assert validate_profile_name("my-profile_1") == "my-profile_1"

    def test_raises_on_blank_input(self) -> None:
        """A blank (or whitespace-only) name is rejected."""
        with pytest.raises(ValueError, match="letters, digits"):
            validate_profile_name("   ")

    def test_raises_on_disallowed_characters(self) -> None:
        """Characters outside letters/digits/hyphen/underscore are rejected."""
        with pytest.raises(ValueError, match="letters, digits"):
            validate_profile_name("shared tracker")

    def test_raises_on_path_traversal_characters(self) -> None:
        """Slashes (which could otherwise escape the app directory) are rejected."""
        with pytest.raises(ValueError, match="letters, digits"):
            validate_profile_name("../evil")
