"""Tests the `:class:Expense` class."""

import pytest
from pydantic import ValidationError

from src.database import Categories, Expense


class TestExpense:
    """Class to test the `Expense` class."""

    def test_valid_expense(self):
        """Tests a valid expense."""
        expense = Expense(
            month=10,
            day_start=15,
            day_end=18,
            description="Physics symposium",
            category=Categories.EDUCATION,
            cost=350.50,
        )
        assert expense.month == 10
        assert expense.cost == 350.50
        assert expense.category == Categories.EDUCATION

    @pytest.mark.parametrize(
        "invalid_data",
        [
            {"month": 13, "day_start": 1, "description": "x", "category": Categories.OTHER, "cost": 10.0},
            {"month": 0, "day_start": 1, "description": "x", "category": Categories.OTHER, "cost": 10.0},
            {"month": 5, "day_start": 32, "description": "x", "category": Categories.OTHER, "cost": 10.0},
            {"month": 5, "day_start": 1, "day_end": 0, "description": "x", "category": Categories.OTHER, "cost": 10.0},
            {"month": 5, "day_start": 10, "day_end": 8, "description": "x", "category": Categories.OTHER, "cost": 10.0},
            {"month": 5, "day_start": 1, "description": "x", "category": Categories.OTHER, "cost": -5.0},
            {"month": 5, "day_start": 1, "description": "x", "category": Categories.OTHER, "cost": 0.0},
        ],
    )
    def test_expense_boundary_validation(self, invalid_data):
        """Tests boundaries for each attribute."""
        with pytest.raises(ValidationError):
            Expense(**invalid_data)

    def test_create_table_schema(self):
        """Tests the sqlite command."""
        query = Expense.create_table()

        expected_substrings = [
            "CREATE TABLE IF NOT EXISTS expenses",
            "id INTEGER PRIMARY KEY AUTOINCREMENT",
            "month INTEGER NOT NULL",
            "day_start INTEGER NOT NULL",
            "category TEXT NOT NULL",
            "cost REAL NOT NULL",
        ]

        for substring in expected_substrings:
            assert substring in query
