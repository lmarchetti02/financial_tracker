"""Unit tests for `database.db_operations.transfers`."""

import pytest

from database.data_structures.transfer import Transfer
from database.db_operations.generic import DbLocation, WhichDb, add_item, initialize_db
from database.db_operations.transfers import (
    TransfersSortingConfig,
    fetch_fee_expense_ids,
    fetch_profit_income_ids,
    fetch_transfers,
)

YEAR = 2024
LOCATION = DbLocation(YEAR)


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


class TestTransfersSortingConfig:
    """Tests for `TransfersSortingConfig`."""

    def test_sorts_by_month(self) -> None:
        """Column 0 sorts by month in the requested direction."""
        config = TransfersSortingConfig(col_id=0, ascending=True)

        assert config.sql_command == "month ASC"

    def test_sorts_by_amount_descending(self) -> None:
        """Column 6 sorts by amount in the requested direction."""
        config = TransfersSortingConfig(col_id=6, ascending=False)

        assert config.sql_command == "amount DESC"

    def test_rejects_an_unsortable_column(self) -> None:
        """A column ID other than 0 or 6 is not sortable."""
        with pytest.raises(ValueError, match="cannot sort"):
            TransfersSortingConfig(col_id=1, ascending=True)


class TestFetchTransfers:
    """Tests for `fetch_transfers`."""

    def test_yields_the_id_and_row_of_every_transfer(self) -> None:
        """With no filter or sort, every transfer is yielded."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(description="first"))
        add_item(LOCATION, make_transfer(description="second"))

        ids = [row_id for row_id, _ in fetch_transfers(LOCATION)]

        assert ids == [1, 2]

    def test_filters_by_month(self) -> None:
        """Only transfers matching the given month are yielded."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(month=1))
        add_item(LOCATION, make_transfer(month=2))

        results = list(fetch_transfers(LOCATION, month=2))

        assert [row_id for row_id, _ in results] == [2]

    def test_sorts_by_amount(self) -> None:
        """The generator yields rows ordered per the given `TransfersSortingConfig`."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(amount=300.0))
        add_item(LOCATION, make_transfer(amount=100.0))
        sort = TransfersSortingConfig(col_id=6, ascending=True)

        ids = [row_id for row_id, _ in fetch_transfers(LOCATION, sort=sort)]

        assert ids == [2, 1]

    def test_filters_by_kind(self) -> None:
        """Only transfers matching the given kind are yielded."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(kind="Loan"))
        add_item(LOCATION, make_transfer(kind="Investment"))

        results = list(fetch_transfers(LOCATION, kind="Investment"))

        assert [row_id for row_id, _ in results] == [2]

    def test_combines_month_and_kind_filters(self) -> None:
        """Filtering by month and kind can be applied together."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(month=1, kind="Investment"))
        add_item(LOCATION, make_transfer(month=2, kind="Loan"))
        add_item(LOCATION, make_transfer(month=2, kind="Investment"))

        results = list(fetch_transfers(LOCATION, month=2, kind="Investment"))

        assert [row_id for row_id, _ in results] == [3]


class TestFetchFeeExpenseIds:
    """Tests for `fetch_fee_expense_ids`."""

    def test_returns_the_ids_referenced_by_a_transfer_s_fee(self) -> None:
        """A transfer with a `fee_expense_id` set contributes that id to the result."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(fee_expense_id=42))

        assert fetch_fee_expense_ids(LOCATION) == {42}

    def test_excludes_transfers_without_a_fee(self) -> None:
        """A transfer with no `fee_expense_id` does not contribute `None` to the result."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer())

        assert fetch_fee_expense_ids(LOCATION) == set()

    def test_combines_ids_from_multiple_transfers(self) -> None:
        """Ids from every transfer with a fee are included."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(fee_expense_id=1))
        add_item(LOCATION, make_transfer(fee_expense_id=2))
        add_item(LOCATION, make_transfer())

        assert fetch_fee_expense_ids(LOCATION) == {1, 2}


class TestFetchProfitIncomeIds:
    """Tests for `fetch_profit_income_ids`."""

    def test_returns_the_ids_referenced_by_a_transfer_s_profit(self) -> None:
        """A transfer with a `profit_income_id` set contributes that id to the result."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(profit_income_id=42))

        assert fetch_profit_income_ids(LOCATION) == {42}

    def test_excludes_transfers_without_a_profit(self) -> None:
        """A transfer with no `profit_income_id` does not contribute `None` to the result."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer())

        assert fetch_profit_income_ids(LOCATION) == set()

    def test_combines_ids_from_multiple_transfers(self) -> None:
        """Ids from every transfer with a profit are included."""
        initialize_db(LOCATION, WhichDb.TRANSFERS)
        add_item(LOCATION, make_transfer(profit_income_id=1))
        add_item(LOCATION, make_transfer(profit_income_id=2))
        add_item(LOCATION, make_transfer())

        assert fetch_profit_income_ids(LOCATION) == {1, 2}
