"""Handles the backend of the application."""

from .expense import Categories, Expense
from .operations import (SortingConfig, add_expense, edit_expense, fetch_by_id,
                         fetch_category, fetch_expenses, remove_expense)
