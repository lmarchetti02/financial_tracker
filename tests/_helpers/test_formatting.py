"""Unit tests for `_helpers.formatting`."""

from enum import Enum, auto

from _helpers.formatting import enum_label


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
        """Underscores in a multi-word member name become spaces."""
        assert enum_label(_Color.DARK_BLUE) == "Dark blue"
