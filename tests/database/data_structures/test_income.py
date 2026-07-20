"""Unit tests for `database.data_structures.income`."""

import pytest

from database.data_structures.income import Income, Sources


def make_income(**overrides: object) -> Income:
    """Builds an `:class:Income` with sensible defaults, overridden by `overrides`."""
    defaults = {
        "month": 6,
        "source": Sources.SALARY,
        "description": "paycheck",
        "amount": 2000.0,
    }
    defaults.update(overrides)
    return Income(**defaults)


class TestIncome:
    """Tests for `Income`."""

    @pytest.mark.parametrize("month", [0, 13])
    def test_construction_fails_for_out_of_range_month(self, month: int) -> None:
        """A month outside 1-12 is rejected."""
        with pytest.raises(ValueError):
            make_income(month=month)

    def test_construction_fails_for_non_positive_amount(self) -> None:
        """An `amount` of zero (or below) is rejected."""
        with pytest.raises(ValueError):
            make_income(amount=0.0)


class TestGetTableColumns:
    """Tests for `Income.get_table_columns`."""

    def test_returns_one_column_per_displayed_field(self) -> None:
        """The table has one column each for month, description, source and amount."""
        assert len(Income.get_table_columns()) == 4


class TestGetTableRow:
    """Tests for `Income.get_table_row`."""

    def test_formats_the_row(self) -> None:
        """The source enum and amount are formatted for display."""
        row = {"month": 6, "description": "paycheck", "source": "INVESTMENTS", "amount": 1234.5}

        cells = Income.get_table_row(row)

        assert cells[0].content.content.value == "6"
        assert cells[1].content.value == "paycheck"
        assert cells[2].content.value == "Investments"
        assert cells[3].content.value == "1234.50"
