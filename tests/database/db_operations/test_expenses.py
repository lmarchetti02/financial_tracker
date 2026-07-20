"""Unit tests for `database.db_operations.expenses`."""

import pytest

from database.data_structures.expense import Categories, Expense
from database.db_operations.expenses import ExpensesSortingConfig, fetch_category, fetch_expenses
from database.db_operations.generic import WhichDb, add_item, initialize_db

YEAR = 2024


def make_expense(**overrides: object) -> Expense:
    """Builds an `:class:Expense` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 1,
        "day_start": 1,
        "description": "test expense",
        "category": Categories.FOOD_AND_DRINKS,
        "cost": 10.0,
    }
    defaults.update(overrides)
    return Expense(**defaults)


class TestExpensesSortingConfig:
    """Tests for `ExpensesSortingConfig`."""

    def test_sorts_by_month_then_day(self) -> None:
        """Column 0 sorts by month, then day, in the requested direction."""
        config = ExpensesSortingConfig(col_id=0, ascending=True)

        assert config.sql_command == "month ASC, day_start ASC"

    def test_sorts_by_cost_descending(self) -> None:
        """Column 4 sorts by cost in the requested direction."""
        config = ExpensesSortingConfig(col_id=4, ascending=False)

        assert config.sql_command == "cost DESC"

    def test_rejects_an_unsortable_column(self) -> None:
        """A column ID other than 0 or 4 is not sortable."""
        with pytest.raises(ValueError, match="cannot sort"):
            ExpensesSortingConfig(col_id=2, ascending=True)


class TestFetchExpenses:
    """Tests for `fetch_expenses`."""

    def test_yields_the_id_and_row_of_every_expense(self) -> None:
        """With no filter or sort, every expense is yielded."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(description="first"))
        add_item(YEAR, make_expense(description="second"))

        ids = [row_id for row_id, _ in fetch_expenses(YEAR)]

        assert ids == [1, 2]

    def test_filters_by_month(self) -> None:
        """Only expenses matching the given month are yielded."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(month=1))
        add_item(YEAR, make_expense(month=2))

        results = list(fetch_expenses(YEAR, month=2))

        assert [row_id for row_id, _ in results] == [2]

    def test_sorts_by_cost(self) -> None:
        """The generator yields rows ordered per the given `ExpensesSortingConfig`."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(cost=30.0))
        add_item(YEAR, make_expense(cost=10.0))
        sort = ExpensesSortingConfig(col_id=4, ascending=True)

        ids = [row_id for row_id, _ in fetch_expenses(YEAR, sort=sort)]

        assert ids == [2, 1]

    def test_combines_month_filter_with_sort(self) -> None:
        """Filtering by month and sorting can be applied together."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(month=1, cost=1.0))
        add_item(YEAR, make_expense(month=2, cost=30.0))
        add_item(YEAR, make_expense(month=2, cost=10.0))
        sort = ExpensesSortingConfig(col_id=4, ascending=True)

        ids = [row_id for row_id, _ in fetch_expenses(YEAR, sort=sort, month=2)]

        assert ids == [3, 2]


class TestFetchCategory:
    """Tests for `fetch_category`."""

    def test_sums_cost_per_month_for_the_given_category(self) -> None:
        """Costs for the requested category are summed per month; other categories are excluded."""
        initialize_db(YEAR, WhichDb.EXPENSES)
        add_item(YEAR, make_expense(month=1, category=Categories.FOOD_AND_DRINKS, cost=10.0))
        add_item(YEAR, make_expense(month=1, category=Categories.FOOD_AND_DRINKS, cost=5.0))
        add_item(YEAR, make_expense(month=3, category=Categories.FOOD_AND_DRINKS, cost=7.0))
        add_item(YEAR, make_expense(month=1, category=Categories.TRAVEL, cost=100.0))

        totals = fetch_category(YEAR, Categories.FOOD_AND_DRINKS)

        assert totals[0] == pytest.approx(15.0)
        assert totals[1] == pytest.approx(0.0)
        assert totals[2] == pytest.approx(7.0)

    def test_returns_all_zeros_when_no_expenses_match(self) -> None:
        """An empty table yields a 12-month array of zeros rather than an error."""
        initialize_db(YEAR, WhichDb.EXPENSES)

        totals = fetch_category(YEAR, Categories.OTHER)

        assert totals.shape == (12,)
        assert (totals == 0).all()
