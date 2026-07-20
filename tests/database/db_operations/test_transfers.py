"""Unit tests for `database.db_operations.transfers`."""

import pytest

from database.data_structures.transfer import Kind, Transfer
from database.db_operations.generic import WhichDb, add_item, initialize_db
from database.db_operations.transfers import TransfersSortingConfig, fetch_transfers

YEAR = 2024


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
        initialize_db(YEAR, WhichDb.TRANSFERS)
        add_item(YEAR, make_transfer(description="first"))
        add_item(YEAR, make_transfer(description="second"))

        ids = [row_id for row_id, _ in fetch_transfers(YEAR)]

        assert ids == [1, 2]

    def test_filters_by_month(self) -> None:
        """Only transfers matching the given month are yielded."""
        initialize_db(YEAR, WhichDb.TRANSFERS)
        add_item(YEAR, make_transfer(month=1))
        add_item(YEAR, make_transfer(month=2))

        results = list(fetch_transfers(YEAR, month=2))

        assert [row_id for row_id, _ in results] == [2]

    def test_sorts_by_amount(self) -> None:
        """The generator yields rows ordered per the given `TransfersSortingConfig`."""
        initialize_db(YEAR, WhichDb.TRANSFERS)
        add_item(YEAR, make_transfer(amount=300.0))
        add_item(YEAR, make_transfer(amount=100.0))
        sort = TransfersSortingConfig(col_id=6, ascending=True)

        ids = [row_id for row_id, _ in fetch_transfers(YEAR, sort=sort)]

        assert ids == [2, 1]

    def test_filters_by_kind(self) -> None:
        """Only transfers matching the given kind are yielded."""
        initialize_db(YEAR, WhichDb.TRANSFERS)
        add_item(YEAR, make_transfer(kind=Kind.LOAN))
        add_item(YEAR, make_transfer(kind=Kind.INVESTMENT))

        results = list(fetch_transfers(YEAR, kind=Kind.INVESTMENT))

        assert [row_id for row_id, _ in results] == [2]

    def test_combines_month_and_kind_filters(self) -> None:
        """Filtering by month and kind can be applied together."""
        initialize_db(YEAR, WhichDb.TRANSFERS)
        add_item(YEAR, make_transfer(month=1, kind=Kind.INVESTMENT))
        add_item(YEAR, make_transfer(month=2, kind=Kind.LOAN))
        add_item(YEAR, make_transfer(month=2, kind=Kind.INVESTMENT))

        results = list(fetch_transfers(YEAR, month=2, kind=Kind.INVESTMENT))

        assert [row_id for row_id, _ in results] == [3]
