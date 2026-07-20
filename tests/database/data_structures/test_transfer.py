"""Unit tests for `database.data_structures.transfer`."""

import pytest

from database.data_structures.transfer import Kind, Transfer


def make_transfer(**overrides: object) -> Transfer:
    """Builds a `:class:Transfer` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 1,
        "kind": Kind.LOAN,
        "description": "test transfer",
        "source": "Bank A",
        "destination": None,
        "amount": 100.0,
    }
    defaults.update(overrides)
    return Transfer(**defaults)


class TestTransfer:
    """Tests for `Transfer`."""

    def test_construction_succeeds_with_only_source(self) -> None:
        """A transfer with a source and no destination is valid."""
        transfer = make_transfer(source="Bank A", destination=None)
        assert transfer.source == "Bank A"
        assert transfer.destination is None

    def test_construction_succeeds_with_only_destination(self) -> None:
        """A transfer with a destination and no source is valid."""
        transfer = make_transfer(source=None, destination="Bank B")
        assert transfer.source is None
        assert transfer.destination == "Bank B"

    def test_construction_fails_when_both_source_and_destination_are_none(self) -> None:
        """A transfer without a source or a destination is rejected."""
        with pytest.raises(ValueError, match="source or a destination"):
            make_transfer(source=None, destination=None)
