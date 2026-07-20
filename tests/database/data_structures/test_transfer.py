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

    @pytest.mark.parametrize("month", [0, 13])
    def test_construction_fails_for_out_of_range_month(self, month: int) -> None:
        """A month outside 1-12 is rejected."""
        with pytest.raises(ValueError):
            make_transfer(month=month)

    def test_construction_fails_for_non_positive_amount(self) -> None:
        """An `amount` of zero (or below) is rejected."""
        with pytest.raises(ValueError):
            make_transfer(amount=0.0)


class TestGetTableColumns:
    """Tests for `Transfer.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """The table has one column each for month, kind, description, source, destination and amount."""
        assert len(Transfer.get_table_columns()) == 6


class TestGetTableRow:
    """Tests for `Transfer.get_table_row`."""

    def test_formats_a_transfer_with_a_source_and_destination(self) -> None:
        """The kind, source and destination are all formatted for display."""
        row = {
            "month": 3,
            "kind": "LOAN",
            "description": "borrowed money",
            "source": "Bank A",
            "destination": "Bank B",
            "amount": 100.0,
        }

        cells = Transfer.get_table_row(row)

        assert cells[0].content.content.value == "3"
        assert cells[1].content.value == "Loan"
        assert cells[2].content.value == "borrowed money"
        assert cells[3].content.value == "Bank a"
        assert cells[4].content.value == "Bank b"
        assert cells[5].content.value == "100.00"

    def test_formats_a_missing_source_or_destination_as_an_em_dash(self) -> None:
        """A `None` source or destination renders as an em dash rather than the string "None"."""
        row = {
            "month": 3,
            "kind": "CREDIT",
            "description": "borrowed money",
            "source": None,
            "destination": "Bank B",
            "amount": 100.0,
        }

        cells = Transfer.get_table_row(row)

        assert cells[3].content.value == "—"
        assert cells[4].content.value == "Bank b"
