"""Unit tests for `database.data_structures.expense`."""

import pytest

from database.data_structures.expense import Expense


def make_expense(**overrides: object) -> Expense:
    """Builds an `:class:Expense` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 6,
        "day_start": 10,
        "description": "groceries",
        "category": "Food and drinks",
        "cost": 25.5,
    }
    defaults.update(overrides)
    return Expense(**defaults)


class TestExpense:
    """Tests for `Expense`."""

    def test_construction_succeeds_for_a_single_day(self) -> None:
        """A single-day expense leaves `day_end` unset."""
        expense = make_expense(day_start=5)

        assert expense.day_start == 5
        assert expense.day_end is None

    def test_construction_succeeds_for_a_day_range(self) -> None:
        """A multi-day expense accepts a `day_end` on or after `day_start`."""
        expense = make_expense(day_start=5, day_end=10)

        assert expense.day_end == 10

    def test_construction_fails_when_day_end_is_before_day_start(self) -> None:
        """A `day_end` earlier than `day_start` is rejected."""
        with pytest.raises(ValueError, match="End date cannot be before start date"):
            make_expense(day_start=10, day_end=5)

    @pytest.mark.parametrize("month", [0, 13])
    def test_construction_fails_for_out_of_range_month(self, month: int) -> None:
        """A month outside 1-12 is rejected."""
        with pytest.raises(ValueError):
            make_expense(month=month)

    @pytest.mark.parametrize("day", [0, 32])
    def test_construction_fails_for_out_of_range_day_start(self, day: int) -> None:
        """A `day_start` outside 1-31 is rejected."""
        with pytest.raises(ValueError):
            make_expense(day_start=day)

    def test_construction_fails_for_non_positive_cost(self) -> None:
        """A `cost` of zero (or below) is rejected."""
        with pytest.raises(ValueError):
            make_expense(cost=0.0)

    def test_cost_expression_defaults_to_none(self) -> None:
        """`cost_expression` defaults to `None` when not provided."""
        expense = make_expense()

        assert expense.cost_expression is None

    def test_cost_expression_round_trips_when_set(self) -> None:
        """`cost_expression` stores the raw text passed in verbatim."""
        expense = make_expense(cost_expression="10+3-2")

        assert expense.cost_expression == "10+3-2"


class TestGetTableColumns:
    """Tests for `Expense.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """The table has one column each for month, day, description, category and cost."""
        assert len(Expense.get_table_columns()) == 5


class TestGetTableRow:
    """Tests for `Expense.get_table_row`."""

    def test_formats_a_single_day_expense(self) -> None:
        """A single-day row shows the day as-is and formats category/cost for display."""
        row = {
            "month": 6,
            "day_start": 10,
            "day_end": None,
            "description": "groceries",
            "category": "Food and drinks",
            "cost": 25.5,
        }

        cells = Expense.get_table_row(row)

        assert cells[0].content.content.value == "6"
        assert cells[1].content.content.value == "10"
        assert cells[2].content.value == "Food and drinks"
        assert cells[3].content.value == "groceries"
        assert cells[4].content.value == "25,50"

    def test_formats_a_multi_day_expense_as_a_range(self) -> None:
        """A multi-day row shows the days as a `start-end` range."""
        row = {
            "month": 6,
            "day_start": 10,
            "day_end": 12,
            "description": "trip",
            "category": "Travel",
            "cost": 100.0,
        }

        cells = Expense.get_table_row(row)

        assert cells[1].content.content.value == "10-12"
