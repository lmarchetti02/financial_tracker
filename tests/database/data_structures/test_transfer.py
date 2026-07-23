"""Unit tests for `database.data_structures.transfer`."""

import pytest

from database.data_structures.transfer import Transfer


def make_transfer(**overrides: object) -> Transfer:
    """Builds a `:class:Transfer` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 1,
        "kind": "Loan",
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

    @pytest.mark.parametrize("day", [0, 32])
    def test_construction_fails_for_out_of_range_day(self, day: int) -> None:
        """A day outside 1-31 is rejected."""
        with pytest.raises(ValueError):
            make_transfer(day=day)

    def test_construction_fails_for_non_positive_amount(self) -> None:
        """An `amount` of zero (or below) is rejected."""
        with pytest.raises(ValueError):
            make_transfer(amount=0.0)

    def test_construction_fails_for_non_positive_fee(self) -> None:
        """A `fee` of zero (or below) is rejected."""
        with pytest.raises(ValueError):
            make_transfer(fee=0.0)

    def test_construction_fails_for_non_positive_profit(self) -> None:
        """A `profit` of zero (or below) is rejected."""
        with pytest.raises(ValueError):
            make_transfer(profit=0.0)

    def test_day_fee_profit_and_generated_ids_default_sensibly(self) -> None:
        """`day` defaults to 1 and `fee`/`fee_expense_id`/`profit`/`profit_income_id` default to `None`."""
        transfer = make_transfer()

        assert transfer.day == 1
        assert transfer.fee is None
        assert transfer.fee_expense_id is None
        assert transfer.profit is None
        assert transfer.profit_income_id is None


class TestGetTableColumns:
    """Tests for `Transfer.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """The table has one column each for month, day, kind, description, source, destination, amount, fee, profit."""
        assert len(Transfer.get_table_columns()) == 9


class TestGetTableRow:
    """Tests for `Transfer.get_table_row`."""

    def test_formats_a_transfer_with_a_source_and_destination(self) -> None:
        """The day, kind, source and destination are all formatted for display."""
        row = {
            "month": 3,
            "day": 15,
            "kind": "Loan",
            "description": "borrowed money",
            "source": "Bank A",
            "destination": "Bank B",
            "amount": 100.0,
            "fee": None,
            "profit": None,
        }

        cells = Transfer.get_table_row(row)

        assert cells[0].content.content.value == "3"
        assert cells[1].content.content.value == "15"
        assert cells[2].content.value == "Loan"
        assert cells[3].content.value == "borrowed money"
        assert cells[4].content.value == "Bank A"
        assert cells[5].content.value == "Bank B"
        assert cells[6].content.value == "100,00"
        assert cells[7].content.value == "—"
        assert cells[8].content.value == "—"

    def test_formats_a_missing_source_or_destination_as_an_em_dash(self) -> None:
        """A `None` source or destination renders as an em dash rather than the string "None"."""
        row = {
            "month": 3,
            "day": 15,
            "kind": "Credit",
            "description": "borrowed money",
            "source": None,
            "destination": "Bank B",
            "amount": 100.0,
            "fee": None,
            "profit": None,
        }

        cells = Transfer.get_table_row(row)

        assert cells[4].content.value == "—"
        assert cells[5].content.value == "Bank B"

    def test_formats_a_set_fee(self) -> None:
        """A non-`None` fee is formatted like any other currency value."""
        row = {
            "month": 3,
            "day": 15,
            "kind": "Investment",
            "description": "bought shares",
            "source": "Bank A",
            "destination": None,
            "amount": 100.0,
            "fee": 1.5,
            "profit": None,
        }

        cells = Transfer.get_table_row(row)

        assert cells[7].content.value == "1,50"

    def test_formats_a_set_profit(self) -> None:
        """A non-`None` profit is formatted like any other currency value."""
        row = {
            "month": 3,
            "day": 15,
            "kind": "Investment",
            "description": "sold shares",
            "source": None,
            "destination": "Bank A",
            "amount": 100.0,
            "fee": 1.5,
            "profit": 25.0,
        }

        cells = Transfer.get_table_row(row)

        assert cells[8].content.value == "25,00"
