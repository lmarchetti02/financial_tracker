"""Implementation of the main operations on the expenses database."""

from dataclasses import dataclass
from logging import getLogger

import numpy as np

from _helpers.constants import EXPENSES_DB_NAME

from ..data_structures import Categories, Expense
from .generic import fetch_monthly_totals, fetch_rows
from .utils import RowGenerator, SortingConfig

logger = getLogger("financial_tracker")


@dataclass
class ExpensesSortingConfig(SortingConfig):
    """Defines how the expenses are to be sorted."""

    def __post_init__(self) -> None:  # noqa: D105
        self._resolve({0: "month, day_start", 4: "cost"})


type ESC = ExpensesSortingConfig


def fetch_expenses(
    year: int, sort: ESC | None = None, month: int | None = None, category: Categories | None = None
) -> RowGenerator:
    """Fetches all the expenses.

    Args:
        year (int): The year of the expenses in the database.
        sort (ExpensesSortingConfig | None): If given, the rows gets sorted (see `ExpensesSortingConfig`).
            Defaults to `None`.
        month (int | None): The month to filter the table by.
            Defaults to `None`.
        category (Categories | None): The category to filter the table by. See `:enum:Categories`.
            Defaults to `None`.

    Returns:
        Generator[tuple[int, list[DataCell]], None, None]: The generator that yields the rows
            and the id of the expense in the database.
    """
    extra_filter = ("category", category) if category is not None else None
    return fetch_rows(year, EXPENSES_DB_NAME, Expense, sort=sort, month=month, extra_filter=extra_filter)


def fetch_category(year: int, category: Categories) -> np.ndarray:
    """Fetch the total expense per month for a specified category.

    Args:
        year (int): The year of the expenses.
        category (Categories): The desired category (see `:enum:Categories`).

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_category'")

    return fetch_monthly_totals(year, EXPENSES_DB_NAME, "cost", "category", category)


def fetch_expense_totals(year: int) -> np.ndarray:
    """Fetch the total expense per month across all categories.

    Args:
        year (int): The year of the expenses.

    Returns:
        np.ndarray: An array of shape (12,) with the totals per month.
    """
    logger.info("Called 'fetch_expense_totals'")

    return fetch_monthly_totals(year, EXPENSES_DB_NAME, "cost")
