"""Unit tests for `database.db_operations.incomes`."""

import pytest

from database.data_structures.income import Income, Sources
from database.db_operations.generic import WhichDb, add_item, initialize_db
from database.db_operations.incomes import IncomesSortingConfig, fetch_incomes

YEAR = 2024


def make_income(**overrides: object) -> Income:
    """Builds an `:class:Income` with sensible defaults, overridden by `overrides`."""
    defaults = {"month": 1, "source": Sources.SALARY, "description": "test income", "amount": 100.0}
    defaults.update(overrides)
    return Income(**defaults)


class TestIncomesSortingConfig:
    """Tests for `IncomesSortingConfig`."""

    def test_sorts_by_month(self) -> None:
        """Column 0 sorts by month in the requested direction."""
        config = IncomesSortingConfig(col_id=0, ascending=True)

        assert config.sql_command == "month ASC"

    def test_sorts_by_amount_descending(self) -> None:
        """Column 2 sorts by amount in the requested direction."""
        config = IncomesSortingConfig(col_id=2, ascending=False)

        assert config.sql_command == "amount DESC"

    def test_rejects_an_unsortable_column(self) -> None:
        """A column ID other than 0 or 2 is not sortable."""
        with pytest.raises(ValueError, match="cannot sort"):
            IncomesSortingConfig(col_id=1, ascending=True)


class TestFetchIncomes:
    """Tests for `fetch_incomes`."""

    def test_yields_the_id_and_row_of_every_income(self) -> None:
        """With no filter or sort, every income is yielded."""
        initialize_db(YEAR, WhichDb.INCOMES)
        add_item(YEAR, make_income(description="first"))
        add_item(YEAR, make_income(description="second"))

        ids = [row_id for row_id, _ in fetch_incomes(YEAR)]

        assert ids == [1, 2]

    def test_filters_by_month(self) -> None:
        """Only incomes matching the given month are yielded."""
        initialize_db(YEAR, WhichDb.INCOMES)
        add_item(YEAR, make_income(month=1))
        add_item(YEAR, make_income(month=2))

        results = list(fetch_incomes(YEAR, month=2))

        assert [row_id for row_id, _ in results] == [2]

    def test_sorts_by_amount(self) -> None:
        """The generator yields rows ordered per the given `IncomesSortingConfig`."""
        initialize_db(YEAR, WhichDb.INCOMES)
        add_item(YEAR, make_income(amount=300.0))
        add_item(YEAR, make_income(amount=100.0))
        sort = IncomesSortingConfig(col_id=2, ascending=True)

        ids = [row_id for row_id, _ in fetch_incomes(YEAR, sort=sort)]

        assert ids == [2, 1]
